# Jobbot – rules for Claude Code

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
  employers (e.g. CGI) require these in the candidate's own words. Packs cover CV Profile and
  cover letter only.
- Only use facts already in `master/cv_master.docx`. Never invent experience, grades, dates
  or numbers. If the role needs something the CV doesn't show, say so in the pack notes.
- Location limits: Belfast / NI first; ROI acceptable; nothing in GB unless Karlo says so.

## Code vs data
- Git holds **code only**: `bin/`, `prompts/`, `systemd/`, `ansible/`, docs.
- CVs, letters, `data/watchlist.json`, `out/` packs and `.env` stay on head01 / NAS.
  They are git-ignored – never commit them, never paste their contents into issues.
- `/opt/jobbot` on head01 is deployed via `ansible/deploy.yml` or `git pull`.
  **No hand-editing files in /opt/jobbot.** Change the repo, then deploy.

## One list
`data/watchlist.json` is the single source of truth for roles (schema: `docs/watchlist.md`).
Status flow: `found → shortlisted → pack_ready → submitted → outcome`.
Any human-readable tracker is generated from it, never edited by hand.

## Working style
- Small changes, one issue per change; reference the issue number in the commit.
- Test against the mock CV/template before any live Claude API call.
- Keep API usage low: cheap model for re-checking listings, stronger model only for packs.
