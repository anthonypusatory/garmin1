"""Build a retro CRT-terminal dashboard from garmin/data.json.

Usage:
    python dashboard.py          # writes garmin/dashboard.html
    python dashboard.py --open   # ...and opens it in your browser

Everything is embedded in one local HTML file; no data leaves your computer.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent / "garmin"

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Crew Vitals Terminal</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500&display=swap" rel="stylesheet">
<style>
:root {
  --fg: #5dffa0; --dim: #2f9a5c; --line: rgba(93,255,160,.22); --bg: #020a05; --glow: rgba(93,255,160,.35);
}
:root[data-phos="amber"] { --fg: #ffbf47; --dim: #a8792a; --line: rgba(255,191,71,.22); --bg: #0a0702; --glow: rgba(255,191,71,.35); }
:root[data-phos="cyan"]  { --fg: #7cf4ff; --dim: #3b9aa5; --line: rgba(124,244,255,.22); --bg: #01080b; --glow: rgba(124,244,255,.32); }

* { box-sizing: border-box; }
html, body { margin: 0; background: #000; }
body {
  color: var(--fg); font-family: 'IBM Plex Mono', 'Menlo', monospace; font-weight: 400;
  font-size: 13px; line-height: 1.5; letter-spacing: .02em;
  text-shadow: 0 0 6px var(--glow);
  min-height: 100vh; -webkit-font-smoothing: antialiased;
}
.screen {
  position: relative; min-height: 100vh; padding: 28px 32px 36px;
  background: radial-gradient(ellipse at 50% 40%, var(--bg) 0%, #000 110%);
  animation: flicker 7s infinite steps(1);
}
.wrap { max-width: 1320px; margin: 0 auto; }
.screen::before {  /* scanlines */
  content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 50;
  background: repeating-linear-gradient(to bottom, rgba(0,0,0,.22) 0 1px, transparent 1px 3px);
}
.screen::after {   /* curved-glass vignette */
  content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 51;
  background: radial-gradient(ellipse at center, transparent 60%, rgba(0,0,0,.7) 100%);
}
@keyframes flicker { 0%{opacity:1} 47%{opacity:.97} 48%{opacity:1} }
.blink { animation: blink 1.1s steps(1) infinite; }
@keyframes blink { 50% { opacity: 0; } }

header { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-end; gap: 10px 24px;
  border-bottom: 1px solid var(--line); padding-bottom: 12px; margin-bottom: 26px; }
h1 { font-size: 15px; margin: 0 0 4px; font-weight: 500; letter-spacing: .5em; }
.sub, .k { color: var(--dim); text-shadow: none; }
.sub { font-size: 10.5px; letter-spacing: .22em; }
.phos { display: flex; gap: 4px; align-items: center; font-size: 10.5px; letter-spacing: .2em; }
.phos button {
  font: inherit; letter-spacing: .15em; background: none; color: var(--dim); border: 1px solid var(--line);
  padding: 3px 9px; cursor: pointer;
}
.phos button:hover { color: var(--fg); }
.phos button[aria-pressed="true"] { background: var(--fg); color: #000; border-color: var(--fg); text-shadow: none; }

.grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 16px; }
.panel { position: relative; border: 1px solid var(--line); padding: 34px 18px 18px; min-width: 0; }
.panel::before { /* corner brackets */
  content: ""; position: absolute; inset: -1px; pointer-events: none; --c: var(--fg); --s: 9px;
  background:
    linear-gradient(var(--c),var(--c)) top left / var(--s) 1px no-repeat,
    linear-gradient(var(--c),var(--c)) top left / 1px var(--s) no-repeat,
    linear-gradient(var(--c),var(--c)) top right / var(--s) 1px no-repeat,
    linear-gradient(var(--c),var(--c)) top right / 1px var(--s) no-repeat,
    linear-gradient(var(--c),var(--c)) bottom left / var(--s) 1px no-repeat,
    linear-gradient(var(--c),var(--c)) bottom left / 1px var(--s) no-repeat,
    linear-gradient(var(--c),var(--c)) bottom right / var(--s) 1px no-repeat,
    linear-gradient(var(--c),var(--c)) bottom right / 1px var(--s) no-repeat;
  opacity: .8;
}
.panel > .tag { position: absolute; top: 11px; left: 18px; font-size: 10px; letter-spacing: .3em;
  color: var(--dim); text-shadow: none; }
.panel > .tag::before { content: "■ "; color: var(--fg); text-shadow: 0 0 6px var(--glow); }
.span3 { grid-column: span 3; } .span5 { grid-column: span 5; } .span7 { grid-column: span 7; }
.span12 { grid-column: span 12; }

.big { font-size: 42px; font-weight: 300; line-height: 1; letter-spacing: -.02em; margin: 2px 0 12px; }
.big small { font-size: 11px; font-weight: 400; letter-spacing: .2em; margin-left: 6px; color: var(--dim); text-shadow: none; }
.panel.span3 > div:last-child { font-size: 11px; letter-spacing: .12em; margin-top: 4px; }
.inv { background: var(--fg); color: #000; text-shadow: none; padding: 0 4px; }
.mono { font-family: 'IBM Plex Mono', 'Menlo', monospace; font-size: 11.5px; line-height: 1.6; letter-spacing: 0; white-space: pre; }
.bar { font-family: 'Menlo', 'DejaVu Sans Mono', monospace; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 12px; }
td, th { text-align: left; padding: 6px 14px 6px 0; vertical-align: top; font-weight: 400; }
tr + tr td { border-top: 1px solid rgba(255,255,255,.04); }
th { color: var(--dim); text-shadow: none; font-size: 10px; letter-spacing: .22em; border-bottom: 1px solid var(--line); padding-top: 4px; }
.log p { margin: 0 0 9px; font-size: 12px; line-height: 1.55; padding-left: 16px; text-indent: -16px; }
.log p::before { content: "▸ "; color: var(--dim); }
.legend { color: var(--dim); text-shadow: none; font-size: 10px; letter-spacing: .14em; margin-top: 12px; }

#boot { position: fixed; inset: 0; z-index: 40; background: #000; padding: 48px; font-size: 13px; letter-spacing: .15em; line-height: 1.9; cursor: pointer; }
#boot.gone { display: none; }
footer { margin-top: 22px; padding-top: 12px; border-top: 1px solid var(--line); color: var(--dim); text-shadow: none;
  display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; font-size: 10.5px; letter-spacing: .2em; }

.span4 { grid-column: span 4; } .span8 { grid-column: span 8; }
.section { grid-column: span 12; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;
  font-size: 11px; letter-spacing: .3em; margin-top: 12px; padding-bottom: 8px; border-bottom: 1px solid var(--line); }
.section:first-child { margin-top: 0; }
.stats { display: flex; gap: 8px 26px; flex-wrap: wrap; margin-bottom: 12px; font-size: 9.5px; letter-spacing: .2em; }
.sv { font-size: 20px; font-weight: 300; letter-spacing: 0; line-height: 1.2; }
.sv small { font-size: 10px; color: var(--dim); text-shadow: none; letter-spacing: .15em; margin-left: 3px; }
.chart svg { display: block; overflow: visible; }
.chart text { font-family: 'IBM Plex Mono', monospace; font-size: 9.5px; fill: var(--dim); letter-spacing: .08em; }
.chart .g { stroke: var(--line); stroke-dasharray: 2 3; }
.chart .mk { fill: var(--fg); opacity: .85; }
.chart .mk.part { opacity: .3; }
.chart .ln { fill: none; stroke: var(--fg); stroke-width: 1.5; filter: drop-shadow(0 0 3px var(--glow)); }
.chart .dt { fill: var(--fg); }
.chart .xh { stroke: var(--fg); stroke-dasharray: 2 2; opacity: .6; }
.chart .hit { fill: transparent; cursor: crosshair; }
.tip { position: fixed; z-index: 60; display: none; pointer-events: none; background: #000; border: 1px solid var(--fg);
  padding: 6px 10px; font-size: 11px; line-height: 1.55; letter-spacing: .08em; box-shadow: 0 0 12px var(--glow); }
.rec { display: grid; grid-template-columns: 1fr auto; gap: 2px 12px; font-size: 12px; }
.rec > div { padding: 7px 0; border-top: 1px solid rgba(255,255,255,.04); }
.rec > div:nth-child(-n+2) { border-top: 0; }
.rec .v { text-align: right; }

@media (max-width: 1000px) {
  .span3, .span4 { grid-column: span 6; }
  .span5, .span7, .span8 { grid-column: span 12; }
}
@media (max-width: 720px) {
  .span3, .span4 { grid-column: span 12; }
}
@media (max-width: 560px) {
  .screen { padding: 18px 16px 28px; }
  .big { font-size: 36px; }
  .mono { font-size: 10.5px; }
}
@media (prefers-reduced-motion: reduce) {
  .screen, .blink { animation: none; }
}
</style>
</head>
<body>
<div class="screen"><div class="wrap">
  <div id="boot" title="Click to skip"></div>
  <header>
    <div>
      <h1>BIOMONITOR 6000</h1>
      <div class="sub">CREW VITALS INTERFACE // TELEMETRY LINK: GARMIN CONNECT // READ-ONLY</div>
    </div>
    <div class="phos" role="group" aria-label="Screen color">
      <span class="k">PHOSPHOR&nbsp;</span>
      <button data-p="green">P1 GRN</button>
      <button data-p="amber">P3 AMB</button>
      <button data-p="cyan">ESPER</button>
    </div>
  </header>
  <main class="grid" id="app"></main>
  <footer><span id="synced"></span><span>READY FOR INQUIRY <span class="blink">█</span></span></footer>
</div></div>
<script id="data" type="application/json">__DATA__</script>
<script>
(() => {
const D = JSON.parse(document.getElementById('data').textContent);
const keys = Object.keys(D.days || {}).sort();
const days = keys.slice(-7).map(k => D.days[k]);
const acts = Object.values(D.activities || {}).sort((a, b) => b.start_local.localeCompare(a.start_local)).slice(0, 8);
const today = new Date(); const pad = n => String(n).padStart(2, '0');
const todayIso = `${today.getFullYear()}-${pad(today.getMonth()+1)}-${pad(today.getDate())}`;
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const U = s => esc(s).toUpperCase();
const nv = v => v === null || v === undefined;

function hm(sec) {
  if (nv(sec)) return '--';
  sec = Math.round(sec); const h = Math.floor(sec / 3600), m = Math.round((sec % 3600) / 60);
  return h ? `${h}H${pad(m)}` : `${m}M`;
}
function bar(v, max, w, on = '█', off = '░') {
  const n = nv(v) ? 0 : Math.max(0, Math.min(w, Math.round(v / max * w)));
  return on.repeat(n) + off.repeat(w - n);
}
function spark(arr) {
  const b = '▁▂▃▄▅▆▇█', xs = arr.filter(x => !nv(x));
  if (!xs.length) return '';
  const lo = Math.min(...xs), hi = Math.max(...xs);
  return arr.map(x => nv(x) ? ' ' : b[hi === lo ? 3 : Math.round((x - lo) / (hi - lo) * 7)]).join('');
}
function dname(iso) {
  const d = new Date(iso + 'T12:00:00');
  return d.toLocaleDateString('en-US', { weekday: 'short' }).toUpperCase() + ' ' + iso.slice(5).replace('-', '.');
}
function delta(cur, prev, betterUp) {
  if (nv(cur) || nv(prev) || cur === prev) return '<span class="k">═ STEADY</span>';
  const up = cur > prev, good = up === betterUp, d = Math.abs(cur - prev);
  const txt = `${up ? '▲' : '▼'} ${d}`;
  return good ? txt : `<span class="inv">${txt}</span>`;
}

const L = days[days.length - 1] || {}, P = days[days.length - 2] || {};
const tr = L.training_readiness || {}, hv = L.hrv || {}, bb = L.body_battery || {};
const app = $('#app');
const panel = (cls, tag, html) => `<section class="panel ${cls}"><span class="tag">${tag}</span>${html}</section>`;
let out = '';

// ---- top readouts
const readout = (tag, val, unit, sub, d) =>
  panel('span3', tag, `<div class="big">${nv(val) ? '--' : val}<small>${unit}</small></div>
    <div class="mono bar">${sub}</div><div>${d}</div>`);
out += readout('READINESS', tr.score, '/100', bar(tr.score, 100, 20), `${U(tr.level || '')} ${delta(tr.score, (P.training_readiness||{}).score, true)}`);
out += readout('HRV', hv.last_night_avg_ms, 'MS', `BASE ${hv.baseline_low_ms ?? '--'}-${hv.baseline_high_ms ?? '--'}  ${U(hv.status || '')}`, delta(hv.last_night_avg_ms, (P.hrv||{}).last_night_avg_ms, true));
out += readout('RESTING HR', L.resting_hr, 'BPM', `7D AVG ${L.resting_hr_7day_avg ?? '--'}  ${spark(days.map(d => d.resting_hr))}`, delta(L.resting_hr, P.resting_hr, false));
out += readout('BODY BATTERY', bb.at_wake, '@WAKE', bar(bb.at_wake, 100, 20), `HI ${bb.high ?? '--'} / LO ${bb.low ?? '--'}`);

// ---- long-range telemetry: data
const DAY = 864e5;
const dn = iso => Math.round(Date.parse(iso.slice(0, 10) + 'T00:00:00Z') / DAY);
const short = n => new Date(n * DAY).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' }).toUpperCase();
const mondayOf = n => n - ((new Date(n * DAY).getUTCDay() + 6) % 7);
const pc = sec => { sec = Math.round(sec); return `${Math.floor(sec / 60)}:${pad(sec % 60)}`; };
const avgOf = xs => xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;
const runs = Object.values(D.activities || {}).filter(a => /run/.test(a.type || '') && a.start_local)
  .sort((a, b) => a.start_local.localeCompare(b.start_local));
const allDays = keys.map(k => D.days[k]);
const todayN = dn(todayIso), thisMon = mondayOf(todayN);
const firstN = Math.min(todayN, ...runs.map(a => dn(a.start_local)), ...keys.map(dn));
const weeks = [];
for (let m = mondayOf(firstN); m <= thisMon; m += 7) {
  const rs = runs.filter(a => { const n = dn(a.start_local); return n >= m && n < m + 7; });
  weeks.push({ t: m, y: Math.round(rs.reduce((s, a) => s + (a.distance_km || 0), 0) * 10) / 10, n: rs.length,
    long: Math.max(0, ...rs.map(a => a.distance_km || 0)), partial: m === thisMon });
}
const vos = runs.filter(a => !nv(a.vo2max));

// ---- long-range telemetry: panels (charts are drawn after the page is built)
out += `<div class="section"><span>LONG-RANGE TELEMETRY <span class="k">// SINCE ${short(firstN)}</span></span>
  <span class="phos" role="group" aria-label="Time range"><span class="k">RANGE&nbsp;</span>
  <button data-r="28">4W</button><button data-r="84">12W</button><button data-r="0">ALL</button></span></div>`;
const cpanel = (cls, tag, id) => panel(cls, tag, `<div class="stats" id="${id}-s"></div><div class="chart" id="${id}"></div>`);
out += cpanel('span8', 'WEEKLY RUN VOLUME // KM', 'c-wk');
out += cpanel('span4', 'VO2 MAX // RUNNING', 'c-vo');
out += cpanel('span4', 'RESTING HR // BPM', 'c-rhr');
out += cpanel('span4', 'HRV // OVERNIGHT MS', 'c-hrv');
out += cpanel('span4', 'SLEEP // HOURS', 'c-sl');

const months = {};
for (const a of runs) {
  const m = months[a.start_local.slice(0, 7)] ||= { n: 0, km: 0, sec: 0, hrw: 0, hrs: 0 };
  m.n++; m.km += a.distance_km || 0; m.sec += a.duration_seconds || 0;
  if (a.avg_hr && a.distance_km) { m.hrw += a.avg_hr * a.duration_seconds; m.hrs += a.duration_seconds; }
}
let mrows = '';
for (const k of Object.keys(months).sort().reverse()) {
  const m = months[k], dist = runs.filter(a => a.start_local.startsWith(k) && a.distance_km);
  const dsec = dist.reduce((s, a) => s + a.duration_seconds, 0), dkm = dist.reduce((s, a) => s + a.distance_km, 0);
  const lbl = new Date(k + '-15T00:00:00Z').toLocaleDateString('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' }).toUpperCase();
  mrows += `<tr><td>${lbl}${k === todayIso.slice(0, 7) ? ' <span class="k">IN PROGRESS</span>' : ''}</td><td>${m.n}</td>
    <td>${m.km.toFixed(1)}</td><td>${hm(m.sec)}</td><td>${dkm ? pc(dsec / dkm) : '--'}</td><td>${m.hrs ? Math.round(m.hrw / m.hrs) : '--'}</td></tr>`;
}
out += panel('span8', 'MONTHLY RUN LOG', runs.length ? `<div class="scroll"><table>
  <tr><th>MONTH</th><th>RUNS</th><th>KM</th><th>TIME</th><th>AVG PACE /KM</th><th>AVG HR</th></tr>${mrows}</table></div>` : '<p>NO RUNS ON FILE</p>');

const rec = [];
if (runs.length) {
  rec.push(['TOTAL DISTANCE', `${runs.reduce((s, a) => s + (a.distance_km || 0), 0).toFixed(1)} KM`, `${runs.length} RUNS`]);
  const lr = runs.reduce((b, a) => (a.distance_km || 0) > (b.distance_km || 0) ? a : b);
  rec.push(['LONGEST RUN', `${lr.distance_km} KM`, short(dn(lr.start_local))]);
  const pk = weeks.reduce((b, w) => w.y > b.y ? w : b);
  rec.push(['BIGGEST WEEK', `${pk.y} KM`, `WK OF ${short(pk.t)}`]);
  const q = runs.filter(a => a.distance_km >= 5 && a.duration_seconds);
  if (q.length) {
    const f = q.reduce((b, a) => a.duration_seconds / a.distance_km < b.duration_seconds / b.distance_km ? a : b);
    rec.push(['FASTEST PACE (5K+)', `${f.pace_per_km} /KM`, `${f.distance_km} KM · ${short(dn(f.start_local))}`]);
  }
  if (vos.length) { const b = vos.reduce((x, a) => a.vo2max > x.vo2max ? a : x); rec.push(['PEAK VO2 MAX', b.vo2max, short(dn(b.start_local))]); }
  const ld = runs.filter(a => a.training_load).reduce((x, a) => !x || a.training_load > x.training_load ? a : x, null);
  if (ld) rec.push(['HIGHEST LOAD', ld.training_load, `${U(ld.name)} · ${short(dn(ld.start_local))}`]);
}
out += panel('span4', 'RECORDS // ALL TIME', `<div class="rec">${rec.map(([k, v, n]) =>
  `<div>${k}<br><span class="k">${n}</span></div><div class="v sv">${v}</div>`).join('')}</div>`);

out += `<div class="section"><span>RECENT CYCLE <span class="k">// LAST ${days.length} DAYS</span></span></div>`;

// ---- sleep
const SMAX = 9 * 3600, SW = 36;
let sl = '';
for (const d of days) {
  const s = d.sleep || {};
  const seg = x => Math.round((x || 0) / SMAX * SW);
  let b = '█'.repeat(seg(s.deep_seconds)) + '▓'.repeat(seg(s.rem_seconds)) + '▒'.repeat(seg(s.light_seconds)) + '░'.repeat(seg(s.awake_seconds));
  b = (b + '·'.repeat(SW)).slice(0, SW);
  sl += `${dname(d.date)}  ${b}  ${hm(s.total_seconds).padStart(5)}  SCORE ${s.score ?? '--'}\n`;
}
sl += `${' '.repeat(11 + Math.round(SW * 7 / 9))}↑ 7H TARGET`;
out += panel('span7', 'SLEEP CYCLES', `<div class="mono bar scroll">${sl}</div>
  <div class="legend">█ DEEP ▓ REM ▒ LIGHT ░ AWAKE · SCALE 9H</div>`);

// ---- HRV vs baseline
let hr = '';
const hvals = days.flatMap(d => [d.hrv?.last_night_avg_ms, d.hrv?.baseline_low_ms, d.hrv?.baseline_high_ms]).filter(x => !nv(x));
const lo = Math.min(...hvals) - 5, hi = Math.max(...hvals) + 5, HW = 26;
const pos = v => Math.round((v - lo) / (hi - lo) * (HW - 1));
for (const d of days) {
  const h = d.hrv || {}; const t = Array(HW).fill('─');
  if (!nv(h.baseline_low_ms) && !nv(h.baseline_high_ms)) for (let i = pos(h.baseline_low_ms); i <= pos(h.baseline_high_ms); i++) t[i] = '═';
  if (!nv(h.last_night_avg_ms)) t[pos(h.last_night_avg_ms)] = '◆';
  hr += `${dname(d.date)}  ${t.join('')}  ${String(h.last_night_avg_ms ?? '--').padStart(3)}MS\n`;
}
out += panel('span5', 'HRV // BASELINE', hvals.length ? `<div class="mono bar scroll">${hr}</div>
  <div class="legend">═ YOUR BALANCED RANGE  ◆ LAST NIGHT</div>` : '<p>NO SIGNAL</p>');

// ---- stress + daily table
let rows = '';
for (const d of days.slice().reverse()) {
  const st = d.stress || {}, b = d.body_battery || {};
  const live = d.date === todayIso ? ' <span class="blink k">LIVE</span>' : '';
  rows += `<tr><td>${dname(d.date)}${live}</td><td>${d.training_readiness?.score ?? '--'}</td>
    <td>${st.average ?? '--'}</td><td>${hm(st.high_seconds)}</td>
    <td>${nv(b.charged) ? '--' : `+${b.charged}/-${b.drained}`}</td>
    <td>${nv(d.steps) ? '--' : d.steps.toLocaleString()}</td></tr>`;
}
out += panel('span7', 'DAILY STATUS', `<div class="scroll"><table>
  <tr><th>DAY</th><th>READY</th><th>STRESS</th><th>HI-STRESS</th><th>BATT +/-</th><th>STEPS</th></tr>${rows}</table></div>
  <div class="legend">STRESS ${spark(days.map(d => d.stress?.average))} &nbsp; BATT@WAKE ${spark(days.map(d => d.body_battery?.at_wake))}</div>`);

// ---- analysis (MOTHER)
const msgs = [];
const sleeps = days.map(d => d.sleep?.total_seconds).filter(x => !nv(x));
if (sleeps.length) {
  const avg = sleeps.reduce((a, b) => a + b, 0) / sleeps.length;
  msgs.push(avg < 7 * 3600 ? `SLEEP DEFICIT DETECTED. AVG ${hm(avg)} OVER ${sleeps.length} NIGHTS. TARGET 7H+.`
                           : `SLEEP VOLUME NOMINAL. AVG ${hm(avg)}.`);
  const ls = L.sleep || {}, prevDeep = days.slice(0, -1).map(d => d.sleep?.deep_seconds).filter(x => !nv(x));
  if (prevDeep.length && !nv(ls.deep_seconds)) {
    const pd = prevDeep.reduce((a, b) => a + b, 0) / prevDeep.length;
    if (ls.deep_seconds < pd * 0.75) msgs.push(`DEEP SLEEP LAST NIGHT ${hm(ls.deep_seconds)}, DOWN FROM ${hm(pd)} AVG.`);
  }
}
if (!nv(hv.last_night_avg_ms) && !nv(hv.baseline_low_ms)) {
  msgs.push(hv.last_night_avg_ms < hv.baseline_low_ms ? 'HRV BELOW BASELINE. RECOMMEND REDUCED LOAD.'
    : hv.last_night_avg_ms > hv.baseline_high_ms ? 'HRV ABOVE BASELINE RANGE. MONITOR.'
    : 'HRV WITHIN BASELINE. AUTONOMIC STATUS NOMINAL.');
}
const rhrs = days.map(d => d.resting_hr).filter(x => !nv(x));
if (rhrs.length > 1) {
  const dr = rhrs[rhrs.length - 1] - rhrs[0];
  msgs.push(dr < 0 ? `RESTING HR TRENDING DOWN ${-dr} BPM. FAVORABLE.` : dr > 0 ? `RESTING HR UP ${dr} BPM. WATCH FATIGUE.` : 'RESTING HR STABLE.');
}
for (const a of acts) {
  const z = a.hr_zones; if (!z) continue;
  const tot = [1,2,3,4,5].reduce((s, i) => s + (z[`z${i}_seconds`] || 0), 0);
  const hard = (z.z3_seconds || 0) + (z.z4_seconds || 0) + (z.z5_seconds || 0);
  if (/easy|recovery/i.test(a.name || '') && tot && hard / tot > 0.5)
    msgs.push(`ACTIVITY "${U(a.name)}" FLAGGED: ${Math.round(hard / tot * 100)}% OF TIME IN Z3+. EASY EFFORT EXCEEDED.`);
}
if (tr.feedback) msgs.push(`READINESS ${tr.score}: ${U(String(tr.feedback).replace(/_/g, ' '))}.`);
const fullWks = weeks.filter(w => !w.partial);
if (fullWks.length >= 2) {
  const lw = fullWks[fullWks.length - 1], prior = fullWks.slice(-5, -1), av = avgOf(prior.map(w => w.y));
  const pct = av ? Math.round((lw.y - av) / av * 100) : 0;
  msgs.push(`LAST WEEK ${lw.y} KM, ${pct >= 0 ? '+' : ''}${pct}% VS PRIOR ${prior.length}-WK AVG ${av.toFixed(1)} KM.` +
    (pct > 30 ? ' VOLUME SPIKE. MONITOR RECOVERY.' : pct < -30 ? ' DOWN WEEK.' : ''));
}
if (vos.length >= 2) {
  const lv = vos[vos.length - 1].vo2max, pv = Math.max(...vos.map(a => a.vo2max));
  msgs.push(lv < pv ? `VO2 MAX ${lv}, ${pv - lv} BELOW PEAK OF ${pv}.` : `VO2 MAX ${lv}. AT PEAK.`);
}
out += panel('span5', 'MOTHER // ANALYSIS', `<div class="log" id="log"></div>`);

// ---- mission log
const zch = ['·', '░', '▒', '▓', '█'];
let ml = '';
for (const a of acts) {
  const z = a.hr_zones; let zb = ' '.repeat(20);
  if (z) {
    const v = [1,2,3,4,5].map(i => z[`z${i}_seconds`] || 0), t = v.reduce((x, y) => x + y, 0) || 1;
    zb = (v.map((x, i) => zch[i].repeat(Math.round(x / t * 20))).join('') + ' '.repeat(20)).slice(0, 20);
  }
  const t = (a.type || '').replace(/_/g, ' ').toUpperCase();
  ml += `<tr><td>${dname(a.start_local.slice(0, 10))}</td><td>${U(a.name || t)}<br><span class="k">${esc(t)}</span></td>
    <td>${hm(a.duration_seconds)}</td><td>${nv(a.distance_km) ? '--' : a.distance_km + ' KM'}${a.pace_per_km && /run|walk|hik/.test(a.type||'') ? '<br><span class="k">' + a.pace_per_km + '/KM</span>' : ''}</td>
    <td>${a.avg_hr ? Math.round(a.avg_hr) : '--'}</td><td>${a.training_load ?? '--'}</td>
    <td>${nv(a.aerobic_te) ? '--' : a.aerobic_te + '/' + a.anaerobic_te}</td><td class="mono bar">${zb}</td></tr>`;
}
out += panel('span12', 'MISSION LOG', acts.length ? `<div class="scroll"><table>
  <tr><th>DATE</th><th>ACTIVITY</th><th>TIME</th><th>DIST</th><th>AVG HR</th><th>LOAD</th><th>TE AER/AN</th><th>HR ZONES</th></tr>${ml}</table></div>
  <div class="legend">ZONES · Z1 ░ Z2 ▒ Z3 ▓ Z4 █ Z5</div>` : '<p>NO ACTIVITY ON FILE</p>');

app.innerHTML = out;
$('#synced').textContent = `LAST TELEMETRY ${String(D.last_synced || '--').replace('T', ' ')} // ${keys.length} DAYS ON FILE`;

// ---- charts: one series each, one axis, hover crosshair + readout
const tip = document.createElement('div'); tip.className = 'tip'; document.body.appendChild(tip);
function niceStep(raw) { const p = 10 ** Math.floor(Math.log10(raw)), f = raw / p; return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p; }
function chart(el, pts, o) {
  const ys = pts.map(p => p.y).filter(v => !nv(v));
  if (!ys.length) { el.innerHTML = '<p class="k">NO SIGNAL IN RANGE</p>'; return; }
  const W = Math.max(160, el.clientWidth), H = o.h || 140, m = { l: 28, r: 4, t: 8, b: 20 };
  let lo = o.zero ? 0 : Math.min(...ys), hi = Math.max(...ys);
  if (!o.zero) { const padv = (hi - lo) * .25 || 2; lo -= padv; hi += padv; }
  const step = niceStep((hi - lo) / 3 || 1); lo = Math.floor(lo / step) * step; hi = Math.ceil(hi / step) * step || step;
  const pw = W - m.l - m.r, ph = H - m.t - m.b, slots = o.bar ? (o.t1 - o.t0) / o.bar + 1 : 0;
  const X = t => m.l + (o.bar ? ((t - o.t0) / o.bar + .5) / slots * pw : o.t1 === o.t0 ? pw / 2 : (t - o.t0) / (o.t1 - o.t0) * pw);
  const Y = v => m.t + ph - (v - lo) / (hi - lo) * ph;
  let s = `<svg width="${W}" height="${H}" role="img" aria-label="${o.label}">`;
  for (let v = lo; v <= hi + step / 2; v += step)
    s += `<line class="g" x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${m.l - 6}" y="${Y(v) + 3}" text-anchor="end">${+v.toFixed(1)}</text>`;
  if (o.bar) {
    const bw = Math.max(1, pw / slots - 2);
    for (const p of pts) if (p.y > 0) s += `<rect class="mk${p.partial ? ' part' : ''}" x="${X(p.t) - bw / 2}" y="${Y(p.y)}" width="${bw}" height="${Y(lo) - Y(p.y)}"/>`;
  } else {
    let d = '', pen = false;
    for (const p of pts) { if (nv(p.y)) { pen = false; continue; } d += `${pen ? 'L' : 'M'}${X(p.t).toFixed(1)},${Y(p.y).toFixed(1)}`; pen = true; }
    s += `<path class="ln" d="${d}"/>`;
    if (ys.length <= 60) for (const p of pts) if (!nv(p.y)) s += `<circle class="dt" cx="${X(p.t)}" cy="${Y(p.y)}" r="2.5"/>`;
  }
  const nl = Math.max(2, Math.min(5, Math.floor(pw / 85))), u = o.bar || 1;
  for (let i = 0; i < nl; i++) {
    const t = o.t0 + Math.round((o.t1 - o.t0) * i / (nl - 1) / u) * u;
    s += `<text x="${X(t)}" y="${H - 4}" text-anchor="${i === 0 ? 'start' : i === nl - 1 ? 'end' : 'middle'}">${short(t)}</text>`;
  }
  s += `<line class="xh" y1="${m.t}" y2="${m.t + ph}" x1="-99" x2="-99"/><rect class="hit" x="${m.l}" y="0" width="${pw}" height="${H}"/></svg>`;
  el.innerHTML = s;
  const svg = el.firstChild, xh = svg.querySelector('.xh'), hit = svg.querySelector('.hit');
  const valid = pts.filter(p => !nv(p.y));
  hit.onpointermove = e => {
    const r = svg.getBoundingClientRect(), mx = e.clientX - r.left;
    const best = valid.reduce((b, p) => Math.abs(X(p.t) - mx) < Math.abs(X(b.t) - mx) ? p : b);
    xh.setAttribute('x1', X(best.t)); xh.setAttribute('x2', X(best.t));
    tip.innerHTML = best.tip; tip.style.display = 'block';
    tip.style.left = Math.min(innerWidth - tip.offsetWidth - 8, e.clientX + 14) + 'px';
    tip.style.top = Math.max(8, r.top - 6) + 'px';
  };
  hit.onpointerleave = () => { tip.style.display = 'none'; xh.setAttribute('x1', -99); xh.setAttribute('x2', -99); };
}
const stats = (id, items) => $(id).innerHTML = items.map(([k, v, u]) =>
  `<div><div class="k">${k}</div><div class="sv">${nv(v) ? '--' : v}${u ? `<small>${u}</small>` : ''}</div></div>`).join('');
const r1 = v => nv(v) ? null : Math.round(v * 10) / 10;

let range = 0; try { range = +(localStorage.getItem('range') || 0); } catch (e) {}
function renderLong() {
  document.querySelectorAll('button[data-r]').forEach(b => b.setAttribute('aria-pressed', +b.dataset.r === range));
  const t0 = range ? Math.max(firstN, todayN - range + 1) : firstN;

  const wk = weeks.filter(w => w.t + 6 >= t0);
  wk.forEach(w => w.tip = `<b>WK OF ${short(w.t)}</b>${w.partial ? ' <span class="k">IN PROGRESS</span>' : ''}<br>${w.y} KM · ${w.n} RUN${w.n === 1 ? '' : 'S'}` +
    (w.n ? `<br><span class="k">LONGEST</span> ${w.long.toFixed(1)} KM` : ''));
  const full = weeks.filter(w => !w.partial);
  stats('#c-wk-s', [['THIS WEEK', weeks[weeks.length - 1].y, 'KM'], ['LAST WEEK', full.length ? full[full.length - 1].y : null, 'KM'],
    ['4-WK AVG', r1(avgOf(full.slice(-4).map(w => w.y))), 'KM/WK'], ['IN RANGE', r1(wk.reduce((s, w) => s + w.y, 0)), 'KM']]);
  chart($('#c-wk'), wk, { bar: 7, t0: wk[0].t, t1: wk[wk.length - 1].t, zero: true, h: 160, label: 'Weekly running kilometers' });

  const vo = vos.filter(a => dn(a.start_local) >= t0).map(a => ({ t: dn(a.start_local), y: a.vo2max,
    tip: `<b>${short(dn(a.start_local))}</b><br>VO2 MAX ${a.vo2max}<br><span class="k">${U(a.name)} · ${a.distance_km ?? '--'} KM</span>` }));
  stats('#c-vo-s', [['LATEST', vos.length ? vos[vos.length - 1].vo2max : null], ['PEAK', vo.length ? Math.max(...vo.map(p => p.y)) : null],
    ['CHANGE', vo.length > 1 ? (vo[vo.length - 1].y - vo[0].y >= 0 ? '+' : '') + (vo[vo.length - 1].y - vo[0].y) : null]]);
  chart($('#c-vo'), vo, { t0, t1: todayN, h: 160, label: 'VO2 max by run' });

  const ds = allDays.filter(d => dn(d.date) >= t0);
  const series = (f, fmt) => ds.map(d => ({ t: dn(d.date), y: f(d), tip: `<b>${short(dn(d.date))}</b><br>${fmt(f(d))}` }));
  const rh = series(d => d.resting_hr, v => nv(v) ? 'NO READING' : `RESTING HR ${v} BPM`), rv = rh.map(p => p.y).filter(v => !nv(v));
  stats('#c-rhr-s', [['LATEST', rv[rv.length - 1]], ['AVG', r1(avgOf(rv))], ['LOW', rv.length ? Math.min(...rv) : null]]);
  chart($('#c-rhr'), rh, { t0, t1: todayN, label: 'Resting heart rate' });

  const hv2 = series(d => d.hrv?.last_night_avg_ms, v => nv(v) ? 'NO READING' : `HRV ${v} MS`), hvv = hv2.map(p => p.y).filter(v => !nv(v));
  stats('#c-hrv-s', [['LATEST', hvv[hvv.length - 1], 'MS'], ['AVG', r1(avgOf(hvv)), 'MS'], ['HIGH', hvv.length ? Math.max(...hvv) : null, 'MS']]);
  chart($('#c-hrv'), hv2, { t0, t1: todayN, label: 'Overnight HRV' });

  const sl2 = ds.map(d => { const v = d.sleep?.total_seconds; return { t: dn(d.date), y: nv(v) ? null : r1(v / 3600),
    tip: `<b>${short(dn(d.date))}</b><br>${nv(v) ? 'NO READING' : `SLEEP ${hm(v)} · SCORE ${d.sleep.score ?? '--'}`}` }; });
  const slv = sl2.map(p => p.y).filter(v => !nv(v));
  stats('#c-sl-s', [['AVG', slv.length ? hm(avgOf(slv) * 3600) : null], ['NIGHTS 7H+', slv.length ? `${slv.filter(v => v >= 7).length}/${slv.length}` : null]]);
  chart($('#c-sl'), sl2, { bar: 1, t0, t1: todayN, zero: true, label: 'Nightly sleep hours' });
}
document.querySelectorAll('button[data-r]').forEach(b => b.onclick = () => {
  range = +b.dataset.r; try { localStorage.setItem('range', range); } catch (e) {} renderLong();
});
renderLong();
let rz; addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(renderLong, 150); });

// ---- phosphor switch
const setP = p => {
  document.documentElement.dataset.phos = p;
  document.querySelectorAll('button[data-p]').forEach(b => b.setAttribute('aria-pressed', b.dataset.p === p));
  try { localStorage.setItem('phos', p); } catch (e) {}
};
let saved = 'green'; try { saved = localStorage.getItem('phos') || 'green'; } catch (e) {}
setP(saved);
document.querySelectorAll('button[data-p]').forEach(b => b.onclick = () => setP(b.dataset.p));

// ---- boot sequence, then type out the analysis
const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
const log = $('#log');
function typeLog() {
  if (still) { log.innerHTML = msgs.map(m => `<p>${m}</p>`).join(''); return; }
  let i = 0;
  const next = () => {
    if (i >= msgs.length) return;
    const p = document.createElement('p'); log.appendChild(p);
    const txt = msgs[i++]; let j = 0;
    const t = setInterval(() => { p.textContent = txt.slice(0, ++j); if (j >= txt.length) { clearInterval(t); setTimeout(next, 250); } }, 18);
  };
  next();
}
const boot = $('#boot');
const lines = ['BIOMONITOR 6000 // COLD START', 'MEMORY CHECK ........ 640K OK', 'LINK: GARMIN CONNECT ...... OK',
  `LOADING ${keys.length} DAYS / ${Object.keys(D.activities || {}).length} ACTIVITIES`, 'DECRYPTING CREW TELEMETRY ... OK', '', 'READY FOR INQUIRY'];
let skipped = false;
const done = () => { if (skipped) return; skipped = true; boot.classList.add('gone'); typeLog(); };
boot.onclick = done; document.addEventListener('keydown', done, { once: true });
if (still) done();
else {
  let k = 0;
  const step = () => {
    if (skipped) return;
    if (k >= lines.length) return setTimeout(done, 500);
    boot.innerHTML += esc(lines[k++]) + '<br>'; setTimeout(step, 180);
  };
  boot.innerHTML = ''; step();
}
})();
</script>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--open", action="store_true", help="open the dashboard when done")
    args = ap.parse_args()

    data_path = OUT / "data.json"
    if not data_path.exists():
        print("No garmin/data.json yet. Run sync.py first.")
        return 1
    # Escape "</" so text from Garmin (e.g. activity notes) can't close the script tag.
    blob = json.dumps(json.loads(data_path.read_text())).replace("</", "<\\/")
    html_path = OUT / "dashboard.html"
    html_path.write_text(TEMPLATE.replace("__DATA__", blob))
    print(f"Dashboard written to {html_path}")
    if args.open and sys.platform == "darwin":
        subprocess.run(["open", str(html_path)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
