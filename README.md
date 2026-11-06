# Jobbot – weekly graduate job search on your own server

Every Sunday at 18:31 it:
1. reads `inbox.md` (your updates) and updates `tracker.md`
2. searches gradireland, Gradcracker NI, TargetJobs/Prospects and Bright Network for new 2027 tech grad roles on the island of Ireland and re-checks existing ones (**Haiku**); `watchlist.py` merges the results into `watchlist.json` by URL and regenerates `tracker.md`
3. writes a Profile sentence and, where required, a cover letter for up to 3 new roles (**Sonnet**)
4. builds tailored `.docx` CVs/letters from your own base documents and a `.ics` of deadlines (plain Python, no AI)
5. sends a summary to your phone via ntfy

It never applies, signs in or submits. You do that, then add a line to `inbox.md`.

## Install (Debian 13 management node)
```bash
sudo mkdir -p /opt/jobbot && sudo chown "$USER" /opt/jobbot
tar -xzf jobbot.tar.gz -C /opt            # gives /opt/jobbot
sudo apt install -y python3-docx curl
curl -fsSL https://claude.ai/install.sh | bash    # Claude Code CLI
claude                                     # sign in once (claude.ai account), then /exit
cd /opt/jobbot && cp config.env.example config.env && nano config.env   # set NTFY_TOPIC
```
Phone: install the ntfy app and subscribe to the same topic name.

Test once by hand: `./run.sh && tail -n 40 logs/run-$(date +%F).log`

Schedule (server timezone must be Europe/London: `sudo timedatectl set-timezone Europe/London`):
```bash
crontab -e
31 18 * * 0 /opt/jobbot/run.sh >> /opt/jobbot/logs/cron.log 2>&1
```

## Seeing the files on your Mac
Easiest: put `/opt/jobbot` on an Unraid share instead (e.g. mount `//tower/jobbot` on the node with CIFS/NFS and install there), then open the share in Finder. `out/` holds the CVs, letters and .ics.

## Telling it about updates
Edit `inbox.md` from anywhere (Finder via the share, or SSH over Tailscale):
```
applied CGI
rejected Citi
interview TD Securities 20 Nov
skip Version 1
```

## Usage / cost
- Scan on Haiku and tailor on Sonnet keeps usage low; change models in `config.env`.
- Runs count against your Claude plan when signed in with your account. To keep it off your plan entirely, set `ANTHROPIC_API_KEY` in `config.env` (pay-per-use API billing) instead of signing in.
- Search budget is capped in `prompts/scan.md` (20 searches + 8 fetches).

## Check before relying on it
- CLI flags in `run.sh` (`--allowedTools`, `--permission-mode`, `--max-turns`) – if your Claude Code version differs, run `claude --help` and adjust.
- Addressee lines in generated cover letters, and every tailored Profile sentence, before you upload.
- Base documents are in `base/` (copies of your Google CV, Kainos CV and Options cover letter). Update them there when your CV changes.

## Code in git (from 6 Nov 2026)
`/opt/jobbot` is a checkout of github.com/karlo-gallegos/jobbot (read-only deploy key on head01).
The tarball install above is superseded: change code in the repo, then on head01
`cd /opt/jobbot && git pull --ff-only` (or run `ansible/deploy.yml`). Don't hand-edit tracked files.

## The role list
`watchlist.json` is the one persistent list (statuses `found → shortlisted → pack_ready →
submitted → outcome`, schema at the top of `watchlist.py`). `tracker.md` is generated from it –
don't edit it by hand. `reminders.py` reads `watchlist.json`. The first run after this change
imports the old hand-kept `tracker.md` and keeps a copy as `tracker-pre-watchlist.md`;
check the generated `tracker.md` against it once. Rebuild by hand: `python3 watchlist.py render`.

Git holds code only. `config.env`, `base/`, `facts.md`, `new_roles*.json`, `watchlist.json`, `scan_results.json`, `tracker.md`,
`inbox*.md`, `summary.txt`, `out/` and `logs/` are git-ignored and stay on head01 / NAS.
Draft scope rules: `docs/scope.md`. Planned work: `docs/first-issues.md`.
