#!/usr/bin/env bash
# Weekly job-search run. Cron: 31 18 * * 0 /opt/jobbot/run.sh >> /opt/jobbot/logs/cron.log 2>&1
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"
source ./config.env          # NTFY_TOPIC, SCAN_MODEL, TAILOR_MODEL, SYNC_DIR
export TODAY="$(date +%F)"
mkdir -p logs out
LOG="logs/run-$TODAY.log"
notify() { curl -fsS -H "Title: Jobbot" -d "$1" "https://ntfy.sh/$NTFY_TOPIC" >/dev/null || true; }
trap 'notify "Jobbot run failed on $TODAY – see $LOG"' ERR

echo "== $(date) scan ($SCAN_MODEL)" >> "$LOG"
echo "[]" > new_roles.json
claude -p "$(cat prompts/scan.md)" \
  --model "$SCAN_MODEL" --max-turns 60 \
  --permission-mode acceptEdits \
  --allowedTools "Read" "Edit" "Write" "WebSearch" "WebFetch" "Bash(echo:*)" "Bash(date:*)" \
  >> "$LOG" 2>&1

if [ "$(python3 -c 'import json;print(len([r for r in json.load(open("new_roles.json")) if not r.get("own_words_only")]))')" -gt 0 ]; then
  echo "== $(date) tailor ($TAILOR_MODEL)" >> "$LOG"
  claude -p "$(cat prompts/tailor.md)" \
    --model "$TAILOR_MODEL" --max-turns 25 \
    --permission-mode acceptEdits \
    --allowedTools "Read" "Edit" "Write" "WebFetch" \
    >> "$LOG" 2>&1
fi

echo "== $(date) build docs" >> "$LOG"
FILES="$(python3 build_docs.py 2>>"$LOG" | tr '\n' ' ')"

# Copy CVs/letters/.ics to the Unraid share so they appear in Finder
if [ -n "${SYNC_DIR:-}" ] && [ -d "$SYNC_DIR" ]; then
  rsync -rt out/ "$SYNC_DIR/" && cp tracker.md "$SYNC_DIR/tracker.md" || echo "sync failed" >> "$LOG"
fi

MSG="$(cat summary.txt 2>/dev/null || echo 'Scan finished.')"
[ -n "$FILES" ] && MSG="$MSG
Files in out/: $FILES"
notify "$MSG"
