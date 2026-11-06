# Jobbot – scope and rules

Draft rules from the 6 Nov handover. To be merged into the CLAUDE.md that already lives in
/opt/jobbot (which the `claude -p` scan/tailor runs read), not to replace it blindly.

## Scope (fixed – do not expand)
The bot does exactly four things:
1. **Find** – scan job boards for 2027 graduate roles (island of Ireland: NI + ROI).
2. **Shortlist** – present new roles to Karlo; he decides what goes forward.
3. **Build pack** – tailored CV Profile + cover letter (+ merged PDF if a form needs one upload).
4. **Remind** – ntfy alerts and an .ics deadline feed for Apple Calendar.

Karlo does: own-words answers, pressing Submit, interviews.

Anything outside these four is a new GitHub Issue with the `later` label. Do not build it.

## Hard rules
- **Never submit an application** or sign in to an employer portal on Karlo's behalf.
- **Never write free-text application answers** (motivation questions, "why us" boxes). Some
  employers (e.g. CGI) require these in the candidate's own words; those roles are marked
  `own_words_only` and get no pack.
- Only use facts already in `base/` CVs and `facts.md`. Never invent experience, grades,
  dates or numbers. If the role needs something the CV doesn't show, list it in `match_gaps`.
- Location limits: Belfast / NI first; ROI acceptable; nothing in GB unless Karlo says so.

## Code vs data
- Git holds **code only**: the scripts, `prompts/`, `ansible/`, docs.
- `config.env`, `base/`, `facts.md`, `new_roles*.json`, `tracker.md`, `inbox*.md`, `out/`
  and `logs/` stay on head01 / NAS. They are git-ignored – never commit them.
- `/opt/jobbot` on head01 is a git checkout. Change the repo, then `git pull`
  (or `ansible/deploy.yml`). **No hand-editing files in /opt/jobbot.**

## Working style
- Small changes, one issue per change; reference the issue number in the commit.
- Test against a mock role before any live `claude -p` run.
- Keep usage low: `SCAN_MODEL` (cheap) for listings, `TAILOR_MODEL` only for packs.
