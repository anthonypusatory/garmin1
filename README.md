# garmin-ai

Pulls your own Garmin workouts and recovery data (sleep, HRV, resting HR, body
battery, stress, steps, training readiness) into a local `garmin/` folder of
plain-English markdown notes plus `garmin/data.json`, so Claude can read it.
Read-only: it never writes anything to your Garmin account.

Built on [python-garminconnect](https://github.com/cyberjunky/python-garminconnect).

## Setup (Claude Code does this for you)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip
```

One-time login. Run it yourself so your password goes into a hidden prompt and
never into the chat. In Claude Code, type it with a leading `!`:

```
! .venv/bin/python login.py
```

It asks for your email, password, and a 2FA code if Garmin sends one. Only the
login token is saved, to `~/.garminconnect` (owner-only permissions, outside this
folder, never committed).

## Sync

```bash
.venv/bin/python sync.py --days 3   # default is 7
```

Output:

- `garmin/index.md`: every day and workout on file
- `garmin/wellness/YYYY-MM-DD.md`: one note per day
- `garmin/activities/YYYY-MM-DD-<type>-<id>.md`: one note per workout
- `garmin/data.json`: all of it as structured data, merged across runs

`garmin/` is git-ignored, so your health data stays on your computer.
