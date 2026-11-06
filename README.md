# jobbot

Personal graduate-job assistant running on head01. It **finds** roles, **shortlists** them
with me, **builds** a tailored CV Profile + cover letter pack, and **reminds** me of
deadlines. It never submits anything. Rules for Claude Code are in [CLAUDE.md](CLAUDE.md).

## Layout
```
bin/
  run.sh             Sunday scan of job boards → watchlist (status: found)
  retailor.sh        build packs for shortlisted roles (Claude API)
  inbox_add.sh       add a role from the iPhone Shortcut (over SSH)
  deadline_watch.py  07:30 / 18:00: build packs for roles closing within 36h, ntfy alert
prompts/rules.md     tailoring rules given to Claude
systemd/             unit templates (rendered by Ansible)
ansible/deploy.yml   the only way code reaches /opt/jobbot
docs/watchlist.md    schema + status flow for the one role list
```

Not in git (head01 / NAS only): `.env`, `data/watchlist.json`, `master/` (cv_master.docx,
letter_template.docx with `{{RECIPIENT}}`, `{{DATE}}`, `{{BODY}}`), `out/` packs.

## Deploy
```bash
# one-off on head01: deploy key for the private repo
sudo -u jobbot ssh-keygen -t ed25519 -f /home/jobbot/.ssh/jobbot_deploy -N ''
# add the .pub as a read-only Deploy Key on GitHub, then:
cp ansible/inventory.example.ini ansible/inventory.ini
ansible-playbook -i ansible/inventory.ini ansible/deploy.yml
```
Before the first deploy: create `/opt/jobbot/.env` from `.env.example` (chmod 600) and copy
the master CV and letter template into `/opt/jobbot/master/`.

## Work tracking
GitHub Issues. Anything outside find / shortlist / build / remind gets the `later` label.

## Status flow
`found → shortlisted → pack_ready → submitted → outcome`
