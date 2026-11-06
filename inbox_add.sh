#!/usr/bin/env bash
# Add one update to inbox.md (used by the iPhone Shortcut over SSH).
# Usage: /opt/jobbot/inbox_add.sh "applied Thales"
#        /opt/jobbot/inbox_add.sh "interview TD Securities 20 Nov"   -> also builds a prep pack now
set -euo pipefail
cd "$(dirname "$0")"
LINE="$(printf '%s' "$*" | tr -d '\r\n' | tr -s ' ' | cut -c1-200)"
[ -z "$LINE" ] && { echo "Nothing to add"; exit 1; }
{ flock 9; echo "$LINE" >&9; } 9>>inbox.md   # same lock as watchlist.py inbox
source ./config.env
mkdir -p logs
# Apply it to watchlist.json / tracker.md now; if that fails the line stays in inbox.md for the next run.
RESULT="$(python3 watchlist.py inbox 2>>logs/inbox.log | tail -n 1 || true)"
curl -fsS -H "Title: Jobbot inbox" -d "Noted: $LINE${RESULT:+
$RESULT}" "https://ntfy.sh/$NTFY_TOPIC" >/dev/null || true
if [[ "${LINE,,}" == interview* ]]; then
  nohup ./prep.sh "$LINE" >> logs/prep.log 2>&1 &
  echo "Added. Interview prep pack is being written.${RESULT:+
$RESULT}"
else
  echo "Added: ${RESULT:-$LINE}"
fi
