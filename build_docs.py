#!/usr/bin/env python3
"""Turn new_roles.json into tailored CV/cover-letter .docx files, then mark those roles
pack_ready in watchlist.json and rewrite tracker.md and out/deadlines.ics.
No AI here: it only copies the base documents and swaps in text the tailor step wrote."""
import json, datetime, pathlib
import docx
import watchlist

ROOT = pathlib.Path(__file__).resolve().parent
BASE, OUT = ROOT / "base", ROOT / "out"
OUT.mkdir(exist_ok=True)

# Base CVs: (file, profile paragraph index, run index holding the text)
CV_BASES = {
    "infra": (BASE / "cv_infra.docx", 5, 0),     # copy of Karlo_Gallegos_CV_Google.docx
    "software": (BASE / "cv_software.docx", 4, 2),  # copy of Karlo Gallegos KainosCV - 2110 2026.docx
}
LETTER_BASE = BASE / "coverletter_template.docx"  # copy of KARLO_GALLEGOS_OPTIONS_COVERLETTER.docx


def set_para(p, text, run_i=0):
    p.runs[run_i].text = text
    for r in p.runs[run_i + 1:]:
        r.text = ""


def build_cv(role):
    path, idx, run_i = CV_BASES[role["cv_type"]]
    d = docx.Document(path)
    p = d.paragraphs[idx]
    old = p.text
    if not old.strip().startswith("Final-year"):
        raise SystemExit(f"Profile paragraph not found in {path.name}; base CV layout changed.")
    leading = " " if run_i else ""
    if role.get("profile"):  # full tailored Profile written from the job description
        set_para(p, f"{leading}{role['profile'].strip()}", run_i)
    else:  # older format: keep facts, swap only the final "Seeking…" sentence
        cut = old.find("Seeking")
        keep = old[:cut].strip() if cut > 0 else old.strip()
        set_para(p, f"{leading}{keep} {role['profile_sentence'].strip()}", run_i)
    out = OUT / f"Karlo_Gallegos_CV_{role['slug']}.docx"
    d.save(out)
    return out


def build_letter(role):
    d = docx.Document(LETTER_BASE)
    P = d.paragraphs
    R = P[0].runs
    R[2].text = role["employer"]
    R[4].text = "Recruitment Team…."
    # Addressee town/region lines (left column): Belfast/Northern Ireland by default
    NI = ("belfast", "derry", "londonderry", "newry", "lisburn", "armagh", "northern ireland")
    loc = role.get("location", "")
    if loc and not any(k in loc.lower() for k in NI):
        P[1].runs[0].text = loc.split("/")[0].split(",")[0].strip() + "…………...."
        P[2].runs[0].text = "Ireland"
    set_para(P[6], f"Dear {role['employer']} Recruitment Team,")
    body = role["cover_letter"][:7]
    slots = P[7:14]  # body paragraphs in the template
    for p, text in zip(slots, body):
        set_para(p, text)
    for p in slots[len(body):]:
        p._element.getparent().remove(p._element)
    out = OUT / f"KARLO_GALLEGOS_{role['slug'].upper()}_COVERLETTER.docx"
    d.save(out)
    return out


def main():
    today = datetime.date.today()
    roles = json.loads((ROOT / "new_roles.json").read_text() or "[]")
    made = []
    wl = watchlist.load(today)
    for r in roles:
        if r.get("own_words_only"):
            watchlist.record_pack(wl, r, [], today)
            continue
        first = len(made)
        if r.get("profile") or r.get("profile_sentence"):
            made.append(build_cv(r))
        if r.get("cover_letter"):
            made.append(build_letter(r))
        watchlist.record_pack(wl, r, [m.name for m in made[first:]], today)
        if r.get("jd_notes"):
            notes = OUT / f"Role_Notes_{r['slug']}.md"
            gaps = r.get("match_gaps") or []
            notes.write_text(
                f"# {r['employer']} – {r['role']}\n{r.get('location','')} · closes {r.get('closing_date') or 'not stated'}\n{r['link']}\n\n"
                "## What the listing asks for\n" + "\n".join(f"- {b}" for b in r["jd_notes"]) +
                ("\n\n## Gaps to address yourself\n" + "\n".join(f"- {g}" for g in gaps) if gaps else "") + "\n")
            made.append(notes)
    watchlist.save(wl)
    watchlist.render(wl, today)
    for m in made:
        print(m.name)


if __name__ == "__main__":
    main()
