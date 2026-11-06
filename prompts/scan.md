Weekly scan. Follow CLAUDE.md. Get today's date with `date +%F`.

1. Read `inbox.md`. Apply each non-comment line to `tracker.md` (e.g. "applied X" → move X to Applied with today's date; "rejected X" / "skip X" → Skip / closed with the reason; "interview X <date>" → note in Applied). Append the processed lines with today's date to `inbox-archive.md`, then rewrite `inbox.md` keeping only its header comment lines.

2. Search (budget: max 25 WebSearch + 10 WebFetch in total). Two parts:
   a) Graduate schemes (about 15 searches): aggregators first – gradireland.com (IT/technology graduate jobs), Gradcracker Northern Ireland, TargetJobs and Prospects (Belfast), Bright Network (technology, Belfast/Dublin) – employer sites only to confirm a status or date. Re-check every row under "Apply now" and "Possibly open".
   b) Entry-level infrastructure jobs (about 10 searches): IrishJobs.ie, Jobs.ie, NIJobs.com, Indeed (ie / uk Belfast) and LinkedIn job results via search, plus careers pages of big Irish infra employers (AWS, Microsoft, Google and Meta data centres, Equinix, Digital Realty, CyrusOne, Intel, Dell, IBM, Version 1, Ward Solutions, BT, Openreach/NIE/Eir/Virgin Media networks, universities' research computing). Use the job titles listed in CLAUDE.md. Record the required start date and experience.

3. Update `tracker.md`: graduate roles under "Possibly open" (or "Apply now" if confirmed on the employer's site); entry-level roles that can start June–Sept 2027 under "Possibly open" with "(entry-level)" after the role; immediate-start entry-level roles under a section "Junior infra – watch list" (Employer | Role | Location | Experience | Link) – keep max 12 rows, newest first; move anything closed to "Skip / closed"; update the "Last checked" line.

4. Write `new_roles.json`: a JSON array of NEW applicable roles (graduate, or entry-level startable summer 2027 – or any entry-level from 2027-03-01) closing within 21 days of today or with a rolling/unstated deadline, maximum 3, best infrastructure fit first then soonest closing. Each item:
   {"employer": str, "slug": str (letters/digits only), "role": str, "location": str, "closing_date": "YYYY-MM-DD" (or "YYYY-MM-DDTHH:MM" if the listing states a time) or null, "link": str, "cv_type": "infra" or "software", "needs_cover_letter": bool, "own_words_only": bool}
   Write `[]` if none.

5. Write `summary.txt` (max 12 lines, plain text): new roles (employer – role – closing date), new watch-list employers, anything that closed, anything needing Karlo.
