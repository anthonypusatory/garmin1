"""Pull your Garmin workouts and recovery data into plain-English notes.

Read-only: this only ever reads from Garmin Connect, never writes to it.

Usage:
    python sync.py            # last 7 days
    python sync.py --days 3   # last 3 days
    python sync.py --all-activities --since first --skip-existing
                              # full history backfill; safe to re-run to resume

Output (in ./garmin/):
    wellness/YYYY-MM-DD.md        one note per day: sleep, HRV, resting HR,
                                  body battery, stress, steps, readiness
    activities/YYYY-MM-DD-<type>-<id>.md   one note per workout
    data.json                     everything above as structured data
                                  (merged across runs, so history builds up)
    index.md                      list of every day and workout on file

Needs a saved login token; run login.py once first.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

TOKENSTORE = os.getenv("GARMINTOKENS", str(Path.home() / ".garminconnect"))
OUT = Path(__file__).resolve().parent / "garmin"

KM_PER_MI = 1.609344


# ---------------------------------------------------------------- helpers ---

def safe(fn, *args):
    """Call a Garmin endpoint; return None instead of crashing if it fails."""
    try:
        return fn(*args)
    except GarminConnectTooManyRequestsError:
        raise
    except Exception as e:  # one missing metric shouldn't stop the whole sync
        print(f"  (skipped {fn.__name__} {' '.join(map(str, args))}: {e})")
        return None


def hm(seconds):
    if seconds is None:
        return None
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m {s:02d}s" if s and m < 10 else f"{m}m"


def pace(seconds_per_unit):
    if not seconds_per_unit:
        return None
    m, s = divmod(int(round(seconds_per_unit)), 60)
    return f"{m}:{s:02d}"


def rnd(x, n=1):
    if x is None:
        return None
    return int(round(x)) if n == 0 else round(x, n)


def line(label, value, suffix=""):
    """A bullet line, or nothing if the value is missing."""
    if value is None or value == "":
        return None
    return f"- **{label}:** {value}{suffix}"


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "activity").lower()).strip("-")


# ---------------------------------------------------------------- wellness ---

def fetch_day(g: Garmin, d: str) -> dict:
    summary = safe(g.get_user_summary, d) or {}
    sleep = safe(g.get_sleep_data, d) or {}
    hrv = safe(g.get_hrv_data, d) or {}
    readiness = safe(g.get_training_readiness, d) or []

    s = sleep.get("dailySleepDTO") or {}
    scores = s.get("sleepScores") or {}
    hrv_sum = hrv.get("hrvSummary") or {}
    baseline = hrv_sum.get("baseline") or {}
    # Garmin can return several readiness readings a day; keep the latest one.
    tr = readiness[0] if isinstance(readiness, list) and readiness else (
        readiness if isinstance(readiness, dict) else {})

    return {
        "date": d,
        "sleep": {
            "total_seconds": s.get("sleepTimeSeconds"),
            "deep_seconds": s.get("deepSleepSeconds"),
            "light_seconds": s.get("lightSleepSeconds"),
            "rem_seconds": s.get("remSleepSeconds"),
            "awake_seconds": s.get("awakeSleepSeconds"),
            "score": (scores.get("overall") or {}).get("value"),
            "quality": (scores.get("overall") or {}).get("qualifierKey"),
            "avg_overnight_hrv": sleep.get("avgOvernightHrv"),
            "avg_respiration": s.get("averageRespirationValue"),
            "avg_spo2": s.get("averageSpO2Value"),
        },
        "hrv": {
            "last_night_avg_ms": hrv_sum.get("lastNightAvg"),
            "last_night_5min_high_ms": hrv_sum.get("lastNight5MinHigh"),
            "weekly_avg_ms": hrv_sum.get("weeklyAvg"),
            "status": hrv_sum.get("status"),
            "baseline_low_ms": baseline.get("balancedLow"),
            "baseline_high_ms": baseline.get("balancedUpper"),
        },
        "resting_hr": summary.get("restingHeartRate"),
        "resting_hr_7day_avg": summary.get("lastSevenDaysAvgRestingHeartRate"),
        "body_battery": {
            "high": summary.get("bodyBatteryHighestValue"),
            "low": summary.get("bodyBatteryLowestValue"),
            "charged": summary.get("bodyBatteryChargedValue"),
            "drained": summary.get("bodyBatteryDrainedValue"),
            "at_wake": summary.get("bodyBatteryAtWakeTime"),
            "latest": summary.get("bodyBatteryMostRecentValue"),
        },
        "stress": {
            "average": summary.get("averageStressLevel"),
            "max": summary.get("maxStressLevel"),
            "rest_seconds": summary.get("restStressDuration"),
            "low_seconds": summary.get("lowStressDuration"),
            "medium_seconds": summary.get("mediumStressDuration"),
            "high_seconds": summary.get("highStressDuration"),
        },
        "steps": summary.get("totalSteps"),
        "step_goal": summary.get("dailyStepGoal"),
        "calories_total": summary.get("totalKilocalories"),
        "calories_active": summary.get("activeKilocalories"),
        "intensity_minutes": {
            "moderate": summary.get("moderateIntensityMinutes"),
            "vigorous": summary.get("vigorousIntensityMinutes"),
        },
        "training_readiness": {
            "score": tr.get("score"),
            "level": tr.get("level"),
            "feedback": tr.get("feedbackShort"),
            "recovery_time_hours": rnd((tr.get("recoveryTime") or 0) / 60, 0)
            if tr.get("recoveryTime") is not None else None,
            "acute_load": tr.get("acuteLoad"),
            "sleep_score_factor_pct": tr.get("sleepScoreFactorPercent"),
            "hrv_factor_pct": tr.get("hrvFactorPercent"),
            "recovery_factor_pct": tr.get("recoveryTimeFactorPercent"),
            "load_factor_pct": tr.get("acwrFactorPercent"),
        },
    }


def pretty(key):
    return (key or "").replace("_", " ").lower() or None


def day_note(w: dict) -> str:
    d = datetime.strptime(w["date"], "%Y-%m-%d")
    sl, hv, bb, st, tr = (w["sleep"], w["hrv"], w["body_battery"],
                          w["stress"], w["training_readiness"])

    stages = None
    if sl["total_seconds"]:
        stages = (f"deep {hm(sl['deep_seconds'])}, light {hm(sl['light_seconds'])}, "
                  f"REM {hm(sl['rem_seconds'])}, awake {hm(sl['awake_seconds'])}")
    baseline = None
    if hv["baseline_low_ms"] and hv["baseline_high_ms"]:
        baseline = f"{hv['baseline_low_ms']}–{hv['baseline_high_ms']} ms"
    steps = None
    if w["steps"] is not None:
        steps = f"{w['steps']:,}" + (f" (goal {w['step_goal']:,})" if w["step_goal"] else "")
    readiness = None
    if tr["score"] is not None:
        readiness = f"{tr['score']}/100" + (f" ({pretty(tr['level'])})" if tr["level"] else "")

    sections = [
        f"# Wellness — {d:%A, %B} {d.day}, {d.year}",
        "",
        "## Training readiness",
        line("Score", readiness),
        line("Garmin's take", pretty(tr["feedback"])),
        line("Recovery time left", tr["recovery_time_hours"], " h"),
        line("Acute training load", tr["acute_load"]),
        "",
        "## Sleep (night ending this morning)",
        line("Total", hm(sl["total_seconds"])),
        line("Sleep score", sl["score"], f" ({pretty(sl['quality'])})" if sl["quality"] else ""),
        line("Stages", stages),
        line("Avg respiration", rnd(sl["avg_respiration"]), " breaths/min"),
        line("Avg SpO2", sl["avg_spo2"], "%"),
        "",
        "## HRV",
        line("Last night avg", hv["last_night_avg_ms"], " ms"),
        line("7-day avg", hv["weekly_avg_ms"], " ms"),
        line("Status", pretty(hv["status"])),
        line("Your balanced range", baseline),
        "",
        "## Heart, body battery, stress",
        line("Resting HR", w["resting_hr"], " bpm"),
        line("Resting HR 7-day avg", w["resting_hr_7day_avg"], " bpm"),
        line("Body battery at wake", bb["at_wake"]),
        line("Body battery high / low", f"{bb['high']} / {bb['low']}" if bb["high"] is not None else None),
        line("Charged / drained", f"+{bb['charged']} / -{bb['drained']}" if bb["charged"] is not None else None),
        line("Avg stress", st["average"], " (0–100, under 25 is restful)"),
        line("High-stress time", hm(st["high_seconds"])),
        "",
        "## Activity",
        line("Steps", steps),
        line("Intensity minutes", f"{w['intensity_minutes']['moderate']} moderate, "
             f"{w['intensity_minutes']['vigorous']} vigorous"
             if w["intensity_minutes"]["moderate"] is not None else None),
        line("Calories", f"{w['calories_total']:,.0f} total, {w['calories_active']:,.0f} active"
             if w["calories_total"] is not None and w["calories_active"] is not None else None),
    ]
    text = "\n".join(s for s in sections if s is not None)
    # Drop headings left with nothing under them.
    text = re.sub(r"## [^\n]+\n\n(?=## |\Z)", "", text + "\n")
    return text.rstrip() + "\n"


# -------------------------------------------------------------- activities ---

def clean_activity(a: dict) -> dict:
    dist_m = a.get("distance") or 0
    dur = a.get("duration") or 0
    zones = {f"z{i}_seconds": a.get(f"hrTimeInZone_{i}") for i in range(1, 6)}
    return {
        "id": a.get("activityId"),
        "name": a.get("activityName"),
        "type": (a.get("activityType") or {}).get("typeKey"),
        "start_local": a.get("startTimeLocal"),
        "duration_seconds": rnd(dur, 0),
        "moving_seconds": rnd(a.get("movingDuration"), 0),
        "distance_km": rnd(dist_m / 1000, 2) if dist_m else None,
        "distance_mi": rnd(dist_m / 1000 / KM_PER_MI, 2) if dist_m else None,
        "pace_per_km": pace(dur / (dist_m / 1000)) if dist_m and dur else None,
        "pace_per_mi": pace(dur / (dist_m / 1000 / KM_PER_MI)) if dist_m and dur else None,
        "avg_hr": a.get("averageHR"),
        "max_hr": a.get("maxHR"),
        "calories": a.get("calories"),
        "elevation_gain_m": rnd(a.get("elevationGain"), 0),
        "avg_power_w": a.get("avgPower"),
        "normalized_power_w": a.get("normPower"),
        "avg_cadence": a.get("averageRunningCadenceInStepsPerMinute")
        or a.get("averageBikingCadenceInRevPerMinute"),
        "aerobic_te": rnd(a.get("aerobicTrainingEffect")),
        "anaerobic_te": rnd(a.get("anaerobicTrainingEffect")),
        "te_label": a.get("trainingEffectLabel"),
        "training_load": rnd(a.get("activityTrainingLoad"), 0),
        "vo2max": a.get("vO2MaxValue"),
        "hr_zones": zones if any(v for v in zones.values()) else None,
        "description": a.get("description"),
    }


def activity_note(a: dict) -> str:
    start = datetime.strptime(a["start_local"], "%Y-%m-%d %H:%M:%S")
    dist = None
    if a["distance_km"]:
        dist = f"{a['distance_mi']} mi ({a['distance_km']} km)"
    pace_txt = None
    if a["pace_per_mi"] and a["type"] and any(k in a["type"] for k in ("run", "walk", "hik")):
        pace_txt = f"{a['pace_per_mi']} /mi ({a['pace_per_km']} /km)"
    te = None
    if a["aerobic_te"] is not None:
        te = f"aerobic {a['aerobic_te']}, anaerobic {a['anaerobic_te']}"
        if a["te_label"]:
            te += f" — {pretty(a['te_label'])}"
    zones = None
    if a["hr_zones"]:
        zones = ", ".join(f"Z{i} {hm(a['hr_zones'][f'z{i}_seconds']) or '0m'}" for i in range(1, 6))

    rows = [
        f"# {a['name'] or pretty(a['type'])}",
        "",
        f"{pretty(a['type']).capitalize() if a['type'] else 'Activity'} on {start:%A, %B} {start.day}, {start.year} at {start.hour % 12 or 12}:{start:%M %p}.",
        "",
        line("Duration", hm(a["duration_seconds"])),
        line("Moving time", hm(a["moving_seconds"]) if a["moving_seconds"] and a["moving_seconds"] != a["duration_seconds"] else None),
        line("Distance", dist),
        line("Avg pace", pace_txt),
        line("Avg / max HR", f"{a['avg_hr']:.0f} / {a['max_hr']:.0f} bpm" if a["avg_hr"] and a["max_hr"] else None),
        line("Time in HR zones", zones),
        line("Elevation gain", a["elevation_gain_m"], " m"),
        line("Avg / normalized power", f"{a['avg_power_w']:.0f} / {a['normalized_power_w']:.0f} W"
             if a["avg_power_w"] and a["normalized_power_w"] else None),
        line("Avg cadence", rnd(a["avg_cadence"], 0)),
        line("Training effect", te),
        line("Training load", a["training_load"]),
        line("VO2 max estimate", a["vo2max"]),
        line("Calories", rnd(a["calories"], 0)),
        line("Notes", a["description"]),
        "",
        f"Garmin activity ID: {a['id']}",
    ]
    return "\n".join(r for r in rows if r is not None) + "\n"


def activity_filename(a: dict) -> str:
    return f"{a['start_local'][:10]}-{slug(a['type'])}-{a['id']}.md"


# -------------------------------------------------------------------- main ---

def write_index(data: dict) -> None:
    lines = ["# Garmin data index", "",
             f"Last synced {data['last_synced']}.", "", "## Days", ""]
    for d in sorted(data["days"], reverse=True):
        w = data["days"][d]
        bits = []
        if w["training_readiness"]["score"] is not None:
            bits.append(f"readiness {w['training_readiness']['score']}")
        if w["sleep"]["score"] is not None:
            bits.append(f"sleep {w['sleep']['score']}")
        if w["hrv"]["last_night_avg_ms"] is not None:
            bits.append(f"HRV {w['hrv']['last_night_avg_ms']}")
        if w["resting_hr"] is not None:
            bits.append(f"RHR {w['resting_hr']}")
        lines.append(f"- [{d}](wellness/{d}.md)" + (f" — {', '.join(bits)}" if bits else ""))
    lines += ["", "## Workouts", ""]
    for a in sorted(data["activities"].values(), key=lambda x: x["start_local"], reverse=True):
        dist = f", {a['distance_mi']} mi" if a["distance_mi"] else ""
        lines.append(f"- [{a['start_local'][:10]} {a['name']}](activities/{activity_filename(a)})"
                     f" — {hm(a['duration_seconds'])}{dist}")
    (OUT / "index.md").write_text("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--days", type=int, default=7, help="how many days back to pull (default 7)")
    ap.add_argument("--since", help="pull wellness from this date (YYYY-MM-DD) instead of --days; "
                    "'first' means the date of your first workout on file")
    ap.add_argument("--skip-existing", action="store_true",
                    help="don't re-download days already in data.json (makes backfills resumable)")
    ap.add_argument("--all-activities", action="store_true",
                    help="download your entire workout history, not just the date range")
    args = ap.parse_args()

    g = Garmin()
    try:
        g.login(TOKENSTORE)
    except (GarminConnectAuthenticationError, FileNotFoundError):
        print("Not logged in (or the saved token expired). Run login.py once, then try again.")
        return 2
    except GarminConnectConnectionError as e:
        print(f"Could not reach Garmin: {e}")
        return 1

    today = date.today()

    (OUT / "wellness").mkdir(parents=True, exist_ok=True)
    (OUT / "activities").mkdir(parents=True, exist_ok=True)
    data_path = OUT / "data.json"
    data = json.loads(data_path.read_text()) if data_path.exists() else {}
    data.setdefault("days", {})
    data.setdefault("activities", {})

    def save():
        data["last_synced"] = datetime.now().isoformat(timespec="seconds")
        data_path.write_text(json.dumps(data, indent=2, sort_keys=True))

    def keep(raw):
        a = clean_activity(raw)
        data["activities"][str(a["id"])] = a
        (OUT / "activities" / activity_filename(a)).write_text(activity_note(a))

    n_acts, n_days = 0, 0
    try:
        # Workouts first: a whole history is only a few requests.
        if args.all_activities:
            print("Workouts (entire history)...")
            page = 0
            while True:
                batch = safe(g.get_activities, page * 100, 100) or []
                for raw in batch:
                    keep(raw)
                n_acts += len(batch)
                print(f"  {n_acts} workouts so far")
                if len(batch) < 100:
                    break
                page += 1
                time.sleep(1)
            save()

        if args.since == "first":
            starts = [a["start_local"][:10] for a in data["activities"].values() if a.get("start_local")]
            start = date.fromisoformat(min(starts)) if starts else today - timedelta(days=args.days - 1)
        elif args.since:
            start = date.fromisoformat(args.since)
        else:
            start = today - timedelta(days=args.days - 1)

        if not args.all_activities:
            print("Workouts...")
            acts = safe(g.get_activities_by_date, start.isoformat(), today.isoformat()) or []
            for raw in acts:
                keep(raw)
            n_acts = len(acts)

        total = (today - start).days + 1
        for i in range(total):
            d = (start + timedelta(days=i)).isoformat()
            # Always refresh the last 2 days; they change as the day goes on.
            if args.skip_existing and d in data["days"] and i < total - 2:
                continue
            print(f"Wellness {d} ({i + 1}/{total})...")
            w = fetch_day(g, d)
            data["days"][d] = w
            (OUT / "wellness" / f"{d}.md").write_text(day_note(w))
            n_days += 1
            if n_days % 25 == 0:
                save()  # so a long backfill never loses progress
            time.sleep(0.5)  # be gentle with Garmin's servers
    except GarminConnectTooManyRequestsError:
        print("Garmin is rate-limiting requests. Saved what we had; run the same command later to continue.")

    save()
    write_index(data)
    print(f"Done: {n_days} day(s) of wellness, {n_acts} workout(s). "
          f"{len(data['days'])} days and {len(data['activities'])} workouts on file. Notes are in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
