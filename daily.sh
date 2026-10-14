#!/bin/bash
# Daily job (run by launchd): sync the last 3 days from Garmin, then rebuild the dashboard.
cd "$(dirname "$0")" || exit 1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') ====="
.venv/bin/python sync.py --days 3 && .venv/bin/python dashboard.py
echo "exit code: $?"
