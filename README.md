# jobbot

Personal graduate-job assistant on head01 (`/opt/jobbot`). It finds roles, builds a
tailored CV Profile + cover letter, and reminds me of deadlines. It never submits anything.
Scope and rules: [docs/scope.md](docs/scope.md).

## What runs
| When | What | Does |
|---|---|---|
| Sun 18:31 (cron) | `run.sh` | `claude -p prompts/scan.md` → `new_roles.json`; `claude -p prompts/tailor.md` adds Profile + letter text; `build_docs.py` writes .docx + .ics to `out/`; rsync to NAS; ntfy summary |
| daily 08:13 (cron) | `reminders.py` | reads `tracker.md`, ntfy alert 3 days / 1 day / day-of before each close |
| manual | `retailor.sh` | re-runs tailor + build on the current `new_roles.json` |
| iPhone Shortcut (SSH) | `inbox_add.sh "<update>"` | appends to `inbox.md`; `interview …` lines also run `prep.sh` |

Claude calls go through the Claude Code CLI (`claude -p`, in `~/.local/bin` for user `karlo`),
not the API SDK, so there is no API key or Python venv to manage.

## Not in git
`config.env` (from `config.env.example`), `base/` CVs + letter template, `facts.md`,
`new_roles.json`, `tracker.md`, `inbox.md`, `out/`, `logs/`.

## Deploy
```bash
cd /opt/jobbot && git pull --ff-only
# or, from anywhere with Ansible:
ansible-playbook -i 'head01,' ansible/deploy.yml
```
