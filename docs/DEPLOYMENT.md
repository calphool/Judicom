# Judicom Deployment

How the working system is set up, and how to rebuild it.  The configuration files are in [`deploy/`](../deploy); passwords and family
phone numbers are **not** in git (the repository is public), so each place that needs one says where it comes from.

```text
Judi's phone number (VoIP.ms DID) --SIP--> NAS: Asterisk in Docker --Tailscale--> Judicom: baresip + judicom-phone
                                           screens callers against                  rings, shows the caller's name,
                                           judicom-allowed.conf                     dials the buttons
                                                    ^ every 10 min                          ^ every 10 min
                                           NAS: ~/judicom/contacts.txt  <-- the ONE caller list (edit only this)
                                           NAS: /mnt/8tbdrive/Photos/Judi  --every hour-->  Judicom: ~/photos
```

| Part | Where it runs | Kept in git | Kept only on the device |
|---|---|---|---|
| VoIP.ms account, DID, caller ID | voip.ms web portal | the settings, below | everything |
| Judi's caller list (master) | NAS: `/home/pi/judicom/contacts.txt` | `deploy/nas/judicom/` (the script) | the list itself |
| Family photos (master) | NAS: `/mnt/8tbdrive/Photos/Judi` (shared with Jellyfin) | | the photos and `.meta` captions |
| Asterisk (PBX) | NAS `naspi`, Docker container `asterisk-test` | `deploy/nas/asterisk/` | passwords, the two messages |
| baresip (phone line) | Judicom, service `judicom-baresip` | `deploy/judicom/` | `~/.baresip/accounts` (password) |
| The phone program | Judicom, service `judicom-phone` | `software/` | `~/contacts.txt`, `~/photos/` |

## 1. VoIP.ms (web portal)

- **Sub-account** `<account>_asterisk`: the account Asterisk registers with (server **chicago4**).
  CallerID: **Use one of my DIDs** -> Judi's number.  ("Passing its own CallerID" does not work: Asterisk sends none, and VoIP.ms
  answers every outgoing call with `503 Service Unavailable`.)
- **DID** (Judi's number, a local number where she lives): routing **SIP/IAX -> the `_asterisk` sub-account**, POP **chicago4**.
- VoIP.ms gives up on an unanswered incoming call after about **60 s** and delivers it again.  That is why the Judicom rings for
  only 40 s (`Dial(PJSIP/judicom,40)` in `judicom-inbound.conf`): Asterisk must play "Judi can't come to the phone" before that.

## 2. The NAS: Asterisk

Asterisk 22 runs in Docker (`deploy/nas/asterisk/compose.yaml`, image `andrius/asterisk:22`, host networking).  Its config folder is
`/home/pi/asterisk-test/config` on the NAS, mounted as `/etc/asterisk`.  **The NAS also runs Jellyfin**: change only this folder and
reload Asterisk's pieces; never restart Docker or the NAS for a phone change.

| File | What it does |
|---|---|
| `pjsip.conf` | two transports: home network `192.168.1.2:5060` (VoIP.ms) and Tailscale `100.64.0.1:5060` (the Judicom); includes the next two |
| `voipms.conf` | the VoIP.ms registration and endpoint; incoming calls land in context `from-voipms`.  From `voipms.conf.example` |
| `judicom.conf` | the Judicom's account (endpoint `judicom`, Tailscale only); its calls land in `from-judicom`.  From `judicom.conf.example` |
| `voipms-test.conf` | `from-judicom`: test numbers 100 (melody) and 101 (records 5 s and plays it back), and 10-digit North American numbers out through VoIP.ms (nothing else can be dialled out).  `from-voipms`: hands every call to `judicom-inbound` |
| `judicom-inbound.conf` | screening: caller on the allowed list -> the Judicom rings 40 s, then "can't come to the phone" (also when busy); anyone else, or a hidden number -> the protected-number message |
| `judicom-allowed.conf` | the allowed callers, 10 digits each.  **Written by `apply_contacts.py`** from the caller list (below): do not edit it |

`extensions.conf` is Asterisk's stock file with these lines at the end (the first was there already):

    #include "voipms-test.conf"
    #include "judicom-inbound.conf"
    #include "judicom-allowed.conf"

The two messages are `custom/judicom-protected.wav` and `custom/judicom-unavailable.wav` in the container's
`/var/lib/asterisk/sounds/custom/` (a Docker volume).  Make them with `deploy/prompts/make_prompts.sh <contact number>` (Piper
text-to-speech; the wording is in `protected.txt` / `unavailable.txt`) and copy them in with `docker cp` (the script says how).

### The housekeeping website

**http://naspi.local:8080** at home, **http://100.64.0.1:8080** over Tailscale (e.g. from a phone away from home).  Pages:
**Callers** (who may ring Judi, names, the two buttons; applied to Asterisk at once), **Events**, **Caller pictures** (any picture,
cropped square from the middle and made 800 x 800 PNG, named after the caller) and **Photos** (the slideshow: upload with a
caption, edit captions, remove).  It edits exactly the files described below, so editing them by hand still works too.

- No password (by choice).  It only answers the home network, Tailscale and the NAS itself, only under the NAS's own names and
  addresses, and every change needs the page's own form token, so a web page elsewhere cannot change the caller list.
- A list with a mistake in it (a number without its area code, two people on one button, a date it cannot read) is shown with the
  problem and not saved.  Each saved list's previous version is kept in `/home/pi/judicom/history/` (newest 30 each).
- Removed pictures are moved to `/mnt/8tbdrive/.judicom-deleted/` (`caller pictures/`, `photos/`), not erased.
- Uploaded photos bigger than 3000 pixels are shrunk (and turned upright); others are stored as they came.
- Code: `deploy/nas/admin/judicom_admin.py` (Flask + Pillow, both from Debian), run from a clone of this repository at
  `/home/pi/Judicom` by `judicom-admin.service` (as pi; `Nice=10`, `MemoryMax=400M` to stay out of Jellyfin's way).
  Install: `git clone https://github.com/calphool/Judicom.git ~/Judicom && bash ~/Judicom/deploy/nas/admin/install_admin.sh`.
  Update: `cd ~/Judicom && git pull && sudo systemctl restart judicom-admin`.  Log: `journalctl -u judicom-admin`.

**See Judicom Now** shows what the Judicom's screen is showing, looked at again every 10 seconds while the page is in view (it
stops when the tab is hidden, so an idle page costs the Judicom nothing). The NAS asks over Tailscale with its own key, which can
only run `software/tools/screen_grab.py`:

- On the NAS: `ssh-keygen -t ed25519 -N "" -C judicom-screen -f ~/.ssh/judicom_screen`, then
  `ssh-keyscan -t ed25519 100.64.0.2 >> ~/.ssh/known_hosts`.
- On the Judicom, in `/home/joe/.ssh/authorized_keys`:
  `restrict,command="/usr/bin/nice -n 10 /usr/bin/python3 /home/joe/Judicom/software/tools/screen_grab.py -" ssh-ed25519 AAAA... judicom-screen`
- On the Judicom, reading the screen needs root, so `/etc/sudoers.d/judicom-screen` (mode 440) allows that one command:
  `joe ALL=(root) NOPASSWD: /usr/bin/python3 /home/joe/Judicom/software/tools/screen_grab.py -`

### Judi's caller list

`/home/pi/judicom/contacts.txt` on the NAS is the only list to edit: same format as `software/contacts.example.txt`
(`number | name | relationship | button`).  Everyone in it may ring the Judicom; `left` / `right` put a person on a button.

- `/home/pi/judicom/apply_contacts.py` (from `deploy/nas/judicom/`) writes `judicom-allowed.conf` from it and reloads the dialplan,
  only when something changed.  `pi`'s crontab runs it every 10 minutes:
  `*/10 * * * * /usr/bin/python3 /home/pi/judicom/apply_contacts.py >/dev/null 2>&1`.  Run it by hand for an instant update;
  `--dry-run` shows what it would write.  Its log: `/home/pi/judicom/apply.log`.  The list before each change is kept as
  `judicom-allowed.conf.prev`.
- A list that cannot be read or has nobody in it changes nothing (the last good allowed list stays, and the log says why).
- The Judicom fetches the same file itself every 10 minutes (section 3), with its own key.  That key's line in
  `/home/pi/.ssh/authorized_keys` only lets it read this list and the events list (below):
  `restrict,command="/home/pi/judicom/serve_list.sh" ssh-ed25519 AAAA... judicom-contacts-sync`
  (`serve_list.sh`, from `deploy/nas/judicom/`, answers `contacts`, the default, `events`, `verses`, `people-list` or
  `people`, and refuses anything else).

### Pictures of the people

`/home/pi/judicom/people/` on the NAS: one picture per person in the caller list, named as in the list (`Frank.png`, `Ann.jpg`,
`Aunt Sue.jpg`; capitals do not matter).  The Judicom shows it in place of the handset while calling that person, talking with
them, or when they ring.  **Square, 800 x 800 pixels, head and shoulders filling most of it** (a profile picture is ideal); at least
400 x 400; .png, .jpg or .jpeg; under 5 MB.  A picture that is not square is cropped from the middle.  No picture: the handset, as
before.  The Judicom checks the folder with the caller list (every 10 minutes) and copies only what changed; removing a picture
here removes it there.  Not in the Jellyfin photo folder: the faces would turn up in the slideshow.

### Judi's events

`/home/pi/judicom/events.txt` on the NAS (start from `deploy/nas/judicom/events.example.txt`): birthdays, holidays and visits for
the Judicom's info screen, which shows the next three with a countdown ("Christmas, December 25 (52 days to go)").  One per line:
`12-25 | Christmas` (every year), `4th Thursday of November | Thanksgiving` / `last Monday of May | Memorial Day` /
`Easter | Easter` (every year, moving), or `2026-11-08 10:30 | Visit from Ann` (once; the time is optional).  It starts with the US
federal holidays and the common family ones (Easter, Mother's Day, Father's Day, Halloween, ...): delete any that are not wanted.  The Judicom fetches it with
the caller list every 10 minutes; format details at the top of `software/judicom/events.py`.
Each event on the screen gets a little cartoon chosen from words in its name (`software/judicom/event_icons.py`), and every holiday
on the list has its own: New Year's Eve -> clock at midnight, New Year's Day -> party hat, Martin Luther King Jr. -> dove,
Valentine -> heart, Presidents -> stovepipe hat, St. Patrick -> shamrock, Easter -> egg, Mother -> flower, Memorial -> poppy,
Flag -> flag, Juneteenth -> star, Father -> tie, Independence / 4th of July -> fireworks, Labor -> hammer and wrench,
Grandparents -> rocking chair, Columbus -> ship, Halloween -> pumpkin, All Saints -> candle, Veterans -> medal,
Thanksgiving -> turkey, Christmas Eve -> stocking, Christmas -> tree, Ugly Sweater -> sweater.  The family's own made-up days (Morse Code, Dog Biscuit, No Pants, ...) each have one too: the list is at the top of `event_icons.py`.  Any birthday -> cake, anniversary / wedding -> two rings,
Visit -> house; anything else a calendar page with the day on it.

### Judi's photos

`/mnt/8tbdrive/Photos/Judi` (on the 8 TB drive, shared with Jellyfin; owner `pi`, group `media`) is the master photo folder: each
picture with its `.meta` caption file (format: top of `software/judicom/photos.py`), no subfolders.  Add, change or remove pictures
there; the Judicom copies the folder every hour (section 3).  The Judicom's key can only **read** it: its line in
`/home/pi/.ssh/authorized_keys` is
`restrict,command="/usr/bin/rrsync -ro /mnt/8tbdrive/Photos/Judi" ssh-ed25519 AAAA... judicom-photo-sync`
(`rrsync` comes with rsync; `-ro`: nothing can be written or removed on the NAS through it).

**How photos get there: the mail importer.**  Family members email pictures to the family uploads Gmail address.  Every 5 minutes
the `jellyfin-mail-importer` timer (system unit, runs as `pi`) runs `/home/pi/jellyfin-mail-importer/import_photos.py`
(copy: `deploy/nas/jellyfin-mail-importer/`; its Gmail app password and Jellyfin key are in `config.env` there, not in git).  It
reads the unread emails, picks the photo folder whose name best matches the **subject** (fuzzy match; "For Judi" -> `Judi`;
no good match -> the fallback folder), saves the picture and video attachments there, deletes the email and asks Jellyfin to rescan.
For Judi's folder it also turns caption lines in the email's text into a `.meta` file next to each picture:

    people: Ann and Joe
    relationship: Your daughter and son-in-law
    taken: 2025-12-24

(Also accepted: names / who, relation, date / when; any capitals.  Only the sender's own text counts, not a quoted reply, a forwarded
message or a signature.  `CAPTION_FOLDERS` in `config.env` lists the folders that get captions; default `Judi`.)  The words are
saved as typed; the Judicom tidies them on the screen however they were written ("bryson and JOE" -> "Bryson and Joe",
"great-grandson" -> "Your great-grandson", "10/24/2026" -> "October 24, 2026"; rules at the top of `software/judicom/photos.py`).  The Judicom shows
.jpg, .png and .bmp only: an iPhone `.heic` is saved (and Jellyfin shows it) but not on the Judicom.
Log: `journalctl -u jellyfin-mail-importer`.

### Judi's verses

`/home/pi/judicom/verses.txt` on the NAS (start from `deploy/nas/judicom/verses.example.txt`: 50 comforting KJV verses, their
words taken from a public-domain KJV text): `reference | words`, one per line, `[2]` where verse 2 begins inside a passage.  The
Judicom fetches it with the caller list every 10 minutes and shows one verse, on a page that looks like an old Bible, every other
time the info screen would come (so after every 10 photos), for 30 seconds; every verse once before any comes again.

### The offline alert

`/home/pi/judicom/watch_judicom.py` (from `deploy/nas/judicom/`; `pi`'s crontab, every 5 minutes) checks that the Judicom is
registered with Asterisk, and that Asterisk answers.  It emails when the Judicom has been offline for 30 minutes, then once a day
at about 9 am while it stays offline, and once when it is back (with how long it was gone).  Short blips send nothing.
- Settings: `/home/pi/judicom/watch.env` (not in git): `ALERT_TO=` (who gets it), `DELAY_MINUTES=30`, `REMINDER_HOUR=9`
  (empty: no daily reminders).
- Sent through the mail importer's Gmail account (its `config.env`; read, not copied).
- `python3 ~/judicom/watch_judicom.py --status` (what it sees now), `--test` (send a test email); log `~/judicom/watch.log`.
- It cannot tell when only the phone program on the Judicom has crashed while baresip still runs (systemd restarts it anyway).

On the Judicom itself: while baresip is not running or not registered with the PBX (no network, Tailscale down, NAS or Asterisk
down), a button does not dial; the screen says "The phone is not working.  It is being fixed." for 15 seconds (`OUT_OF_ORDER_SECONDS`).  baresip notices a lost PBX at its next registration, within about 1.5
minutes (`regint=60` plus the 32 s SIP timeout); a call tried before that may still end in "No answer.".
Callers meanwhile hear the "not available" message from the PBX.  It is back to normal by itself once baresip registers again.

### Call history

Asterisk writes one line per call (and per leg of a call) to `/var/log/asterisk/cdr-csv/Master.csv` in the container (a Docker
volume, so it survives restarts): who called whom, when, how long it rang and was talked, and how it ended (`ANSWERED`,
`NO ANSWER`, `BUSY`, ...).  Times are **UTC** (the container's clock; US Central time is 6 hours behind, 5 in summer).  It holds phone
numbers: it stays on the NAS.  The folder was made by hand on 2026-11-03 (before that every call logged a harmless
"Unable to open file ... Master.csv" error):

    docker exec asterisk-test tail -20 /var/log/asterisk/cdr-csv/Master.csv
    # if the volume is ever made new:  docker exec asterisk-test sh -c "mkdir -p /var/log/asterisk/cdr-csv && chown asterisk:asterisk /var/log/asterisk/cdr-csv"

### Applying a change (safe: no restart, no dropped registrations)

Back up the file first (`cp -p x.conf x.conf.before-<what>-<date>`), edit, then:

    docker exec asterisk-test asterisk -rx "dialplan reload"        # extensions*.conf, voipms-test.conf, judicom-*.conf
    docker exec asterisk-test asterisk -rx "module reload res_pjsip.so"   # only for pjsip.conf / voipms.conf / judicom.conf

### Checks

    docker exec asterisk-test asterisk -rx "pjsip show registrations"   # voipms ... Registered
    docker exec asterisk-test asterisk -rx "pjsip show contacts"        # judicom/sip:...@100.64.0.2 = the Judicom is registered
    docker exec asterisk-test asterisk -rx "dialplan show judicom-allowed"
    docker exec asterisk-test asterisk -rx "core show channels"         # calls up right now

A call from Asterisk to the Judicom, for testing (rings it as "unknown caller"; lift the handset and the melody plays):

    docker exec asterisk-test asterisk -rx "channel originate PJSIP/judicom extension 100@from-judicom"

To see why a call failed, turn on detailed logging for one call, then off again:

    A="docker exec asterisk-test asterisk -rx"
    $A "logger add channel /var/log/asterisk/judicom-debug.log notice,warning,error,verbose"; $A "core set verbose 3"
    $A "pjsip set logger host 208.100.60.6"                 # SIP messages to and from VoIP.ms
    # ... make the call, then read:  docker exec asterisk-test cat /var/log/asterisk/judicom-debug.log
    $A "pjsip set logger off"; $A "core set verbose 0"; $A "logger remove channel /var/log/asterisk/judicom-debug.log"

(The log holds the VoIP.ms account name and login exchanges: delete it afterwards.)

### Firewall

One hand-made rule guards Asterisk; everything else in the NAS's nftables ruleset is made automatically by Tailscale (the
`ts-...` chains) and Docker (the `DOCKER...` chains).  Debian's own `nftables` service is **off** and `/etc/nftables.conf` is the
untouched default; the rule has its own service instead:

| File on the NAS | Copy | What it does |
|---|---|---|
| `/etc/asterisk-firewall.nft` | `deploy/nas/firewall/` (as it was before the set) | table `inet asterisk_test`: on the home network (`eth0`), SIP (UDP 5060) from anyone not in the set `voipms` (VoIP.ms's Chicago server) is **dropped**.  Written by `voipms_address_check.py` |
| `/etc/systemd/system/asterisk-firewall.service` | `deploy/nas/firewall/` | loads that file at boot (before Docker), only if the table is not there already; enabled |

What gets through to Asterisk:
- **VoIP.ms** (`208.100.60.6`) on the home network: the registration, and incoming calls to Judi's number.
- **The Judicom**, over Tailscale (`tailscale0`, Asterisk's `100.64.0.1:5060`): Tailscale's own rules accept everything that comes
  over Tailscale, so the rule above does not apply there.
- Nobody else's SIP on the home network.  (The rule is IPv4 only; Asterisk listens on IPv4 only, so that is enough.)  The RTP
  (voice) ports are not filtered.

**VoIP.ms changing the server's address is handled by itself**: `voipms-address-check.timer` (root, hourly; installed with
`deploy/nas/firewall/install_address_check.sh`) runs `/usr/local/sbin/voipms_address_check.py`, which looks up `chicago4.voip.ms`
and ADDS any new address (never removes) to the firewall's `voipms` set (live, and in `/etc/asterisk-firewall.nft` for the next
boot) and to the `match=` line of `voipms-identify` in `voipms.conf` (then a pjsip reload).  A lookup that fails, or gives a
private address or too many, changes nothing and writes a WARNING.  See what it did: `journalctl -u voipms-address-check`;
what it would do: `sudo python3 /usr/local/sbin/voipms_address_check.py --dry-run`.  (On 2026-11-03 the address was
`208.100.60.6`.)

See the live rules: `sudo nft list table inet asterisk_test` (all of them: `sudo nft list ruleset`).

## 3. The Judicom

Raspberry Pi 3 B+, Raspberry Pi OS without a desktop, user `joe` (in the groups `video render input gpio audio`), Tailscale
installed and logged in (address `100.64.0.2`), **time zone America/Chicago** (`sudo timedatectl set-timezone America/Chicago`:
the screen's clock and the 9 pm - 6 am night clock go by it).

**What the screen shows** when no call is going on: the photos; after every 5 photos, for 30 s, the next of three screens in
turn: the info screen (day, date, time, the next 5 events with countdowns), a Bible verse, and the weather (Springfield today and
the next 5 days, from Open-Meteo; left out when there is no internet); from 9 pm to 6 am the night clock (time and date, dim).
Settings at the end of `software/judicom/config.py`.  To see the photos and the info screen at night (setting up, showing
someone): `touch ~/judicom-awake` on the Judicom; it pauses the night clock for 2 hours (or until `rm ~/judicom-awake`).

    sudo apt install python3-pygame python3-pil python3-gpiozero python3-lgpio alsa-utils baresip
    git clone https://github.com/calphool/Judicom.git ~/Judicom

| File on the Judicom | From | Notes |
|---|---|---|
| `~/.asoundrc` | `deploy/judicom/asoundrc` | names the cards: `judicom_handset` (USB card `Device`), `judicom_ring` (`Headphones` jack), `judicom_mic_boost` (USB mic, with a software gain control).  The USB adapter's microphone is **mono** (`slave.channels 1`) |
| `~/.baresip/config` | `deploy/judicom/baresip/config` | binds to `tailscale0`; `ctrl_tcp` on `127.0.0.1:4444` (the phone program's connection); `call_max_calls 1` (a second caller gets busy); `audio_alert alsa,null` (baresip does not ring: the phone program does); `statmode_default off` (no live call-status line: under systemd it piles up into one huge journal entry, `[blob data]`, during every call) |
| `~/.baresip/accounts` | `deploy/judicom/baresip/accounts.example` | the password is the one in `judicom.conf` on the NAS |
| `~/contacts.txt` | **fetched from the NAS** by the `judicom-contacts-sync` timer (at boot, then every 10 minutes) | a copy of Judi's caller list: the two buttons and the names shown for incoming calls.  Local changes are overwritten.  Fetch now: `sudo systemctl start judicom-contacts-sync`; log: `journalctl -u judicom-contacts-sync` |
| `~/events.txt` | **fetched from the NAS** with the caller list | a copy of Judi's events list, for the info screen |
| `~/verses.txt` | **fetched from the NAS** with the caller list | a copy of Judi's verse list, for the verse screen |
| `~/people/` | **copied from the NAS** with the caller list | a copy of `/home/pi/judicom/people/`: the people pictures for the call screens (section 2).  Only changed pictures are fetched (compared by sha256); at most 5 MB each and 50 MB altogether |
| `~/.ssh/judicom_sync` | `ssh-keygen -t ed25519 -N "" -C judicom-contacts-sync -f ~/.ssh/judicom_sync` | the key that fetches the list; its public half goes on the NAS (section 2) |
| `~/photos/` | **copied from the NAS** by the `judicom-photo-sync` timer (2 min after boot, then every hour) | a copy of `/mnt/8tbdrive/Photos/Judi`, **pictures it can show (.jpg .jpeg .png .bmp) and .meta captions only**: videos and other formats the mail importer saves there stay on the NAS (Jellyfin), so they cannot fill the card.  Pictures removed there go here too.  Nothing is changed if the NAS can't be reached, its folder has no pictures (drive not mounted?), copying the new photos would leave less than 4 GB free on the card (`PHOTO_KEEP_FREE`; a "nearly full" warning in the log), or more than half of the pictures would go (`python3 -m judicom.photo_sync --force` by hand if that is meant).  Fetch now: `sudo systemctl start judicom-photo-sync`; see first: `python3 -m judicom.photo_sync --dry-run`; log: `journalctl -u judicom-photo-sync` |
| `~/.ssh/judicom_photos` | `ssh-keygen -t ed25519 -N "" -C judicom-photo-sync -f ~/.ssh/judicom_photos` | the key that copies the photos; its public half goes on the NAS (section 2) |
| boot picture | `judicom_splash/install_splash.sh` | |
| services | `bash ~/Judicom/software/systemd/install_services.sh` | `judicom-baresip`, `judicom-phone`, and the `judicom-contacts-sync` and `judicom-photo-sync` timers; also keeps the boot picture up until the first photo and turns off the login prompt on the screen |

baresip's controlling connection takes **one client at a time**: while `judicom-phone` runs, do not use
`python3 -m judicom.calls` (it knocks the phone off the line).  Stop the service first.

### Wi-Fi

NetworkManager joins the best known network it can see.  Joe's phone hotspot `JOE5G` has priority 100 (the home network 0), so
whenever the Judicom is choosing a network and the hotspot is on, it takes the hotspot: at a new place (the nursing home) for the
first setup, or when the Wi-Fi there fails.  Add the nursing home's network while on the hotspot:

    sudo nmcli dev wifi connect "NETWORK" password "PASSWORD"
    sudo nmcli connection modify JOE5G connection.autoconnect-priority 100     # (already done)

### The system log

Raspberry Pi OS keeps it in memory only, so a restart would erase what happened before it.  `install_services.sh` installs
`software/systemd/journald-judicom.conf` as `/etc/systemd/journald.conf.d/90-judicom.conf`: kept on the card, a new file every
hour, nothing older than a day, at most 50 MB (and always 1 GB free).  The boot before the current one: `journalctl -b -1`.

### Checks

    systemctl is-active judicom-baresip judicom-phone
    journalctl -u judicom-phone -f            # mode changes, calls, which photo
    journalctl -u judicom-baresip -f          # registration ("200 OK"), calls

baresip's first start at boot usually fails once (`tailscale0: No such device`, Tailscale is not up yet) and the 5 s automatic
restart works; its log also shows `module stdio.so: Operation not permitted` (no keyboard under systemd).  Both are expected.

### Reaching it

On the home network: `ssh joe@judicom.local`.  Anywhere else, through Tailscale: `ssh joe@100.64.0.2` from a device on Tailscale,
or through the NAS: `ssh -J pi@naspi.local joe@100.64.0.2`.

## Backup of the SD card

The whole card, as an image, while the Judicom runs, **at home only** (it goes over the home network; over Tailscale the copy
stalls while the card is frozen, which on 2026-11-04 left the Judicom frozen until it was unplugged).  On the Judicom:

    bash ~/Judicom/deploy/judicom/backup_judicom.sh --trial     # measures the speed and the image size; tries the freeze and
                                                                # the watchdog; the phone is off for about a minute
    bash ~/Judicom/deploy/judicom/backup_judicom.sh             # the backup: the phone is off for about 6 minutes, 15 at most

It stops the phone and the syncs, moves the system log to memory, and runs `backup_stream.sh` as root: it freezes the main
partition (`fsfreeze`) and writes the start of the card and the boot partition (dd) plus the main partition's used blocks
(free space as zeros) to the NAS through zstd.  It unfreezes whenever it ends (done, error, Ctrl-C), a watchdog
inside it ends the copy after 15 minutes (under the 30 that set off the offline alert), and a separate guard unfreezes after
20 minutes even if it were killed.  Every 30 seconds it notes in `/run/judicom-backup-progress.log` (in memory, kept until the
next backup or reboot) what the card has given, what has gone out over Wi-Fi and what the copying programs are doing, so a stuck
copy shows which stage stopped.  In a terminal, step 2 shows a progress bar of how far through the main partition the copy is (it
stays at 0% for the first half minute, the boot area, and speeds up in the free space near the end); if the spinner turns but the
MB stand still, the copy is stuck.  It starts the phone again itself as soon as the card is unfrozen.  The main partition is read by `copy_used_blocks.py`: the used blocks
(from `dumpe2fs`, read-only) as they are, the free ones as zeros, i.e. the image `e2image -ra` makes (plus the backup
superblocks).  Not e2image itself: its "is it mounted?" check creates `/.ismount-test-file`, which waits forever on a frozen root
(found with strace on 2026-11-04; a loop device does not hide the mount, device-mapper refuses a mounted partition).  The NAS keeps the upload as a hidden unfinished file until `commit`: only if its SHA-256 matches what the Judicom
sent and it unpacks does it get its real name (so a cut-off upload never looks like a backup).  While frozen nothing can start `sudo` (it writes a session record):
if something ever does hang, wait for the guard (20 minutes) or unplug the Judicom (a frozen card is in a clean state).

- On the NAS: `/mnt/2tbdrive/judicom-backups/judicom-<date-time>.img.zst` (+ `.sha256`), the newest 5 kept.  The Judicom's key
  `~/.ssh/judicom_backup` may only store, commit and discard (speed test): `restrict,command="/home/pi/judicom/receive_backup.sh" ...`
  (`deploy/nas/judicom/receive_backup.sh`).
- **Putting a backup on a new card** (as large as the old one, or larger): copy the `.img.zst` to a computer, then either
  Raspberry Pi Imager -> "Use custom" -> the file, or
  `zstd -dc judicom-....img.zst | sudo dd of=/dev/sdX bs=4M status=progress conv=fsync` (sdX: the new card; check with lsblk!).
  The card is then the Judicom as it was at the backup, with the same Tailscale identity, keys and Wi-Fi networks.
- Make one after big changes, and keep a spare card with a recent backup on it.
- If the Judicom's card is ever changed for a different size, check `backup_judicom.sh`: it expects the main partition to reach
  the end of the card.

## 4. Adding someone who may call Judi

Easiest: the **Callers** page of the housekeeping website (section 2).  By hand: add a line `<number> | <name> | <relationship>` to `/home/pi/judicom/contacts.txt` on the NAS.  Within 10 minutes they can ring
through, and within 10 minutes their name shows on the Judicom.  For both at once:

    python3 /home/pi/judicom/apply_contacts.py                  # on the NAS
    sudo systemctl start judicom-contacts-sync                  # on the Judicom

Removing someone works the same way.  To change who the buttons call, move `left` / `right` to another line.

## 5. What is not in git (back it up somewhere private)

- NAS: `/home/pi/judicom/contacts.txt` (Judi's caller list), `voipms.conf`, `judicom.conf` (passwords), the two message WAVs (they
  speak the contact number)
- NAS: `/mnt/8tbdrive/Photos/Judi` (Judi's photos; the Judicom only has a copy)
- Judicom: `~/.baresip/accounts` (password), `~/.ssh/judicom_sync` and `~/.ssh/judicom_photos` (can be made again)
- VoIP.ms portal settings (section 1)
