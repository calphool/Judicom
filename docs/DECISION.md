# Judicom Design Decisions

A short decision log. **Accepted** means chosen as the current baseline; it does not imply the full implementation has been tested.

| ID | Decision | Status | Rationale / consequence |
|---|---|---|---|
| D-001 | Use Raspberry Pi 3 Model B+ as the endpoint target | Accepted | Existing Raspberry Pi/Python ecosystem; confirm migration from earlier Pi 3 A+ work |
| D-002 | Use Raspberry Pi 4 Model B Rev 1.5 as the NAS | Accepted | Centralizes application services, storage, and telephony |
| D-003 | Run Asterisk 22 in Docker on the NAS, using VoIP.ms | Implemented in part | Registration has worked; inbound SIP/RTP still needs end-to-end testing |
| D-004 | Use Tailscale for private endpoint/NAS connectivity | Accepted | Avoid exposing endpoint services directly to the public internet |
| D-005 | Favor physical buttons and a traditional Merlin handset | Accepted direction | Familiar operation and fewer on-screen interaction requirements |
| D-006 | Investigate USB audio for the Merlin handset | Proposed | More portable and potentially simpler than I²S; verify transducer compatibility |
| D-007 | Use separate ringtone speaker through Pi analog output and LM386 | Proposed | Separates ringtone playback from private handset audio |
| D-008 | Defer video calling | Deferred | Reduce complexity and focus on reliable audio communication |
| D-009 | Reconsider Orange Pi only for a later hardware revision | Deferred | Little benefit from migrating until the current hardware path is stable |

## Open decisions

- **Handset internals:** retain original microphone/receiver or replace them after inspection?
- **Audio adapter:** which USB interface provides adequate bias, gain, and receiver drive with acceptably low noise?
- **Call experience:** what do the buttons do, how is answer/hangup detected, and which callers are admitted?
- **Networking:** what inbound SIP/RTP and firewall configuration works reliably behind CGNAT?
- **Power and enclosure:** final supply rating, distribution, wiring, and service-access design?

## Decision rule

Record only choices that materially affect architecture, hardware, security, or user interaction. When a choice changes, update its row with the replacement decision and a brief reason; keep detailed experiments in issues or technical notes.
