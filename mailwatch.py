#!/usr/bin/env python3
"""Recruiter-email watch – part of "Remind". Cron: every 2 hours, 08:07–22:07.

1. Reads new Gmail messages over IMAP (app password in config.env). Read-only: never marks
   anything read, never sends, never deletes. Optional: adds the MAIL_LABEL Gmail label.
2. Plain-Python filter (no AI): drops job-alert / newsletter senders, keeps mail from
   application / assessment platforms, from employers in watchlist.json, from MAIL_EXTRA_SENDERS,
   or with action words in the subject. Most runs stop here and cost nothing.
3. Only if something is left: ONE `claude -p` call (MAIL_MODEL, default SCAN_MODEL) with NO
   tools turns those emails into deadlines / events / actions as JSON. Python checks every
   field (dates must parse, links must appear in the email) before keeping anything.
   If that call fails, the emails are still pinged by subject so nothing is missed.
4. Saves mail_events.json, rewrites out/deadlines.ics (watchlist.write_ics adds mail events)
   and pings ntfy. reminders.py also pings mail deadlines 3 days / 1 day / on the day.

  python3 mailwatch.py                 normal run (cron)
  python3 mailwatch.py --since 14      look back 14 days this run (ignores the saved position)
  python3 mailwatch.py --dry-run       print what it would do; save / ping / label nothing
  python3 mailwatch.py --eml DIR       read DIR/*.eml instead of IMAP (tests)
  python3 mailwatch.py --status        print "Mail watch: last OK <time>" (run.sh summary)

Any error (IMAP, revoked app password, crash) pings ntfy "Jobbot mail watch failed" – at most once
per 12 h – and is re-raised so it is in logs/mail.log. Without MAIL_USER the step is switched off.

mail_events.json = {"version": 1, "uidvalidity": int, "last_uid": int, "events": [event, ...],
                    "last_ok": "YYYY-MM-DDTHH:MM" (last successful run),
                    "last_error_ping": "YYYY-MM-DDTHH:MM" (last failure ping)}
event = {"uid": stable id, "msg": message id, "kind": "deadline" | "event" | "action" | "info",
         "employer", "title", "action", "due": "YYYY-MM-DD[THH:MM]" | null,
         "end": "YYYY-MM-DDTHH:MM" | null, "checked": bool (date found word-for-word in the email),
         "links": [urls from the email], "from", "subject", "received", "thread_url", "found",
         "outcome": "interview" | "rejected" | "offer" | null (only used to suggest an inbox line),
         "done": true once Karlo sends "done <employer> [title words]" via inbox.md}
Set JOBBOT_CLAUDE to override the claude command (tests use a stub).
"""
import argparse, datetime, email, email.policy, email.utils, fcntl, hashlib, html.parser, imaplib
import json, os, pathlib, re, subprocess, sys, time, zoneinfo
import watchlist
from reminders import config, notify

ROOT = pathlib.Path(__file__).resolve().parent
STATE = ROOT / "mail_events.json"
LOCK = ROOT / "mail_events.lock"
PROMPT = ROOT / "prompts" / "mail.md"
UK = zoneinfo.ZoneInfo("Europe/London")
MAX_EMAILS = 15        # per model call
MAX_BODY = 6000        # characters of each email sent to the model
KEEP_DAYS = 30         # drop events this long after they are due / found
KINDS = ("deadline", "event", "action", "info")
OUTCOMES = ("interview", "rejected", "offer")  # suggested as "→ log it: <outcome> <employer>"
ERROR_PING_HOURS = 12  # at most one "mail watch failed" ping this often
STALE_HOURS = 6        # run.sh summary: older last_ok = not running

# Job alerts and newsletters mention employers and "apply by" all the time – never analyse them.
NOISE = ("linkedin.com", "indeed.com", "targetjobs.co.uk", "up2staff.com", "nijobs.com",
         "jobs2web.com", "irishjobs.ie", "jobs.ie", "gradireland.com", "prospects.ac.uk",
         "gradcracker.com", "brightnetwork.co.uk", "glassdoor.com", "totaljobs.com", "reed.co.uk",
         "milkround.com", "ratemyplacement.co.uk", "openai.com", "zohocampaigns.com")
# Application-tracking, assessment and interview platforms – always worth a look.
PLATFORMS = ("myworkday.com", "myworkdayjobs.com", "candidatemanager.net", "cammio.me", "cammio.com",
             "hirevue.com", "aon-assessment.com", "cut-e.com", "shl.com", "talentlens.com",
             "pymetrics.ai", "harver.com", "tal.net", "oleeo.com", "greenhouse.io",
             "greenhouse-mail.io", "lever.co", "smartrecruiters.com", "successfactors.com",
             "successfactors.eu", "sapsf.com", "sapsf.eu", "icims.com", "taleo.net", "jobvite.com",
             "ashbyhq.com", "teamtailor.com", "workablemail.com", "workable.com", "jobtrain.co.uk",
             "beapplied.com", "codility.com", "hackerrank.com", "codesignal.com", "testgorilla.com",
             "eploy.net", "broadbean.net", "recruitee.com", "pinpointhq.com", "avature.net",
             "phenom.com", "calendly.com", "modernhire.com", "sova.co", "arctic-shores.com")
SUBJECT_WORDS = re.compile(
    r"\b(assessment|interview|invit\w*|response required|action required|reply required|deadline|"
    r"complete\w*|next steps?|offer|onboard\w*|right to work|checklist|forms?|urgent|shortlist\w*|"
    r"reminder|schedul\w*|booking|book your|slot|availability|congratulations|outcome|"
    r"your application|application (update|status|received)|video interview|online test)\b", re.I)


# ---------- state ----------
def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"version": 1, "uidvalidity": None, "last_uid": 0, "events": []}


def save_state(st):
    tmp = STATE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(st, indent=1, ensure_ascii=False) + "\n")
    os.replace(tmp, STATE)


def events():
    """Mail events for watchlist.write_ics / reminders.py (empty if the step never ran)."""
    try:
        return load_state()["events"]
    except (OSError, ValueError, KeyError):
        return []


def upcoming_alerts(today, alert_days):
    """(days, text) for deadline/event items due in one of alert_days – used by reminders.py."""
    out = []
    for e in events():
        if e["kind"] not in ("deadline", "event") or not e.get("due") or e.get("done"):
            continue
        try:
            day, at = watchlist.parse_closing(e["due"])
        except ValueError:
            continue
        days = (day - today).days
        if days in alert_days:
            when = f"{day:%a %d %b}" + (f" {at:%H:%M}" if at else "")
            verb = "due" if e["kind"] == "deadline" else "at"
            out.append((days, f"{e['title']} – {verb} {alert_days[days]} ({when})"))
    return out


def match_events(evs, name, today):
    """Open (not done, not long past) events matching '<employer> [title words]', like
    watchlist.match_roles: employer first, then words from the title. Best matches only."""
    want = watchlist._words(name)
    scored = []
    for e in evs:
        if e.get("done") or e["kind"] == "info" or (e.get("due") or "9999")[:10] < str(today - datetime.timedelta(days=1)):
            continue
        emp, title = watchlist._words(e.get("employer", "")), watchlist._words(e["title"])
        if not want:
            continue
        if emp and want[:len(emp)] == emp:
            rest = want[len(emp):]
            if rest and not set(rest) <= set(title):
                continue
            score = 10 + len(rest)
        elif " ".join(want) in " ".join(emp + title):  # e.g. "Mint" for "Mint People"
            score = 1
        else:
            continue
        scored.append((score, e))
    best = max((sc for sc, _ in scored), default=None)
    return [e for sc, e in scored if sc == best]


def mark_done(name, today, wait=30):
    """inbox.md "done <employer> [title words]". Returns (ok, message); ok is None if a mail watch
    run is active for longer than `wait` seconds – the line then stays in inbox.md for later."""
    with open(LOCK, "a") as lk:
        for _ in range(wait + 1):
            try:
                fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(1)
        else:
            return None, "mail watch is running – will retry"
        st = load_state()
        found = match_events(st["events"], name, today)
        if not found:
            return False, f"no open mail item matches {name!r}"
        if len(found) > 1:
            opts = "; ".join(e["title"] for e in found[:4])
            return False, f"{name!r} matches {len(found)} mail items ({opts}) – add words from the title"
        found[0]["done"] = True
        save_state(st)
        return True, f"done: {found[0]['title']}"


# ---------- reading mail ----------
class _Text(html.parser.HTMLParser):
    """HTML -> plain text, keeping link targets next to their text."""
    BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table", "ul", "ol"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.href, self.skip = [], None, 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script", "head"):
            self.skip += 1
        if tag in self.BLOCK:
            self.out.append("\n")
        if tag == "a":
            self.href = dict(attrs).get("href")

    def handle_endtag(self, tag):
        if tag in ("style", "script", "head"):
            self.skip = max(0, self.skip - 1)
        if tag == "a" and self.href and self.href.startswith("http"):
            self.out.append(f" <{self.href}>")
            self.href = None
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def body_text(msg):
    plain = msg.get_body(preferencelist=("plain",))
    html_part = msg.get_body(preferencelist=("html",))
    text = ""
    if plain is not None:
        text = plain.get_content()
    if html_part is not None and ("http" not in text or not text.strip()):
        p = _Text()
        p.feed(html_part.get_content())
        text = "".join(p.out)
    text = re.sub(r"[ \t ͏‌﻿]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def headers(msg):
    name, addr = email.utils.parseaddr(str(msg.get("From", "")))
    try:
        sent = email.utils.parsedate_to_datetime(str(msg.get("Date"))).astimezone(UK)
    except (TypeError, ValueError):
        sent = datetime.datetime.now(UK)
    return {"from_name": name, "from": addr.lower(), "subject": str(msg.get("Subject", "")).strip(),
            "received": sent.strftime("%Y-%m-%dT%H:%M")}


class Gmail:
    def __init__(self, cfg, write):
        self.m = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=60)
        self.m.login(cfg["MAIL_USER"], cfg["MAIL_APP_PASSWORD"].replace(" ", ""))
        folder = self._all_mail()
        typ, _ = self.m.select(folder, readonly=not write)
        if typ != "OK":
            raise SystemExit(f"cannot open {folder}")
        self.uidvalidity = int(self.m.response("UIDVALIDITY")[1][0])

    def _all_mail(self):
        # "[Gmail]/All Mail" or "[Google Mail]/All Mail" depending on the account – find it by flag.
        for line in self.m.list()[1]:
            s = line.decode(errors="replace")
            m = re.match(r'\((?P<flags>[^)]*)\) "[^"]*" (?P<name>.+)$', s)
            if m and "\\All" in m.group("flags"):
                return m.group("name")
        return '"[Gmail]/All Mail"'

    def new_uids(self, last_uid, since):
        if since:
            typ, d = self.m.uid("SEARCH", None, "SINCE", since.strftime("%d-%b-%Y"))
        else:
            typ, d = self.m.uid("SEARCH", None, f"UID {last_uid + 1}:*")
        return sorted(u for u in map(int, d[0].split()) if since or u > last_uid)

    def headers(self, uids):
        out = []
        for i in range(0, len(uids), 200):
            chunk = ",".join(map(str, uids[i:i + 200]))
            typ, data = self.m.uid("FETCH", chunk,
                                   "(UID X-GM-MSGID X-GM-THRID BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            for item in data:
                if not isinstance(item, tuple):
                    continue
                meta = item[0].decode()
                g = lambda k: re.search(rf"{k} (\d+)", meta).group(1)
                msg = email.message_from_bytes(item[1], policy=email.policy.default)
                out.append({"imap_uid": int(g("UID")), "id": g("X-GM-MSGID"),
                            "thread_url": f"https://mail.google.com/mail/u/0/#all/thread-f:{g('X-GM-THRID')}",
                            **headers(msg)})
        return out

    def body(self, item):
        typ, data = self.m.uid("FETCH", str(item["imap_uid"]), "(BODY.PEEK[])")
        raw = next(x[1] for x in data if isinstance(x, tuple))
        return body_text(email.message_from_bytes(raw, policy=email.policy.default))

    def label(self, uids, name):
        for u in uids:
            self.m.uid("STORE", str(u), "+X-GM-LABELS", f'("{name}")')

    def close(self):
        try:
            self.m.logout()
        except Exception:
            pass


class EmlDir:
    """Test mailbox: DIR/*.eml, sorted by name; uid = position."""
    uidvalidity = 1

    def __init__(self, path):
        self.files = sorted(pathlib.Path(path).glob("*.eml"))
        self.msgs = [email.message_from_bytes(f.read_bytes(), policy=email.policy.default) for f in self.files]

    def new_uids(self, last_uid, since):
        return [i + 1 for i in range(len(self.files)) if since or i + 1 > last_uid]

    def headers(self, uids):
        return [{"imap_uid": u, "id": hashlib.sha1(self.files[u - 1].name.encode()).hexdigest()[:16],
                 "thread_url": None, **headers(self.msgs[u - 1])} for u in uids]

    def body(self, item):
        return body_text(self.msgs[item["imap_uid"] - 1])

    def label(self, uids, name):
        pass

    def close(self):
        pass


# ---------- filter (no AI) ----------
def _domain_in(addr, domains):
    host = addr.rsplit("@", 1)[-1]
    return any(host == d or host.endswith("." + d) for d in domains)


def employer_names(wl):
    names = set()
    for r in wl["roles"]:
        if r.get("kind") == "junior_watch" or r.get("outcome") in ("skipped", "closed", "rejected"):
            continue
        if r["status"] in ("shortlisted", "pack_ready", "submitted", "outcome"):
            n = re.sub(r"\s*\(.*?\)", "", r.get("employer", "")).strip()
            if len(n) >= 3:
                names.add(n.lower())
    return names


def interesting(h, cfg, employers):
    """Why this email is worth analysing, or None."""
    addr = h["from"]
    me = cfg.get("MAIL_USER", "").lower()
    if not addr or addr == me:
        return None
    ignore = NOISE + tuple(d.strip().lower() for d in cfg.get("MAIL_IGNORE_SENDERS", "").split(",") if d.strip())
    if _domain_in(addr, ignore):
        return None
    extra = tuple(d.strip().lower() for d in cfg.get("MAIL_EXTRA_SENDERS", "").split(",") if d.strip())
    if _domain_in(addr, extra) or addr in extra:
        return "extra sender"
    if _domain_in(addr, PLATFORMS):
        return "platform"
    hay = f"{h['from_name']} {addr} {h['subject']}".lower()
    for n in employers:
        if re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", hay):
            return f"employer {n}"
    if SUBJECT_WORDS.search(h["subject"]):
        return "subject"
    return None


# ---------- model step ----------
def ask_model(cfg, items, today):
    payload = [{"id": i["id"], "from": f"{i['from_name']} <{i['from']}>", "subject": i["subject"],
                "sent": i["received"], "body": i["body"][:MAX_BODY]} for i in items]
    prompt = (PROMPT.read_text().replace("{TODAY}", str(today))
              + "\n<emails>\n" + json.dumps(payload, ensure_ascii=False, indent=1) + "\n</emails>\n")
    env = dict(os.environ, PATH=f"{pathlib.Path.home() / '.local/bin'}:{os.environ.get('PATH', '/usr/bin:/bin')}")
    cmd = [os.environ.get("JOBBOT_CLAUDE", "claude"), "-p",
           "--model", cfg.get("MAIL_MODEL") or cfg.get("SCAN_MODEL", "claude-haiku-5-5"),
           "--max-turns", "2", "--tools", "", "--strict-mcp-config"]  # no tools: email text is untrusted
    res = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=ROOT, env=env, timeout=600)
    if res.returncode:
        raise ValueError(f"claude exit {res.returncode}: {(res.stderr or res.stdout)[-300:].strip()}")
    out = res.stdout
    start, end = out.find("["), out.rfind("]")
    if start < 0 or end < start:
        raise ValueError("no JSON array in model output")
    data = json.loads(out[start:end + 1])
    if not isinstance(data, list):
        raise ValueError("model output is not a list")
    return data


def _squash(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().casefold()


def _clean_date(value, received):
    """Keep a model date only if it parses and is plausible for this email."""
    if not value:
        return None
    try:
        day, at = watchlist.parse_closing(str(value))
    except ValueError:
        return None
    sent = datetime.date.fromisoformat(received[:10])
    if not (sent - datetime.timedelta(days=1) <= day <= sent + datetime.timedelta(days=400)):
        return None
    return f"{day}T{at:%H:%M}" if at else str(day)


def validate(raw, items, today):
    """Model output -> clean event dicts. Anything that doesn't check out is dropped or blanked."""
    by_id = {i["id"]: i for i in items}
    out, seen = [], set()
    for r in raw:
        if not isinstance(r, dict) or not r.get("relevant") or str(r.get("id")) not in by_id:
            continue
        src = by_id[str(r["id"])]
        kind = r.get("kind") if r.get("kind") in KINDS else "action"
        due = _clean_date(r.get("due"), src["received"])
        end = _clean_date(r.get("end"), src["received"]) if kind == "event" else None
        if due and end and ("T" not in due or "T" not in end or not (due < end <= due[:11] + "23:59")):
            end = None
        if kind in ("deadline", "event") and not due:
            kind = "action"  # no usable date: still tell Karlo, just not as a calendar entry
        body = _squash(src["body"])
        ev_txt = _squash(r.get("evidence"))
        links = [l for l in (r.get("links") or []) if isinstance(l, str) and l.startswith("http")
                 and l in src["body"]][:3]  # only links that really are in the email
        title = re.sub(r"\s+", " ", str(r.get("title") or src["subject"]))[:90]
        e = {"kind": kind, "employer": str(r.get("employer") or "")[:60], "title": title,
             "action": re.sub(r"\s+", " ", str(r.get("action") or ""))[:240], "due": due, "end": end,
             "checked": bool(due and ev_txt and ev_txt in body), "links": links, "msg": src["id"],
             "from": src["from"], "subject": src["subject"][:150], "received": src["received"],
             "thread_url": src["thread_url"], "found": str(today),
             "outcome": r.get("outcome") if r.get("outcome") in OUTCOMES else None}
        e["uid"] = hashlib.sha1(f"{src['id']}|{kind}|{due}|{title.lower()}".encode()).hexdigest()[:16]
        if e["uid"] not in seen:
            seen.add(e["uid"])
            out.append(e)
    return out


# ---------- ping ----------
def _when(value):
    day, at = watchlist.parse_closing(value)
    return f"{day:%a %d %b}" + (f" {at:%H:%M}" if at else "")


def _due_dt(e):
    day, at = watchlist.parse_closing(e["due"])
    return datetime.datetime.combine(day, at or datetime.time(23, 59))


def suggest_line(e, wl):
    """The inbox.md line Karlo would send for this email ("interview SONI"), or None. Only a
    suggestion: mail never changes watchlist.json."""
    if not e.get("outcome") or not e.get("employer") or not wl:
        return None
    name = re.sub(r"\s+", " ", e["employer"]).strip()
    # Same lookup apply_line does for interview / rejected / offer, so the line will apply as is.
    found = watchlist.match_roles(wl, name, "applied")
    if len(found) != 1 or found[0].get("outcome") == e["outcome"]:
        return None  # no role, ambiguous, or already logged
    return f"{e['outcome']} {name}"


def message(new, now, wl=None):
    """ntfy text + priority + click URL for the new events (most urgent first)."""
    def rank(e):
        return (_due_dt(e) if e.get("due") else datetime.datetime.max, KINDS.index(e["kind"]))
    lines, prio, suggested = [], 2, set()
    for e in sorted(new, key=rank):
        check = "" if e["checked"] or not e.get("due") else " (check date)"
        if e["kind"] in ("deadline", "event") and e.get("due"):
            late = _due_dt(e) < now
            label = ("OVERDUE – was " if late else ("DUE " if e["kind"] == "deadline" else "")) + _when(e["due"])
            hours = (_due_dt(e) - now).total_seconds() / 3600
            prio = max(prio, 5 if late or hours <= 24 else 4 if hours <= 24 * 7 else 3)
            lines.append(f"{label}{check}: {e['title']}")
        elif e["kind"] == "action":
            prio = max(prio, 4)
            lines.append(f"TO DO (no date given): {e['title']}")
        else:
            lines.append(f"FYI: {e['title']}")
        if e["action"] and e["kind"] != "info":
            lines.append(f"  → {e['action']}")
        hint = suggest_line(e, wl)
        if hint and hint not in suggested:
            suggested.add(hint)
            lines.append(f"  → log it: {hint}")
    text = "\n".join(lines)
    if len(text.encode()) > 3800:
        text = text.encode()[:3800].decode(errors="ignore") + "\n…"
    first = sorted(new, key=rank)[0]
    return text, prio, first.get("thread_url") or (first["links"][0] if first["links"] else None)


def ping(cfg, title, text, prio, click=None):
    extra = {"Priority": str(prio), "Tags": "envelope"}
    if click:
        extra["Click"] = click
    notify(cfg, text, title, **extra)


# ---------- health ----------
def _now():
    if os.environ.get("JOBBOT_NOW"):  # tests only
        return datetime.datetime.fromisoformat(os.environ["JOBBOT_NOW"])
    return datetime.datetime.now(UK).replace(tzinfo=None)


def _stamp(t):
    return t.strftime("%Y-%m-%dT%H:%M")


def mark_ok(now):
    st = load_state()
    st["last_ok"] = _stamp(now)
    save_state(st)


def failure_alert(cfg, err, now):
    """Ping "mail watch failed" unless one was sent in the last ERROR_PING_HOURS."""
    short = re.sub(r"\s+", " ", f"{type(err).__name__}: {err}")[:200]
    try:
        st = load_state()
    except (OSError, ValueError):  # unreadable state: ping, but don't overwrite the file
        st = None
    last = (st or {}).get("last_error_ping")
    if last and now - datetime.datetime.fromisoformat(last) < datetime.timedelta(hours=ERROR_PING_HOURS):
        print(f"mail watch failed ({short}); failure ping already sent at {last}", file=sys.stderr)
        return
    if cfg.get("NTFY_TOPIC"):
        notify(cfg, f"Jobbot mail watch failed: {short}\nSee logs/mail.log", "Jobbot mail watch failed",
               Priority="high", Tags="warning")
    if st is not None:
        st["last_error_ping"] = _stamp(now)
        save_state(st)


def status(now=None):
    """One line for the run.sh summary."""
    now = now or _now()
    try:
        last = load_state().get("last_ok")
    except (OSError, ValueError):
        last = None
    if last and now - datetime.datetime.fromisoformat(last) <= datetime.timedelta(hours=STALE_HOURS):
        return f"Mail watch: last OK {last.replace('T', ' ')}"
    return f"Mail watch NOT running since {last.replace('T', ' ') if last else '(never ran OK)'}"


# ---------- main ----------
def run(args):
    now = _now()
    cfg = config()
    if not args.eml and not cfg.get("MAIL_USER"):
        print("MAIL_USER not set in config.env – mail watch is off")
        return
    try:
        check_mail(args, cfg, now)
    except BaseException as e:
        if not args.dry_run and not isinstance(e, KeyboardInterrupt):
            failure_alert(cfg, e, now)
        raise
    if not args.dry_run:
        mark_ok(now)


def check_mail(args, cfg, now):
    today = now.date()
    for k in ("NTFY_TOPIC",) + (() if args.eml else ("MAIL_USER", "MAIL_APP_PASSWORD")):
        if not cfg.get(k):
            raise SystemExit(f"{k} missing in config.env")
    st = load_state()
    label = cfg.get("MAIL_LABEL", "").strip()
    box = EmlDir(args.eml) if args.eml else Gmail(cfg, write=bool(label) and not args.dry_run)
    try:
        since = None
        if args.since is not None:
            since = today - datetime.timedelta(days=args.since)
        elif st.get("uidvalidity") != box.uidvalidity or not st.get("last_uid"):
            since = today - datetime.timedelta(days=int(cfg.get("MAIL_LOOKBACK_DAYS", "3")))
        uids = box.new_uids(st.get("last_uid", 0) if not since else 0, since)
        if not uids:
            print(f"{now:%F %H:%M}: no new mail")
            return
        heads = box.headers(uids)
        wl = watchlist.load(today)
        employers = employer_names(wl)
        known = {e["msg"] for e in st["events"]}
        picked = []
        for h in heads:
            why = interesting(h, cfg, employers)
            if why and h["id"] not in known:
                picked.append((why, h))
        print(f"{now:%F %H:%M}: {len(heads)} new, {len(picked)} to check: "
              + "; ".join(f"{h['subject'][:50]} [{w}]" for w, h in picked))
        skipped = []
        if len(picked) > MAX_EMAILS:
            skipped = [h for _, h in picked[:-MAX_EMAILS]]
            picked = picked[-MAX_EMAILS:]   # newest
        items = [dict(h, body=box.body(h)) for _, h in picked]

        new, failed = [], None
        if items and cfg.get("MAIL_MODEL", "").lower() == "none":
            failed = "MAIL_MODEL=none"
        elif items:
            try:
                new = validate(ask_model(cfg, items, today), items, today)
            except (subprocess.SubprocessError, OSError, ValueError) as e:
                failed = f"{type(e).__name__}: {e}"[:200]
                print(f"model step failed: {failed}", file=sys.stderr)
        if failed or skipped:  # never lose an email: list it by subject
            rest = items if failed else []
            rest += [dict(h, body="") for h in skipped]
            text = "\n".join(f"{i['subject'][:90]} – {i['from_name'] or i['from']}" for i in rest)
            if text and not args.dry_run:
                ping(cfg, "Jobbot mail – check these", text, 4,
                     rest[0].get("thread_url"))
            print(("Unread by model:\n" if failed else "Over the limit:\n") + text)

        old = {e["uid"] for e in st["events"]}
        new = [e for e in new if e["uid"] not in old]
        for e in new:
            print(f"  {e['kind']:<8} {e.get('due') or '-':<16} {e['title']}  ({'ok' if e['checked'] else 'unchecked'})")
        if args.dry_run:
            return

        cutoff = str(today - datetime.timedelta(days=KEEP_DAYS))
        st["events"] = [e for e in st["events"] if (e.get("due") or e["found"])[:10] >= cutoff] + new
        st["uidvalidity"] = box.uidvalidity
        st["last_uid"] = max(uids + [st.get("last_uid") or 0])
        save_state(st)
        if new:
            watchlist.write_ics(watchlist.load(today), today)
            text, prio, click = message(new, now, wl)
            ping(cfg, "Jobbot mail", text, prio, click)
            if label:
                box.label([i["imap_uid"] for i in items if i["id"] in {e["msg"] for e in new}], label)
    finally:
        box.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--since", type=int, help="look back N days this run")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--eml", help="read DIR/*.eml instead of IMAP")
    ap.add_argument("--status", action="store_true", help="print when the last run succeeded")
    args = ap.parse_args(argv)
    if args.status:
        print(status())
        return
    with open(LOCK, "w") as lk:
        try:
            fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("another mailwatch run is active")
            return
        run(args)


if __name__ == "__main__":
    main()
