# Judicom Design Decisions

A short log of the choices that shaped the Judicom, and why.

| ID | Decision | Status | Rationale / consequence |
|---|---|---|---|
| D-001 | Use Raspberry Pi 3 Model A+ as the endpoint | Implemented | Existing Raspberry Pi/Python ecosystem; its single USB port needs a hub for the sound adapter and touch panel |
| D-002 | Use Raspberry Pi 4 Model B Rev 1.5 as the NAS | Implemented | Centralizes application services, storage, and telephony |
| D-003 | Run Asterisk 22 in Docker on the NAS, using VoIP.ms | Implemented | Registration and calls in both directions work; incoming calls are screened against the caller list |
| D-004 | Use Tailscale for private endpoint/NAS connectivity | Implemented | Avoid exposing endpoint services directly to the public internet |
| D-005 | Favor physical buttons and a traditional Merlin handset | Implemented | Familiar operation and fewer on-screen interaction requirements |
| D-006 | Use USB audio for the Merlin handset | Implemented | C-Media USB adapter; the Merlin's original microphone was replaced with an electret the adapter can bias. Simpler than I²S |
| D-007 | Use separate ringtone speaker through Pi analog output and a PAM8403 amplifier | Implemented | Separates ringtone playback from private handset audio; the amplifier is switched off between sounds (GPIO 25) to stop its noise |
| D-008 | Defer video calling | Deferred | Reduce complexity and focus on reliable audio communication |
| D-009 | Reconsider Orange Pi only for a later hardware revision | Deferred | Little benefit from migrating until the current hardware path is stable |

## Decision rule

Record only choices that materially affect architecture, hardware, security, or user interaction. When a choice changes, update its row with the replacement decision and a brief reason; keep detailed experiments in issues or technical notes.
