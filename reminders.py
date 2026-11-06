#!/usr/bin/env python3
"""Daily deadline reminders. Reads watchlist.json and pings ntfy 3 days, 1 day and on the day
of each closing date for roles not yet submitted (found / shortlisted / pack_ready; the junior
watch list is excluded).

Then, for up to MAX_PACKS roles per run (cron: once a day) closing within PACK_HOURS that have no pack yet, it runs the same
tailor step as retailor.sh (claude -p prompts/tailor.md, TAILOR_MODEL) on that one role via
pack_role.json – new_roles.json is left alone – then build_docs.py, and pings when it's ready.
Set JOBBOT_CLAUDE to override the claude command (tests use a stub).
Cron: 13 8 * * * /usr/bin/python3 /opt/jobbot/reminders.py >> /opt/jobbot/logs/reminders.log 2>&1"""
import datetime, json, os, pathlib, re, subprocess, sys, urllib.request
import watchlist

ROOT = pathlib.Path(__file__).resolve().parent
ALERT_DAYS = {3: "in 3 days", 1: "TOMORROW", 0: "TODAY"}
PACK_HOURS, MAX_PACKS = 36, 2
PACK_FILE = "pack_role.json"


def config():
    cfg = {}
    for line in (ROOT / "config.env").read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.split(" #")[0].strip().strip('"').strip("'")
    return cfg


def notify(cfg, msg, title, **headers):
    try:
        req = urllib.request.Request(f"https://ntfy.sh/{cfg['NTFY_TOPIC']}", data=msg.encode(),
                                     headers={"Title": title, **headers})
        urllib.request.urlopen(req, timeout=20)
    except Exception as e:  # a failed ping must not stop the pack step
        print(f"ntfy failed: {e}", file=sys.stderr)


def open_roles(wl):
    """Yield (role, closing_date, closing_time-or-None) for roles still to apply for."""
    for r in wl["roles"]:
        if r["status"] not in watchlist.OPEN or r.get("kind") == "junior_watch" or not r.get("closing_date"):
            continue
        try:
            close, at = watchlist.parse_closing(r["closing_date"])
        except ValueError:
            continue
        yield r, close, at


def due_for_pack(wl, now):
    """Roles closing within PACK_HOURS with no pack yet and not tried today, soonest first."""
    due = []
    for r, close, at in open_roles(wl):
        deadline = datetime.datetime.combine(close, at or datetime.time(23, 59))
        if (r["status"] in ("found", "shortlisted") and not r.get("own_words_only")
                and r.get("link", "").startswith("http") and r.get("pack_attempt") != str(now.date())
                and now <= deadline <= now + datetime.timedelta(hours=PACK_HOURS)):
            due.append((deadline, r))
    return [r for _, r in sorted(due, key=lambda x: x[0])][:MAX_PACKS]


def build_pack(r, cfg, today):
    """Tailor + build one role. Returns (ok, message)."""
    item = {"employer": r["employer"], "role": r["role"], "location": r.get("location", ""),
            "slug": r.get("slug") or re.sub(r"[^A-Za-z0-9]", "", r["employer"] + r["role"])[:40],
            "closing_date": r.get("closing_date"), "link": r["link"],
            "cv_type": r.get("cv_type") or "infra", "needs_cover_letter": r.get("needs_cover_letter", True),
            "own_words_only": False}
    (ROOT / PACK_FILE).write_text(json.dumps([item], indent=1, ensure_ascii=False) + "\n")
    prompt = (ROOT / "prompts" / "tailor.md").read_text().replace("new_roles.json", PACK_FILE)
    env = dict(os.environ, PATH=f"{pathlib.Path.home() / '.local/bin'}:{os.environ.get('PATH', '/usr/bin:/bin')}",
               TODAY=str(today))
    (ROOT / "logs").mkdir(exist_ok=True)
    log = ROOT / "logs" / f"pack-{today}.log"
    with open(log, "a") as lf:
        lf.write(f"== {datetime.datetime.now():%F %T} tailor {item['slug']} ({cfg.get('TAILOR_MODEL')})\n")
        lf.flush()
        try:
            # Same call as retailor.sh, on pack_role.json instead of new_roles.json.
            subprocess.run([os.environ.get("JOBBOT_CLAUDE", "claude"), "-p", prompt,
                            "--model", cfg.get("TAILOR_MODEL", "sonnet"), "--max-turns", "25",
                            "--permission-mode", "acceptEdits",
                            "--allowedTools", "Read", "Edit", "Write", "WebFetch"],
                           cwd=ROOT, env=env, stdout=lf, stderr=subprocess.STDOUT, timeout=900, check=True)
            built = subprocess.run([sys.executable, str(ROOT / "build_docs.py"), PACK_FILE], cwd=ROOT,
                                   env=env, capture_output=True, text=True, timeout=300, check=True)
            lf.write(built.stdout + built.stderr)
        except (subprocess.SubprocessError, OSError) as e:
            what = f"exit {e.returncode}" if isinstance(e, subprocess.CalledProcessError) else type(e).__name__
            lf.write(f"failed: {pathlib.Path(str(getattr(e, 'cmd', ['?'])[0])).name} {what}\n")
            return False, f"Pack failed for {r['employer']} – {r['role']} – see logs/{log.name}"
    done = json.loads((ROOT / PACK_FILE).read_text())[0]
    if done.get("own_words_only"):
        return True, f"{r['employer']} – {r['role']}: own words only – no pack, apply by hand"
    files = built.stdout.split()
    sync = cfg.get("SYNC_DIR")
    if sync and pathlib.Path(sync).is_dir():
        subprocess.run(["rsync", "-rt", f"{ROOT / 'out'}/", f"{sync}/"], check=False)
    return bool(files), (f"Pack ready: {r['employer']} – {r['role']}: {' '.join(files)}" if files
                         else f"Tailor wrote nothing for {r['employer']} – {r['role']} – see logs/{log.name}")


def main():
    now = datetime.datetime.now()
    today = now.date()
    cfg = config()
    if "NTFY_TOPIC" not in cfg:
        raise SystemExit("NTFY_TOPIC missing in config.env")
    wl = watchlist.load(today)
    for m in watchlist.process_inbox(wl, today):  # so "applied X" stops reminders the next morning
        print(m)
    watchlist.refresh(wl, today)
    watchlist.save(wl)
    watchlist.render(wl, today)

    alerts = []
    for r, close, at in open_roles(wl):
        days = (close - today).days
        if days in ALERT_DAYS:
            when = f"{close:%a %d %b}" + (f" {at:%H:%M}" if at else "")
            alerts.append(f"{r['employer']} closes {ALERT_DAYS[days]} ({when}) – {r['role']}")
    if alerts:
        notify(cfg, "\n".join(alerts), "Jobbot deadline", Priority="high", Tags="alarm_clock")
        print(f"{today}: sent {len(alerts)} reminder(s)")
    else:
        print(f"{today}: no deadlines due")

    for key in [r["key"] for r in due_for_pack(wl, now)]:
        r = next(x for x in wl["roles"] if x["key"] == key)
        r["pack_attempt"] = str(today)  # at most one try per role per day
        watchlist.save(wl)
        ok, msg = build_pack(r, cfg, today)
        print(msg)
        notify(cfg, msg, "Jobbot pack" if ok else "Jobbot pack failed")
        wl = watchlist.load(today)  # build_docs.py updated it


if __name__ == "__main__":
    main()
