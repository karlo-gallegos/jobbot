# Issues to open

Labels: `bot` (in scope), `later` (scope creep – park it), `bug`.
Written against what is actually on head01 on 6 Nov 2026.
Opened and fixed on 6 Nov 2026 as #1–#7 (items 0–6). Item 7 not opened yet (undecided).

0. **[bug] build_docs.py crashes on a closing date with a time.** The SONI entry has
   `"closing_date": "2026-11-06T12:00"`; `datetime.date.fromisoformat()` rejects that on
   Python 3.13, so `build_ics` raises, `run.sh` fails and ntfy says "run failed". Fix:
   parse `closing_date[:10]`, and keep the time if present for the .ics event.
1. **[bot] One persistent role list.** Today `new_roles.json` is wiped to `[]` every Sunday
   (a per-run batch), `tracker.md` is the real list (reminders.py parses its tables), and the
   claude.ai project tracker is a hand-kept copy. Add `watchlist.json` with statuses
   `found → shortlisted → pack_ready → submitted → outcome`; scan merges into it by URL;
   `tracker.md` is generated from it; `reminders.py` reads it instead of parsing markdown.
2. **[bot] inbox.md updates set statuses.** "applied X" → `submitted`, "interview X" →
   `outcome: interview`, "rejected X" → `outcome: rejected`; processed lines move to
   `inbox-archive.md`.
3. **[bot] One stable .ics feed.** `build_ics` writes a dated file each run
   (`Grad_Deadlines_YYYY-MM-DD.ics`) covering only that run's roles. Write one
   `deadlines.ics` from the whole watchlist and serve it (NAS or Tailscale) so Apple
   Calendar subscribes once and stays current.
4. **[bot] Pack for roles closing within 36h.** `deadline_watch.py` from the 6 Nov handover is
   not on head01. Either recover it, or (simpler) have `reminders.py` call the same
   `claude -p prompts/tailor.md` step `retailor.sh` uses, for one role, then `build_docs.py`.
5. **[bot] Cron in the repo.** Manage the two crontab lines with `ansible.builtin.cron`
   in `deploy.yml` so the schedule is versioned.
6. **[bot] Merge `docs/scope.md` into the live CLAUDE.md** (done; draft removed) used by the `claude -p` runs.
7. **[later] Interview prep packs (`prep.sh`)** – exists already, but interviews sit on
   Karlo's side of the scope line. Decide: keep as-is, or park.
