#!/usr/bin/env bash
# Re-run the tailor + build steps on the current new_roles.json (e.g. after changing prompts).
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"
source ./config.env
claude -p "$(cat prompts/tailor.md)" \
  --model "$TAILOR_MODEL" --max-turns 25 \
  --permission-mode acceptEdits \
  --allowedTools "Read" "Edit" "Write" "WebFetch"
python3 build_docs.py
[ -n "${SYNC_DIR:-}" ] && [ -d "$SYNC_DIR" ] && rsync -rt out/ "$SYNC_DIR/" || true
