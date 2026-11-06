# Jobbot update – reminders, phone shortcut, Mac sync, interview prep

## 0. Install the update (from your Mac or Fedora PC)
```bash
scp jobbot-update.tar.gz karlo@head01:~
ssh karlo@head01 'tar -xzf ~/jobbot-update.tar.gz -C /opt && chmod +x /opt/jobbot/*.sh /opt/jobbot/reminders.py'
```
Your config.env, tracker.md and inbox.md are not touched.

## 1. Daily deadline reminders (no AI)
Installed by `ansible/deploy.yml` (cron is versioned in the repo now – don't use `crontab -e`):
```
13 8 * * * /usr/bin/python3 /opt/jobbot/reminders.py >> /opt/jobbot/logs/reminders.log 2>&1
```
Every morning at 08:13 it pings your phone for anything in tracker.md closing in 3 days, tomorrow, or today.
Test now: `python3 /opt/jobbot/reminders.py` (prints "no deadlines due" or sends a ping).

## 2. Files appear on your Mac (no AI) – via an Unraid share
On Unraid: Shares → Add Share → name `jobbot` → SMB Security: Private, give your Unraid user Read/Write.
On head01:
```bash
sudo apt install -y cifs-utils rsync
sudo mkdir -p /mnt/unraid/jobbot
sudo nano /root/.smb-unraid          # two lines: username=YOURUSER  password=YOURPASS
sudo chmod 600 /root/.smb-unraid
echo '//UNRAID-IP/jobbot /mnt/unraid/jobbot cifs credentials=/root/.smb-unraid,uid=karlo,gid=karlo,iocharset=utf8,_netdev,nofail 0 0' | sudo tee -a /etc/fstab
sudo mount -a && ls /mnt/unraid/jobbot
grep -q SYNC_DIR /opt/jobbot/config.env || echo 'SYNC_DIR=/mnt/unraid/jobbot' >> /opt/jobbot/config.env
```
(Replace UNRAID-IP with your server's IP or Tailscale name.)
On the Mac: Finder → Go → Connect to Server → `smb://UNRAID-IP/jobbot` (tick "Remember"). Every run copies CVs, letters, .ics, prep packs and tracker.md there.

## 3. One-tap inbox updates from your iPhone (no AI)
Needs the Tailscale app on the iPhone, signed in to the same account.
In the Shortcuts app → + → name it "Jobbot":
1. **List** action: `applied`, `rejected`, `interview`, `skip`
2. **Choose from List** (prompt: "Update")
3. **Ask for Input** → Text, prompt: "Employer (add date for interviews)"
4. **Run Script Over SSH**
   - Host: `head01` · Port: `22` · User: `karlo`
   - Authentication: **SSH Key** → tap the key → **Share Public Key** → copy it
   - Script: `/opt/jobbot/inbox_add.sh "` [Chosen Item] ` ` [Provided Input] `"`  (insert the two variables)
5. **Show Result**

Authorise the phone's key on head01:
```bash
echo "PASTE-THE-PHONE-PUBLIC-KEY" >> ~/.ssh/authorized_keys
```
Tap the shortcut (or say "Hey Siri, Jobbot"). You get an ntfy "Noted" confirmation.

## 4. Interview prep packs (Sonnet, only when you have an interview)
Choosing **interview** in the shortcut (e.g. "TD Securities 20 Nov") immediately writes
`out/Interview_Prep_<Employer>.md`: what the programme is, 8 likely questions with which of your experiences to use (STAR outlines, not scripts), technical topics to revise, questions to ask, and anything found about their assessment format. You get a ping when it's ready.
Manual run: `/opt/jobbot/prep.sh "interview TD Securities 20 Nov"`
