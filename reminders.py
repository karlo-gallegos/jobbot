#!/usr/bin/env python3
"""Daily deadline reminders (no AI). Reads tracker.md and pings ntfy 3 days, 1 day
and on the day before each closing date in the 'Apply now' and 'Possibly open' tables.
Cron: 13 8 * * * /usr/bin/python3 /opt/jobbot/reminders.py >> /opt/jobbot/logs/reminders.log 2>&1"""
import datetime, pathlib, re, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
ALERT_DAYS = {3: "in 3 days", 1: "TOMORROW", 0: "TODAY"}
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def topic():
    for line in (ROOT / "config.env").read_text().splitlines():
        if line.startswith("NTFY_TOPIC="):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("NTFY_TOPIC missing in config.env")


def parse_date(text):
    m = re.search(r"(20\d\d)-(\d\d)-(\d\d)", text)
    if m:
        return datetime.date(*map(int, m.groups()))
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\.?\s+(20\d\d)", text)
    if m and m.group(2).lower() in MONTHS:
        return datetime.date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
    return None


def open_roles():
    """Yield (employer, role, closing_date) from the Apply now / Possibly open tables."""
    section, header = None, None
    for line in (ROOT / "tracker.md").read_text().splitlines():
        if line.startswith("## "):
            low = line.lower()
            section = "open" if ("apply now" in low or "possibly open" in low) else None
            header = None
            continue
        if section != "open" or not line.startswith("|") or set(line) <= set("|- "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if header is None:
            header = [c.lower() for c in cells]
            continue
        row = dict(zip(header, cells))
        close = next((parse_date(v) for k, v in row.items() if k.startswith("clos") and not v.lower().startswith(("not stated", "rolling", "unknown"))), None)
        if close:
            yield row.get("employer", "?"), row.get("role", ""), close


def main():
    today = datetime.date.today()
    alerts = []
    for employer, role, close in open_roles():
        days = (close - today).days
        if days in ALERT_DAYS:
            alerts.append(f"{employer} closes {ALERT_DAYS[days]} ({close:%a %d %b}) – {role}")
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
