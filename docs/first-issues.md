# Issues to open after the first commit

Labels: `bot` (in scope), `later` (scope creep – park it), `bug`.

1. **[bot] Merge new_roles.json into watchlist.json** – one list, statuses per docs/watchlist.md;
   one-off migration script; retailor.sh reads/writes watchlist only.
2. **[bot] Retire the hand-edited tracker** – generate a read-only markdown/HTML summary
   from watchlist.json after each run (or drop it).
3. **[bot] .ics deadline feed** – write `deadlines.ics` from watchlist (roles in
   shortlisted / pack_ready), serve it over Tailscale or publish to the NAS, subscribe in
   Apple Calendar. Alarm 48h and 12h before close.
4. **[bot] deadline_watch.py uses the same Claude call as retailor.sh** – factor the call
   into one shared helper so prompts/rules.md is the only place tailoring rules live.
5. **[bot] First live test of deadline_watch.py** – mock role closing in <36h, real API call,
   check pack + ntfy, confirm nothing is submitted.
6. **[bot] Move the Sunday scan onto a systemd timer** managed by deploy.yml (if it's still cron).
7. **[later]** anything else that comes up.
