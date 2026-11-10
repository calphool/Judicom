# Judicom Architecture

Judicom is a simple, physical communications device intended for a person who may find conventional smartphones difficult to use. A Raspberry Pi endpoint provides a display, two physical photo buttons, and telephone-style audio. A separate Raspberry Pi NAS hosts supporting services and connects the endpoint to family members and a SIP telephone provider.

## System overview

```mermaid
flowchart LR
    H["Merlin handset<br/>USB audio"] --> J["Judicom endpoint<br/>Raspberry Pi 3 A+"]
    B["Physical buttons, hook switch +<br/>7-inch HDMI touch display"] --- J
    J --> S["Ringtone speaker<br/>3.5 mm + switched amplifier"]
    J -->|Tailscale| N["NAS/PBX<br/>Raspberry Pi 4 Model B Rev 1.5"]
    N -->|Tailscale| J
    N --- A["Asterisk 22<br/>Docker"]
    A -->|SIP / RTP| V["VoIP.ms"]
    V -->|SIP / RTP| A
    F["Family-facing services<br/>and media workflows"] --- N
```


The endpoint is designed to communicate with the NAS over a private network. The NAS hosts Asterisk and other application/media services. VoIP.ms provides external SIP connectivity; incoming calls are screened by Asterisk (`judicom-inbound.conf`) and ring the Judicom.

## Components

| Component | Platform / function | Status |
|---|---|---|
| Judicom endpoint | Raspberry Pi 3 Model A+; Python / Pygame; 7-inch 1024×600 HDMI touch display (portrait); two physical buttons and a hook switch | In use |
| Handset audio | Merlin handset (microphone replaced with an electret) via a C-Media USB audio adapter | In use |
| Ringtone | Separate speaker driven by 3.5 mm output through a PAM8403 (class-D) amplifier, switched by GPIO 25 | In use |
| NAS | Raspberry Pi 4 Model B Rev 1.5; Debian Linux, Docker, storage, network services (also Jellyfin) | In use; set-up in `docs/DEPLOYMENT.md` |
| Asterisk | Asterisk 22 in Docker on NAS; screens incoming callers against the caller list | Running |
| SIP service | VoIP.ms, Chicago server | Registration confirmed; incoming and outgoing calls in use |
| Private networking | Tailscale between endpoint and NAS; SSH administration with restricted keys | In use |
| Family/media workflows | Housekeeping website (callers, events, pictures, photos, messages to the screen); photos emailed in by family; offline alert emails | In use |

## Communication and security

- **Endpoint ↔ NAS:** over Tailscale (SIP, the list and photo syncs, the screen and messages); only the SD-card backup uses the home network. The endpoint is not exposed to the internet.
- **NAS ↔ VoIP.ms:** Asterisk registers with VoIP.ms and uses SIP signaling and RTP media; ports and firewall are in `docs/DEPLOYMENT.md`.
- **Firewall:** an `nftables` rule on the NAS drops SIP on the home network from anyone but VoIP.ms (details in `docs/DEPLOYMENT.md`).
- **Secrets:** SIP credentials, tokens, private keys, and other secrets must not be committed to Git. Check exported configurations before adding them.

## Current state and open decisions

**Established:** the Python/Pygame phone on the Pi 3 A+; hook switch and buttons; USB handset audio; the switched ringtone amplifier; NAS-hosted Asterisk 22; VoIP.ms registration and calls in both directions; Tailscale connectivity.

**Still to validate:** the 5 V at the Pi (it dipped below the under-voltage threshold when the handset was lifted or the ringer started); device boot and recovery behavior; final enclosure.

**Deferred:** video calling and optional migration to Orange Pi.

## Related documentation

- `README.md` — purpose and how the phone behaves
- `software/README.md` — the phone program, its tests and hardware checks
- `docs/DEPLOYMENT.md` — installation, services, Asterisk, Docker, and firewall configuration
- `docs/HARDWARE.md` — wiring, pin assignments, handset tests, and enclosure
- `docs/DECISION.md` — significant design choices and their rationale

> **Documentation rule:** This file describes the architecture. Actual configuration files and repeatable deployment steps belong alongside it in version control, with secrets excluded.
