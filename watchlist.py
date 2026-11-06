#!/usr/bin/env python3
"""The one persistent role list (watchlist.json) and the tracker.md generated from it. No AI.

  python3 watchlist.py render            write tracker.md and out/deadlines.ics from watchlist.json
  python3 watchlist.py merge [FILE ...]  merge scan output by URL (default: scan_results.json
                                         new_roles.json), then write tracker.md
  python3 watchlist.py inbox             apply inbox.md lines (applied / interview / rejected /
                                         offer / withdrawn / skip / shortlist <employer> [role]
                                         [date]), move them to inbox-archive.md, write tracker.md

watchlist.json = {"version": 1, "last_scan": "YYYY-MM-DD", "roles": [role, ...]}
role = {"key": normalised link, "link", "employer", "role", "location",
        "closing_date": "YYYY-MM-DD[THH:MM]" | null, "date_from_board": bool,
        "kind": "grad" | "entry" | "junior_watch", "confirmed": bool (open on employer site),
        "status": found | shortlisted | pack_ready | submitted | outcome,
        "outcome": null | interview | offer | rejected | skipped | withdrawn | closed,
        "applied": "YYYY-MM-DD" | null, "own_words_only": bool, "experience", "notes", "slug",
        "cv_type": "infra" | "software", "needs_cover_letter": bool, "pack_attempt": "YYYY-MM-DD",
        "pack": [file names], "found", "last_seen", "history": [{"at", "status", "outcome"?, "note"?}]}

The first load without watchlist.json imports the old hand-kept tracker.md tables
(a copy is kept as tracker-pre-watchlist.md). Roles are never removed.
"""
import datetime, fcntl, hashlib, json, os, pathlib, re, shutil, sys, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent
WATCHLIST, TRACKER = ROOT / "watchlist.json", ROOT / "tracker.md"
TRACKER_BACKUP = ROOT / "tracker-pre-watchlist.md"
INBOX, INBOX_ARCHIVE = ROOT / "inbox.md", ROOT / "inbox-archive.md"
ICS = ROOT / "out" / "deadlines.ics"   # one stable feed; Apple Calendar subscribes to it
REMIND_DAYS = 4
OPEN = ("found", "shortlisted", "pack_ready")
WATCH_ROWS = 12
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
# Fields a scan / new_roles item may set or update on a role.
SCAN_FIELDS = ("employer", "role", "location", "closing_date", "date_from_board", "kind",
               "confirmed", "experience", "notes", "slug", "own_words_only", "cv_type",
               "needs_cover_letter")


# ---------- dates ----------
def parse_closing(value):
    """Return (date, time-or-None) for "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM[:SS]".
    Raises ValueError if the first 10 characters are not a date."""
    close = datetime.date.fromisoformat(value[:10])
    m = re.match(r"[T ](\d{1,2}):(\d{2})", value[10:])
    at = datetime.time(int(m.group(1)), int(m.group(2))) if m else None
    return close, at


def closing_day(role):
    try:
        return parse_closing(role["closing_date"])[0] if role.get("closing_date") else None
    except ValueError:
        return None


def parse_date(text):
    """Find a date in free text: 2026-11-14, 14 Nov 2026, 14th November 2026."""
    m = re.search(r"(20\d\d)-(\d\d)-(\d\d)", text)
    if m:
        return datetime.date(*map(int, m.groups()))
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3})[a-z]*\.?,?\s+(20\d\d)", text)
    if m and m.group(2).lower() in MONTHS:
        return datetime.date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
    return None


# ---------- keys / load / save ----------
def norm_url(url):
    u = urllib.parse.urlsplit(url.strip())
    query = urllib.parse.urlencode([(k, v) for k, v in urllib.parse.parse_qsl(u.query)
                                    if not k.lower().startswith(("utm_", "src", "source", "ref"))])
    return urllib.parse.urlunsplit(("https", u.netloc.lower().removeprefix("www."),
                                    u.path.rstrip("/"), query, ""))


def key_for(item):
    link = (item.get("link") or "").strip()
    if link.startswith("http"):
        return norm_url(link)
    return "name:" + re.sub(r"[^a-z0-9|]", "", f"{item.get('employer', '')}|{item.get('role', '')}".lower())


def load(today=None):
    if WATCHLIST.exists():
        return json.loads(WATCHLIST.read_text())
    wl = {"version": 1, "last_scan": None, "roles": []}
    if TRACKER.exists():  # one-off migration from the hand-kept tracker
        text = TRACKER.read_text()
        if not TRACKER_BACKUP.exists():
            shutil.copy2(TRACKER, TRACKER_BACKUP)
        import_tracker(wl, text, today or datetime.date.today())
        print(f"Imported {len(wl['roles'])} role(s) from tracker.md into watchlist.json", file=sys.stderr)
    save(wl)
    return wl


def save(wl):
    tmp = WATCHLIST.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(wl, indent=1, ensure_ascii=False) + "\n")
    os.replace(tmp, WATCHLIST)


def find(wl, item):
    k = key_for(item)
    return next((r for r in wl["roles"] if r["key"] == k), None)


# ---------- status changes ----------
def set_status(r, status, today, outcome=None, note=None):
    if r.get("status") == status and r.get("outcome") == outcome:
        return
    r["status"], r["outcome"] = status, outcome
    if status == "submitted" and not r.get("applied"):
        r["applied"] = str(today)
    h = {"at": str(today), "status": status}
    if outcome:
        h["outcome"] = outcome
    if note:
        h["note"] = note
    r.setdefault("history", []).append(h)


def new_role(item, today):
    r = {"key": key_for(item), "link": (item.get("link") or "").strip(), "employer": "", "role": "",
         "location": "", "closing_date": None, "date_from_board": False, "kind": "grad",
         "confirmed": False, "status": None, "outcome": None, "applied": None, "own_words_only": False,
         "experience": None, "notes": None, "slug": None, "pack": [], "found": str(today),
         "last_seen": str(today), "history": []}
    return r


def merge(wl, items, today):
    """Merge scan / new_roles items by URL. Returns (added, updated) counts."""
    added = updated = 0
    for item in items:
        if not isinstance(item, dict) or not (item.get("link") or item.get("employer")):
            continue
        r = find(wl, item)
        if r is None:
            r = new_role(item, today)
            wl["roles"].append(r)
            set_status(r, "found", today)
            added += 1
        else:
            updated += 1
        for f in SCAN_FIELDS:
            v = item.get(f)
            if v is None or v == "" or (f == "own_words_only" and not v):
                continue  # never blank out something already known; own_words_only is sticky
            if f == "role":
                v = re.sub(r"\s*\(entry-level\)\s*$", "", v)
            r[f] = v
        r["last_seen"] = str(today)
        if item.get("closed") and r["status"] in OPEN:
            set_status(r, "outcome", today, "closed", item.get("notes") or "closed (scan)")
    return added, updated


def refresh(wl, today):
    """Roles still open whose closing date has passed become outcome: closed."""
    for r in wl["roles"]:
        day = closing_day(r)
        if r["status"] in OPEN and day and day < today:
            set_status(r, "outcome", today, "closed", "closing date passed")


def record_pack(wl, item, files, today):
    """Called by build_docs.py after a tailor run for one new_roles item."""
    r = find(wl, item)
    if r is None:
        merge(wl, [item], today)
        r = find(wl, item)
    if item.get("own_words_only"):
        r["own_words_only"] = True
    if files:
        r["pack"] = sorted(set(r.get("pack") or []) | set(files))
        if r["status"] in ("found", "shortlisted"):
            set_status(r, "pack_ready", today)


# ---------- inbox.md ----------
# verb -> (status, outcome, which roles to prefer when several match)
VERBS = {
    "applied": ("submitted", None, "open"), "submitted": ("submitted", None, "open"),
    "shortlist": ("shortlisted", None, "open"), "shortlisted": ("shortlisted", None, "open"),
    "skip": ("outcome", "skipped", "open"), "skipped": ("outcome", "skipped", "open"),
    "interview": ("outcome", "interview", "applied"),
    "rejected": ("outcome", "rejected", "applied"), "reject": ("outcome", "rejected", "applied"),
    "offer": ("outcome", "offer", "applied"),
    "withdrawn": ("outcome", "withdrawn", "applied"), "withdraw": ("outcome", "withdrawn", "applied"),
}
DATE_TAIL = re.compile(r"\s+(?:on\s+)?(?:\d{4}-\d\d-\d\d|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,}\.?(?:\s+20\d\d)?"
                       r"|(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\b.*)(?:\s+(?:at\s+)?\d{1,2}[:.]\d\d)?\s*$", re.I)


def _words(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).split()


def match_roles(wl, name, prefer):
    """Best-matching roles for '<employer> [role words]'. Returns a list (empty, one, or ambiguous)."""
    want = _words(name)
    scored = []
    for r in wl["roles"]:
        emp = _words(r["employer"])
        if not emp or not want:
            continue
        if want[:len(emp)] == emp:          # starts with the employer name
            rest = want[len(emp):]
            role_words = set(_words(r["role"]))
            if rest and not set(rest) <= role_words:
                continue
            score = 10 + len(rest)
        elif " ".join(want) in " ".join(emp + _words(r["role"])):  # e.g. "TD" for "TD Securities"
            score = 1
        else:
            continue
        is_applied = bool(r.get("applied")) or r.get("outcome") in ("interview", "offer")
        if (prefer == "open" and r["status"] in OPEN) or (prefer == "applied" and is_applied):
            score += 5
        scored.append((score, r))
    if not scored:
        return []
    best = max(s for s, _ in scored)
    return [r for s, r in scored if s == best]


def apply_line(wl, line, today):
    """Apply one inbox line. Returns (done, message)."""
    verb, _, rest = line.strip().partition(" ")
    if verb.lower() not in VERBS or not rest.strip():
        return False, "not understood (start with applied / interview / rejected / offer / withdrawn / skip / shortlist)"
    status, outcome, prefer = VERBS[verb.lower()]
    name = DATE_TAIL.sub("", rest).strip()
    detail = rest[len(name):].strip()
    found = match_roles(wl, name, prefer)
    if not found and status == "submitted":  # applied to something the scan never saw
        merge(wl, [{"employer": name, "role": "", "notes": "added from inbox"}], today)
        found = [find(wl, {"employer": name, "role": ""})]
    if not found:
        return False, f"no role matches {name!r}"
    if len(found) > 1:
        opts = "; ".join(f"{r['employer']} – {r['role']}" for r in found[:4])
        return False, f"{name!r} matches {len(found)} roles ({opts}) – add words from the role title"
    r = found[0]
    note = f"{verb.lower()} {detail}".strip() if detail else None
    if status == "submitted" and r["status"] == "outcome" and r.get("outcome") in ("interview", "offer"):
        return True, f"{r['employer']} – {r['role']}: already {r['outcome']}"
    set_status(r, status, today, outcome, note or "via inbox")
    if outcome in ("interview", "offer") and not r.get("applied"):
        r["applied"] = str(today)
    if note and outcome == "interview":
        r["notes"] = "; ".join(x for x in (r.get("notes"), note) if x)
    return True, f"{r['employer']} – {r['role'] or '?'}: {outcome or status.replace('_', ' ')}"


def process_inbox(wl, today):
    """Apply inbox.md lines; move processed ones to inbox-archive.md. Lines that can't be applied
    are commented out in place with the reason. Comment (#, <!--) and blank lines stay.
    Returns a list of messages. Holds an flock on inbox.md (inbox_add.sh uses it too)."""
    if not INBOX.exists():
        return []
    msgs, keep, done = [], [], []
    with open(INBOX, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        lines = f.read().splitlines()
        for line in lines:
            if not line.strip() or line.lstrip().startswith(("#", "<!--")):
                keep.append(line)
                continue
            ok, msg = apply_line(wl, line, today)
            if ok:
                msgs.append(f"{line.strip()} → {msg}")
                done.append(f"{today} {line.strip()} → {msg}")
            else:  # commented out so it never applies itself later by elimination
                msgs.append(f"NOT APPLIED: {line.strip()} → {msg}")
                keep.append(f"# NOT APPLIED {today} – {msg}: {line.strip()}")
        if msgs:  # at least one non-comment line was handled
            save(wl)  # before the lines leave inbox.md
            if done:
                with open(INBOX_ARCHIVE, "a") as a:
                    a.write("\n".join(done) + "\n")
            f.seek(0)
            f.truncate()
            f.write("\n".join(keep) + ("\n" if keep else ""))
    return msgs


# ---------- import of the old hand-kept tracker.md ----------
def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def import_tracker(wl, text, today):
    section, header = None, None
    for line in text.splitlines():
        if line.startswith("#"):
            low = line.lower()
            header = None
            if "watch" in low or "junior" in low:
                section = "watch"
            elif "skip" in low or "closed" in low:
                section = "skip"
            elif "apply now" in low:
                section = "now"
            elif "possibly" in low:
                section = "possibly"
            elif "applied" in low:
                section = "applied"
            else:
                section = None
            continue
        if section is None or not line.lstrip().startswith("|") or set(line.strip()) <= set("|-: "):
            continue
        cells = _cells(line)
        if header is None:
            header = [c.lower() for c in cells]
            continue
        row = dict(zip(header, cells))
        get = lambda *names: next((v for k, v in row.items() if k.startswith(names)), "")
        url = next((m.group(0) for v in cells for m in [re.search(r"https?://[^\s)\]>|]+", v)] if m), "")
        employer = re.sub(r"\[([^]]*)\]\([^)]*\)", r"\1", get("employer", "company", "organisation"))
        role_txt = re.sub(r"\[([^]]*)\]\([^)]*\)", r"\1", get("role", "title", "programme", "position"))
        if not employer and not url:
            continue
        closes = get("clos", "deadline")
        day = parse_date(closes)
        used = {k for k in row if k.startswith(("employer", "company", "organisation", "role", "title",
                                                "programme", "position", "location", "clos", "deadline",
                                                "link", "url", "applied", "date", "submitted"))}
        plain = ("notes", "note", "reason", "status", "comments")  # value is enough, no "key:" prefix
        notes = "; ".join(v if k in plain else f"{k}: {v}"
                          for k, v in row.items() if k not in used and v and v not in ("-", "–"))
        item = {"employer": employer, "role": role_txt, "link": url, "location": get("location"),
                "closing_date": str(day) if day else None, "date_from_board": "board" in closes.lower(),
                "kind": "junior_watch" if section == "watch" else
                        ("entry" if "entry-level" in role_txt.lower() else "grad"),
                "confirmed": section == "now", "experience": get("experience") or None,
                "notes": notes or None}
        if find(wl, item):
            continue
        merge(wl, [item], today)
        r = find(wl, item)
        r["history"][-1]["note"] = "imported from tracker.md"
        text_all = " ".join(cells).lower()
        if section == "applied":
            set_status(r, "submitted", today)
            applied = parse_date(get("applied", "date", "submitted"))
            if applied:
                r["applied"] = str(applied)
            if "offer" in text_all:
                set_status(r, "outcome", today, "offer")
            elif "interview" in text_all:
                set_status(r, "outcome", today, "interview")
            elif "reject" in text_all or "unsuccessful" in text_all:
                set_status(r, "outcome", today, "rejected")
        elif section == "skip":
            outcome = ("rejected" if "reject" in text_all else
                       "skipped" if "skip" in text_all else "closed")
            set_status(r, "outcome", today, outcome, notes or None)


# ---------- tracker.md ----------
def _c(v):
    return str(v or "").replace("|", "/").replace("\n", " ").strip()


def _closes(r):
    day = closing_day(r)
    if not day:
        return "Rolling" if "rolling" in (r.get("notes") or "").lower() else "Not stated"
    return f"{day}" + (" (board)" if r.get("date_from_board") else "")


def _role(r):
    return _c(r["role"]) + (" (entry-level)" if r.get("kind") == "entry" else "")


def _table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(_c(x) for x in row) + " |" for row in rows]
    return out if rows else out + ["| " + " | ".join(["–"] * len(head)) + " |"]


def render(wl, today):
    roles = wl["roles"]
    applied = [r for r in roles if r.get("applied") or r.get("outcome") in ("interview", "offer")]
    is_open = lambda r: r["status"] in OPEN and r not in applied
    open_roles = sorted([r for r in roles if is_open(r) and r.get("kind") != "junior_watch"],
                        key=lambda r: (closing_day(r) or datetime.date.max, r["employer"].lower()))
    watch = sorted([r for r in roles if is_open(r) and r.get("kind") == "junior_watch"],
                   key=lambda r: r["found"], reverse=True)[:WATCH_ROWS]
    skipped = [r for r in roles if r["status"] == "outcome" and r not in applied]
    skipped.sort(key=lambda r: r["history"][-1]["at"] if r.get("history") else "", reverse=True)

    def notes(r):
        bits = (["own words only – no pack"] if r.get("own_words_only") else []) + \
               ([r["notes"]] if r.get("notes") else [])
        return "; ".join(bits)

    open_row = lambda r: [r["employer"], _role(r), r["location"], _closes(r),
                          r["status"].replace("_", " "), r["link"], notes(r)]
    open_head = ["Employer", "Role", "Location", "Closes", "Status", "Link", "Notes"]
    reason = lambda r: next((h.get("note") for h in reversed(r.get("history", [])) if h.get("note")
                             and h.get("note") != "imported from tracker.md"), "") or r.get("notes") or ""
    lines = [
        "# Job tracker", "",
        f"Generated from watchlist.json by watchlist.py on {today}. Do not edit – send updates via inbox.md.",
        f"Last checked: {wl.get('last_scan') or 'never'}", "",
        "## Applied", "",
        *_table(["Employer", "Role", "Location", "Applied", "Outcome", "Link", "Notes"],
                [[r["employer"], _role(r), r["location"], r.get("applied") or "", r.get("outcome") or "submitted",
                  r["link"], notes(r)] for r in sorted(applied, key=lambda r: r.get("applied") or "", reverse=True)]),
        "", "## Apply now", "",
        *_table(open_head, [open_row(r) for r in open_roles if r.get("confirmed")]),
        "", "## Possibly open", "",
        *_table(open_head, [open_row(r) for r in open_roles if not r.get("confirmed")]),
        "", "## Junior infra – watch list", "",
        *_table(["Employer", "Role", "Location", "Experience", "Link"],
                [[r["employer"], r["role"], r["location"], r.get("experience") or "", r["link"]] for r in watch]),
        "", "## Skip / closed", "",
        *_table(["Employer", "Role", "Outcome", "Reason", "Link"],
                [[r["employer"], _role(r), r.get("outcome") or "", reason(r), r["link"]] for r in skipped]),
        "",
    ]
    tmp = TRACKER.with_suffix(".md.tmp")
    tmp.write_text("\n".join(lines))
    os.replace(tmp, TRACKER)
    write_ics(wl, today)


# ---------- out/deadlines.ics ----------
VTIMEZONE_LONDON = [
    "BEGIN:VTIMEZONE", "TZID:Europe/London",
    "BEGIN:DAYLIGHT", "TZOFFSETFROM:+0000", "TZOFFSETTO:+0100", "TZNAME:BST",
    "DTSTART:19700329T010000", "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU", "END:DAYLIGHT",
    "BEGIN:STANDARD", "TZOFFSETFROM:+0100", "TZOFFSETTO:+0000", "TZNAME:GMT",
    "DTSTART:19701025T020000", "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU", "END:STANDARD",
    "END:VTIMEZONE",
]


def _ics_text(v):
    return str(v).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line):
    """RFC 5545: lines over 75 octets continue on the next line after a space."""
    out, cur = [], ""
    for ch in line:
        if len((cur + ch).encode()) > (75 if not out else 74):
            out.append(cur)
            cur = ""
        cur += ch
    out.append(cur)
    return "\r\n ".join(out)


def ics_events(wl, today):
    """Closing + 'apply' reminder events for every role still to apply for."""
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    noon = datetime.time(12, 0)
    events = []

    def ev(uid, start, summary, desc):
        end = start + datetime.timedelta(hours=1)
        return ["BEGIN:VEVENT", f"UID:{uid}@jobbot", f"DTSTAMP:{stamp}",
                f"DTSTART;TZID=Europe/London:{start:%Y%m%dT%H%M%S}",
                f"DTEND;TZID=Europe/London:{end:%Y%m%dT%H%M%S}",
                f"SUMMARY:{_ics_text(summary)}", f"DESCRIPTION:{_ics_text(desc)}",
                "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Reminder", "TRIGGER:-PT0M", "END:VALARM",
                "END:VEVENT"]

    for r in sorted(wl["roles"], key=lambda r: r["key"]):
        if r["status"] not in OPEN or r.get("kind") == "junior_watch" or not r.get("closing_date"):
            continue
        try:
            close, at = parse_closing(r["closing_date"])
        except ValueError:
            continue
        uid = hashlib.sha1(r["key"].encode()).hexdigest()[:16]  # stable per role, even if the date moves
        at_s = f" {at:%H:%M}" if at else ""
        if at:  # timed deadline: the event ends at the closing time
            start = datetime.datetime.combine(close, at) - datetime.timedelta(hours=1)
        else:   # date-only deadline: midday event
            start = datetime.datetime.combine(close, noon)
        board = " (date from job board)" if r.get("date_from_board") else ""
        desc = f"{r['link']}\nStatus: {r['status'].replace('_', ' ')}{board}"
        events += ev(f"{uid}-close", start, f"Closes{at_s}: {r['employer']} – {r['role']}", desc)
        remind = close - datetime.timedelta(days=REMIND_DAYS)
        if remind >= today:
            events += ev(f"{uid}-remind", datetime.datetime.combine(remind, noon),
                         f"Apply: {r['employer']} (closes {close:%a %d %b}{at_s})", desc)
    return events


def write_ics(wl, today):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//jobbot//EN", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", "X-WR-CALNAME:Jobbot deadlines", "X-WR-TIMEZONE:Europe/London",
             "REFRESH-INTERVAL;VALUE=DURATION:PT6H", "X-PUBLISHED-TTL:PT6H",
             *VTIMEZONE_LONDON, *ics_events(wl, today), "END:VCALENDAR"]
    ICS.parent.mkdir(exist_ok=True)
    tmp = ICS.with_suffix(".ics.tmp")
    tmp.write_bytes(("\r\n".join(_fold(l) for l in lines) + "\r\n").encode())
    os.chmod(tmp, 0o644)
    os.replace(tmp, ICS)


def _read_items(path):
    if not path.exists():
        return []
    data = json.loads(path.read_text() or "[]")
    if not isinstance(data, list):
        raise SystemExit(f"{path.name}: expected a JSON array")
    return data


def main(argv):
    today = datetime.date.today()
    cmd = argv[1] if len(argv) > 1 else "render"
    wl = load(today)
    if cmd == "merge":
        files = [pathlib.Path(a) for a in argv[2:]] or [ROOT / "scan_results.json", ROOT / "new_roles.json"]
        added = updated = 0
        for f in files:
            a, u = merge(wl, _read_items(f if f.is_absolute() else ROOT / f), today)
            added, updated = added + a, updated + u
        wl["last_scan"] = str(today)
        print(f"watchlist: {added} new, {updated} updated, {len(wl['roles'])} total")
    elif cmd == "inbox":
        for m in process_inbox(wl, today):
            print(m)
    elif cmd != "render":
        raise SystemExit(__doc__)
    refresh(wl, today)
    save(wl)
    render(wl, today)


if __name__ == "__main__":
    main(sys.argv)
