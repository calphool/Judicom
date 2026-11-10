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
| NAS | Raspberry Pi 4 Model B Rev 1.5; Debian Linux, Docker, storage, network services | Existing; configuration to inventory |
| Asterisk | Asterisk 22 in Docker on NAS | Running; VoIP.ms registration previously confirmed |
| SIP service | VoIP.ms, Chicago server | Registration confirmed; incoming and outgoing calls in use |
| Private networking | Tailscale between endpoint and NAS; SSH administration | In use / verify current routing and access rules |
| Family/media workflows | Family-facing messages and media services hosted or mediated by NAS | Partially implemented / evolving |

## Communication and security

- **Endpoint ↔ NAS:** private IP connectivity, preferably over Tailscale; no need to expose the endpoint directly to the internet.
- **NAS ↔ VoIP.ms:** Asterisk uses SIP signaling and RTP media. Confirm the actual ports, NAT traversal, and inbound media behavior against the live configuration.
- **Firewall:** NAS uses `nftables` rules for SIP access. Preserve the live rules and their persistence mechanism in deployment documentation, not here.
- **Secrets:** SIP credentials, tokens, private keys, and other secrets must not be committed to Git. Check exported configurations before adding them.

## Current state and open decisions

**Established:** the Python/Pygame phone on the Pi 3 A+; hook switch and buttons; USB handset audio; the switched ringtone amplifier; NAS-hosted Asterisk 22; VoIP.ms registration and calls in both directions; Tailscale connectivity.

**Still to validate:** power supply rating (the Pi has reported under-voltage); device boot and recovery behavior; final enclosure.

**Deferred:** video calling and optional migration to Orange Pi.

## Related documentation

- `README.md` — purpose and quick start
- `docs/DEPLOYMENT.md` — installation, services, Asterisk, Docker, and firewall configuration
- `docs/HARDWARE.md` — wiring, pin assignments, handset tests, and enclosure
- `docs/DECISION.md` — significant design choices and their rationale

> **Documentation rule:** This file describes the architecture. Actual configuration files and repeatable deployment steps belong alongside it in version control, with secrets excluded.
