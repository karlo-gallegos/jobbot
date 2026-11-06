# watchlist.json – the one list

Lives at `$JOBBOT_DATA/watchlist.json` on head01 (not in git). Replaces `new_roles.json`
and the hand-edited project tracker.

```json
{
  "roles": [
    {
      "id": "cgi-tech-grad-2027",
      "employer": "CGI",
      "title": "Technical Graduate – Technology Engineer (Software, Cloud & Infrastructure) 2027",
      "location": "Belfast",
      "url": "https://…",
      "closes": "2026-11-14T23:59:00+00:00",
      "closes_verified": false,
      "status": "pack_ready",
      "outcome": null,
      "found": "2026-11-03",
      "notes": "Free-text answers in own words (CGI policy)",
      "history": [
        {"at": "2026-11-03", "status": "found"},
        {"at": "2026-11-04", "status": "shortlisted"}
      ]
    }
  ]
}
```

## Statuses
| status | meaning | set by |
|---|---|---|
| `found` | scanner saw it; not reviewed | bot |
| `shortlisted` | Karlo said yes | Karlo (via inbox_add / shortlist step) |
| `pack_ready` | CV Profile + letter built | bot |
| `submitted` | Karlo pressed Submit | Karlo |
| `outcome` | final state; detail in `outcome` field (`rejected`, `interview`, `offer`, `withdrawn`, `closed`) | Karlo |

Roles Karlo rejects at shortlist go straight to `outcome` with `"outcome": "skipped"`.

## Migration from new_roles.json
One-off script (issue to be opened): read `new_roles.json`, map each entry to `found`
(or `pack_ready` if a pack already exists in `out/`), merge by URL, then delete the old file.
