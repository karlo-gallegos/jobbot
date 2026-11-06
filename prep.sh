#!/usr/bin/env bash
# Build an interview prep pack for one "interview <employer> <date>" line.
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"
source ./config.env
export INTERVIEW_LINE="$1"
mkdir -p out logs
notify() { curl -fsS -H "Title: Jobbot interview prep" -d "$1" "https://ntfy.sh/$NTFY_TOPIC" >/dev/null || true; }
trap 'notify "Interview prep failed for: $INTERVIEW_LINE – see logs/prep.log"' ERR
FILE="$(claude -p "$(cat prompts/prep.md)" \
  --model "$TAILOR_MODEL" --max-turns 20 \
  --permission-mode acceptEdits \
  --allowedTools "Read" "Write" "WebSearch" "WebFetch" "Bash(printenv:*)" | tail -n 1)"
[ -n "${SYNC_DIR:-}" ] && [ -d "$SYNC_DIR" ] && rsync -rt out/ "$SYNC_DIR/" || true
notify "Prep pack ready: $FILE"
