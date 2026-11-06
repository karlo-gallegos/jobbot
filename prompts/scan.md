Weekly scan. Follow CLAUDE.md. Get today's date with `date +%F`.

`tracker.md` is generated from `watchlist.json` after this step. Read `tracker.md`, but do not edit `tracker.md`, `watchlist.json` or `inbox.md`.

1. Read `tracker.md` to see which roles are already known.

2. Search (budget: max 25 WebSearch + 10 WebFetch in total). Two parts:
   a) Graduate schemes (about 15 searches): aggregators first – gradireland.com (IT/technology graduate jobs), Gradcracker Northern Ireland, TargetJobs and Prospects (Belfast), Bright Network (technology, Belfast/Dublin) – employer sites only to confirm a status or date. Re-check every row under "Apply now" and "Possibly open".
   b) Entry-level infrastructure jobs (about 10 searches): IrishJobs.ie, Jobs.ie, NIJobs.com, Indeed (ie / uk Belfast) and LinkedIn job results via search, plus careers pages of big Irish infra employers (AWS, Microsoft, Google and Meta data centres, Equinix, Digital Realty, CyrusOne, Intel, Dell, IBM, Version 1, Ward Solutions, BT, Openreach/NIE/Eir/Virgin Media networks, universities' research computing). Use the job titles listed in CLAUDE.md. Record the required start date and experience.

3. Write `scan_results.json`: a JSON array with one item for EVERY role you found or re-checked this run – new ones and ones already in `tracker.md` (use the same link as `tracker.md` for known roles), including roles that have closed. Each item:
   {"employer": str, "role": str, "location": str, "closing_date": "YYYY-MM-DD" (or "YYYY-MM-DDTHH:MM" if the listing states a time) or null, "date_from_board": bool (true if the date is only on a job board), "link": str, "cv_type": "infra" or "software", "kind": "grad" | "entry" (entry-level that can start June–Sept 2027, or any entry-level from 2027-03-01) | "junior_watch" (entry-level needing an immediate start), "confirmed": bool (open on the employer's own site), "closed": bool, "experience": str or null, "notes": str or null (start date, why closed, "rolling")}
   Write `[]` if none.

4. Write `new_roles.json`: a JSON array of NEW applicable roles (not already in `tracker.md`) (graduate, or entry-level startable summer 2027 – or any entry-level from 2027-03-01) closing within 21 days of today or with a rolling/unstated deadline, maximum 3, best infrastructure fit first then soonest closing. Each item:
   {"employer": str, "slug": str (letters/digits only), "role": str, "location": str, "closing_date": "YYYY-MM-DD" (or "YYYY-MM-DDTHH:MM" if the listing states a time) or null, "link": str, "cv_type": "infra" or "software", "needs_cover_letter": bool, "own_words_only": bool}
   Write `[]` if none.

5. Write `summary.txt` (max 12 lines, plain text): new roles (employer – role – closing date), new watch-list employers, anything that closed, anything needing Karlo.
