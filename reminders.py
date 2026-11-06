#!/usr/bin/env python3
"""Daily deadline reminders (no AI). Reads watchlist.json and pings ntfy 3 days, 1 day
and on the day of each closing date for roles not yet submitted (found / shortlisted /
pack_ready; the junior watch list is excluded).
Cron: 13 8 * * * /usr/bin/python3 /opt/jobbot/reminders.py >> /opt/jobbot/logs/reminders.log 2>&1"""
import datetime, pathlib, urllib.request
import watchlist

ROOT = pathlib.Path(__file__).resolve().parent
ALERT_DAYS = {3: "in 3 days", 1: "TOMORROW", 0: "TODAY"}


def topic():
    for line in (ROOT / "config.env").read_text().splitlines():
        if line.startswith("NTFY_TOPIC="):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("NTFY_TOPIC missing in config.env")


def open_roles(wl):
    """Yield (employer, role, closing_date, closing_time-or-None) for roles still to apply for."""
    for r in wl["roles"]:
        if r["status"] not in watchlist.OPEN or r.get("kind") == "junior_watch" or not r.get("closing_date"):
            continue
        try:
            close, at = watchlist.parse_closing(r["closing_date"])
        except ValueError:
            continue
        yield r["employer"], r["role"], close, at


def main():
    today = datetime.date.today()
    alerts = []
    wl = watchlist.load(today)
    for m in watchlist.process_inbox(wl, today):  # so "applied X" stops reminders the next morning
        print(m)
    watchlist.refresh(wl, today)
    watchlist.save(wl)
    watchlist.render(wl, today)
    for employer, role, close, at in open_roles(wl):
        days = (close - today).days
        if days in ALERT_DAYS:
            when = f"{close:%a %d %b}" + (f" {at:%H:%M}" if at else "")
            alerts.append(f"{employer} closes {ALERT_DAYS[days]} ({when}) – {role}")
    if not alerts:
        print(f"{today}: no deadlines due")
        return
    msg = "\n".join(alerts).encode()
    req = urllib.request.Request(f"https://ntfy.sh/{topic()}", data=msg,
                                 headers={"Title": "Jobbot deadline", "Priority": "high", "Tags": "alarm_clock"})
    urllib.request.urlopen(req, timeout=20)
    print(f"{today}: sent {len(alerts)} reminder(s)")


if __name__ == "__main__":
    main()
