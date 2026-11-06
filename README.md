# Jobbot – weekly graduate job search on your own server

Every Sunday at 18:31 it:
1. applies `inbox.md` (your updates) to `watchlist.json` and regenerates `tracker.md` (plain Python; also done straight away by `inbox_add.sh` and each morning by `reminders.py`)
2. searches gradireland, Gradcracker NI, TargetJobs/Prospects and Bright Network for new 2027 tech grad roles on the island of Ireland and re-checks existing ones (**Haiku**); `watchlist.py` merges the results into `watchlist.json` by URL and regenerates `tracker.md`
3. writes a Profile sentence and, where required, a cover letter for up to 3 new roles (**Sonnet**)
4. builds tailored `.docx` CVs/letters from your own base documents (plain Python, no AI); `out/deadlines.ics` is rewritten from the whole watchlist whenever it changes
5. sends a summary to your phone via ntfy

Every morning at 08:13 `reminders.py` pings deadlines (3 days, tomorrow, today) and, for up to 2
roles closing within 36 hours that still have no pack, runs the same tailor step as `retailor.sh`
on just that role (via `pack_role.json`; **Sonnet**, so it uses your plan) and builds the CV/letter.

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
`ansible/deploy.yml` installs both cron jobs for `karlo` (Sunday 18:31 `run.sh`, daily 08:13
`reminders.py`) with `ansible.builtin.cron`, so the schedule is versioned. Change times there,
not with `crontab -e`. On the first deploy it removes the old hand-added copies of those two lines
(other crontab lines are left alone). Check with `crontab -l`.

## Seeing the files on your Mac
Easiest: put `/opt/jobbot` on an Unraid share instead (e.g. mount `//tower/jobbot` on the node with CIFS/NFS and install there), then open the share in Finder. `out/` holds the CVs, letters and `deadlines.ics`.

## Deadlines in Apple Calendar (subscribe once)
`out/deadlines.ics` is one stable feed: a "Closes" event (ending at the closing time if the listing
gives one, else midday) and an "Apply" reminder 4 days before, for every role not yet submitted.
Events update in place when a date changes and disappear once you apply or the role closes.

Serve just that file to your tailnet (not the internet – never `funnel`), once, on head01:
```bash
sudo tailscale serve --bg --set-path /jobbot/deadlines.ics /opt/jobbot/out/deadlines.ics
tailscale serve status        # shows https://head01.<tailnet>.ts.net/jobbot/deadlines.ics
```
(Needs MagicDNS + HTTPS certificates enabled in the Tailscale admin console.)
Mac: Calendar → File → New Calendar Subscription → paste the URL, refresh every hour.
iPhone: Settings → Calendar → Accounts → Add Account → Other → Add Subscribed Calendar.
Devices need Tailscale connected to refresh. Old `Grad_Deadlines_*.ics` files are no longer written;
delete any you imported into Calendar so events aren't doubled.

## Telling it about updates
Edit `inbox.md` from anywhere (Finder via the share, or SSH over Tailscale):
```
applied CGI
rejected Citi
interview TD Securities 20 Nov
skip Version 1
```
Verbs: `applied` → submitted · `interview` / `rejected` / `offer` / `withdrawn` → outcome ·
`skip` → outcome: skipped · `shortlist` → shortlisted. Then the employer name, then (if the employer
has more than one role) words from the role title, e.g. `applied CGI cloud`. A trailing date is
kept as a note. Applied lines move to `inbox-archive.md`; a line that matches no role or several
roles is commented out in `inbox.md` with the reason (`# NOT APPLIED …`) – send it again, more specific.
`applied X` for a role the scan never found adds it to the list.

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
Scope and rules (for the cron runs and for code changes): `CLAUDE.md`. Planned work: `docs/first-issues.md` / GitHub issues.
