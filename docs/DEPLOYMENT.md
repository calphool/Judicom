# Judicom Deployment

How the working system is set up, and how to rebuild it.  The configuration files are in [`deploy/`](../deploy); passwords and family
phone numbers are **not** in git (the repository is public), so each place that needs one says where it comes from.

```text
Judi's phone number (VoIP.ms DID) --SIP--> NAS: Asterisk in Docker --Tailscale--> Judicom: baresip + judicom-phone
                                           screens callers against                  rings, shows the caller's name
                                           judicom-allowed.conf                     (contacts.txt), dials the buttons
```

| Part | Where it runs | Kept in git | Kept only on the device |
|---|---|---|---|
| VoIP.ms account, DID, caller ID | voip.ms web portal | the settings, below | everything |
| Asterisk (PBX) | NAS `naspi`, Docker container `asterisk-test` | `deploy/nas/asterisk/` | passwords, `judicom-allowed.conf`, the two messages |
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
| `judicom-allowed.conf` | the allowed callers, 10 digits each.  From `judicom-allowed.conf.example` |

`extensions.conf` is Asterisk's stock file with these lines at the end (the first was there already):

    #include "voipms-test.conf"
    #include "judicom-inbound.conf"
    #include "judicom-allowed.conf"

The two messages are `custom/judicom-protected.wav` and `custom/judicom-unavailable.wav` in the container's
`/var/lib/asterisk/sounds/custom/` (a Docker volume).  Make them with `deploy/prompts/make_prompts.sh <contact number>` (Piper
text-to-speech; the wording is in `protected.txt` / `unavailable.txt`) and copy them in with `docker cp` (the script says how).

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

The NAS's `nftables` rules for SIP are **not documented yet** (reading them needs sudo on the NAS).  To add:
`sudo nft list ruleset`, and how the rules are made permanent.

## 3. The Judicom

Raspberry Pi 3 B+, Raspberry Pi OS without a desktop, user `joe` (in the groups `video render input gpio audio`), Tailscale
installed and logged in (address `100.64.0.2`).

    sudo apt install python3-pygame python3-pil python3-gpiozero python3-lgpio alsa-utils baresip
    git clone https://github.com/calphool/Judicom.git ~/Judicom

| File on the Judicom | From | Notes |
|---|---|---|
| `~/.asoundrc` | `deploy/judicom/asoundrc` | names the cards: `judicom_handset` (USB card `Device`), `judicom_ring` (`Headphones` jack), `judicom_mic_boost` (USB mic, with a software gain control).  The USB adapter's microphone is **mono** (`slave.channels 1`) |
| `~/.baresip/config` | `deploy/judicom/baresip/config` | binds to `tailscale0`; `ctrl_tcp` on `127.0.0.1:4444` (the phone program's connection); `call_max_calls 1` (a second caller gets busy); `audio_alert alsa,null` (baresip does not ring: the phone program does) |
| `~/.baresip/accounts` | `deploy/judicom/baresip/accounts.example` | the password is the one in `judicom.conf` on the NAS |
| `~/contacts.txt` | `software/contacts.example.txt` | the two buttons and the names shown for incoming calls (see `software/README.md`) |
| `~/photos/` | the NAS (twice-a-day sync, still to be set up) | |
| boot picture | `judicom_splash/install_splash.sh` | |
| services | `bash ~/Judicom/software/systemd/install_services.sh` | `judicom-baresip` and `judicom-phone`; also keeps the boot picture up until the first photo and turns off the login prompt on the screen |

baresip's controlling connection takes **one client at a time**: while `judicom-phone` runs, do not use
`python3 -m judicom.calls` (it knocks the phone off the line).  Stop the service first.

### Wi-Fi

NetworkManager joins the best known network it can see.  Joe's phone hotspot `JOE5G` has priority 100 (the home network 0), so
whenever the Judicom is choosing a network and the hotspot is on, it takes the hotspot: at a new place (the nursing home) for the
first setup, or when the Wi-Fi there fails.  Add the nursing home's network while on the hotspot:

    sudo nmcli dev wifi connect "NETWORK" password "PASSWORD"
    sudo nmcli connection modify JOE5G connection.autoconnect-priority 100     # (already done)

### Checks

    systemctl is-active judicom-baresip judicom-phone
    journalctl -u judicom-phone -f            # mode changes, calls, which photo
    journalctl -u judicom-baresip -f          # registration ("200 OK"), calls

baresip's first start at boot usually fails once (`tailscale0: No such device`, Tailscale is not up yet) and the 5 s automatic
restart works; its log also shows `module stdio.so: Operation not permitted` (no keyboard under systemd).  Both are expected.

### Reaching it

On the home network: `ssh joe@judicom.local`.  Anywhere else, through Tailscale: `ssh joe@100.64.0.2` from a device on Tailscale,
or through the NAS: `ssh -J pi@naspi.local joe@100.64.0.2`.

## 4. Adding someone who may call Judi

1. On the NAS: add `exten => <10 digits>,1,NoOp(<name>)` to `judicom-allowed.conf`, then `dialplan reload`.
2. On the Judicom: add `<number> | <name> | <relationship>` to `~/contacts.txt` (picked up within 5 s).

If step 2 is forgotten the call still rings, as "Incoming call from unknown caller: <number>".  If step 1 is forgotten the caller hears
the protected-number message.

## 5. What is not in git (back it up somewhere private)

- NAS: `voipms.conf`, `judicom.conf` (passwords), `judicom-allowed.conf` (numbers), the two message WAVs (they speak the contact number)
- Judicom: `~/.baresip/accounts` (password), `~/contacts.txt` (numbers), `~/photos/`
- VoIP.ms portal settings (section 1)
