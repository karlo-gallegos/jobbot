Tailor step. Follow CLAUDE.md. Read `new_roles.json` and `facts.md`.

For EACH item where own_words_only is false (max 3):

1. Read the job description: WebFetch the item's "link" (one fetch; if it is a job-board page with an "Apply"/employer link, you may make ONE more fetch of the employer's own listing). Extract only: what the team/programme does, key responsibilities, required and desirable skills/technologies, degree/eligibility, start date, application format (CV/cover letter/questions), and any rule that answers must be in the candidate's own words / no AI. If the page says that, set own_words_only to true, write nothing else for this item, and move on. Never copy sentences from the listing into Karlo's documents – paraphrase in your own words.

2. Add these fields to the item:
   - "jd_notes": 4–8 short bullet strings summarising the listing (paraphrased), each ≤20 words, plus "Source: <url>".
   - "profile": the full Profile paragraph for the CV, 70–95 words, British English, third person without pronouns, in this order:
     (a) "Final-year BSc Computer Science student at Queen's University Belfast (72% Level 2 average) with 15 months' software engineering experience at Verint" plus the ONE Verint achievement most relevant to this listing;
     (b) one sentence matching the listing's main technical needs to Karlo's strongest relevant facts (homelab/infrastructure, automation, software, data, security – whichever the job wants);
     (c) "Seeking to join <employer> as <role>…" naming one concrete thing about the team/programme from the listing.
     Use ONLY facts in facts.md. Do not claim skills the listing wants that facts.md does not support.
   - "cover_letter": ALWAYS (unless own_words_only), an array of 6 paragraph strings, 400–470 words total (must still fit one A4 page), British English, plain confident first person:
     1. The role (exact title), location, and who Karlo is.
     2. Why this employer and this programme – 2–3 specifics from the listing (paraphrased), linked to Karlo's interests.
     3. Verint evidence matched to the listing's responsibilities.
     4. Current projects – ALWAYS mention both, weighting them to the role:
        - the Linux Infrastructure & HPC Lab (two-node Debian cluster, Ansible automation, key-only SSH/Tailscale/ProxyJump, Slurm planned) and the Unraid server – lead with these for infrastructure/cloud/platform/DevOps/systems roles;
        - the TemporalGuard final-year project (detecting AI-generated/manipulated video from spatio-temporal cues; early stage – no results claimed) – lead with this for data/AI/ML/software/security roles, otherwise one sentence.
        Then, if words allow, one line of hackathon (FlowNI) or datathon evidence matched to the listing.
     5. Interests outside study (from the "Interests" section of facts.md): pick the 2–3 most relevant to this role – e.g. hardware repair, console modding and the Volvo restoration for infrastructure/hardware roles; robotics for embedded/systems roles; filmmaking for communication, teamwork under deadlines, or anything video/imaging. Say in one sentence each what the hobby shows (problem-solving, patience with fiddly diagnostics, delivering to a hard deadline as a team). Mention hospitality only if the role is customer- or client-facing.
     6. "Thank you for considering my application. …" one closing sentence about contributing to the team.
     No greeting or sign-off (the template has them). No facts outside facts.md.
   - "match_gaps": up to 3 short strings naming listing requirements Karlo does not clearly meet (so he can address them himself), or [].

3. Write the updated array back to `new_roles.json`. Change nothing else.
