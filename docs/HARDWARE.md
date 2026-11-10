# Judicom Hardware

This page records the hardware baseline and integration questions. It is **not yet a finalized wiring diagram**.

## Computing platforms

| Device | Hardware | Function |
|---|---|---|
| Judicom endpoint | Raspberry Pi 3 Model B+ | Local display, controls, and audio |
| NAS | Raspberry Pi 4 Model B Rev 1.5 | Storage and network/application services, including Asterisk |

The endpoint is currently assumed to be a **Pi 3 B+**, replacing earlier Pi 3 A+ prototype assumptions. Reconfirm connector placement, current draw, mounting, and GPIO assignments against the actual board before finalizing the enclosure.

## Endpoint components

| Component | Details | State |
|---|---|---|
| Display | 7-inch HDMI IPS, 1024 × 600; USB connection for touch functionality | Previously tested with Raspberry Pi/Pygame; verify on Pi 3 B+ |
| Physical controls | Two large illuminated pushbuttons (EG STARTS, 60 mm) | Intended; GPIO wiring and function mapping TBD |
| Handset | Vintage AT&T Merlin handset, model/transducers to be inspected | Ordered; connector pinout and internal construction unverified |
| Handset audio | USB full-duplex audio interface, with suitable mic bias and receiver drive if required | Proposed |
| Ringtone speaker | 4 Ω, 3 W speaker; approximately 53 × 53 × 25 mm | Available; final mounting TBD |
| Ringtone amplifier | PAM8403 (class-D) amplifier module driven from Pi's 3.5 mm analog output | Proposed; gain, noise and output level to test |
| Microphone prototype | INMP441 I²S microphone | Previously functional; likely to be retired for handset design |
| Enclosure | Custom 3D-printed enclosure designed in FreeCAD | In development; mounting geometry may change |
| Power | External regulated 5 V supply and internal distribution | Final supply rating and wiring TBD |

## Planned audio paths

```text
Merlin handset mic/receiver <-> compatible analog interface <-> USB sound device <-> Pi 3 B+
Pi 3 B+ analog 3.5 mm output -> PAM8403 amplifier -> external ringtone speaker
GPIO 25 (high = on) -> MOSFET switch for the PAM8403: the phone switches the amplifier on only while the speaker plays
```

Do **not** assume the original Merlin microphone is an electret capsule, that its receiver is suitable for direct connection to a USB adapter, or that the handset's four contacts have a standard pinout. Identify the actual handset and measure its circuits first. Do not connect an unknown transducer directly to a powered mic input.

The Pi 3 B+ analog jack is a four-pole A/V connector; confirm the correct audio contacts using the Pi's documented pinout or a known-compatible breakout. Do not short stereo outputs together to form mono; use software mono routing or an appropriate summing network.

### The handset microphone plug (USB adapter's pink socket)

The handset mic is an electret capsule into the C-Media USB adapter (Unitek Y-247A).  On that adapter's mic socket the
**sleeve is ground**; the tip carries the signal and the bias that powers the electret.  The plug in use is a four-section
(TRRS) one, wired so that it works whether the socket's ground spring lands on the second ring or on the sleeve:

| Plug section, from the end | Wired to |
|---|---|
| tip | electret signal (+): the pad *not* joined to the capsule's metal can |
| first ring | nothing (insulated) |
| second ring | electret ground (−): the pad joined to the can |
| sleeve | electret ground (−), the same as the second ring |

A plug with only tip and ring wired does **not** work: the electret has no ground and the caller hears only a 60 Hz buzz
(found 2026-11-09; it had seemed to work only because the plug sat a few millimetres out of the socket).  To check the mic:
with no call going on, `arecord -D hw:CARD=Device,DEV=0 -f S16_LE -r 48000 -c 1 -d 6 /tmp/mic.wav` while counting into the
handset, and listen to it, or look at it: speech rises and falls; a steady level of nothing but hum means no ground.
With the mic plug pulled out, the input records near silence (about -80 dBFS).

## Ringer amplifier switch (why the amplifier is switched on and off)

The PAM8403 put noise on the ringtone speaker whenever it was powered, even with nothing playing.  Rather than chase the noise
itself, the amplifier is now switched off whenever the speaker has nothing to play:

- A MOSFET switch controlled by **GPIO 25** (BCM numbering; high = amplifier on) turns the PAM8403 on and off.  It was built and
  tested on 2026-11-07.
- The phone program switches it **on** just before anything plays on the speaker (the ringer, a message's three beeps, the
  maintenance shell's bongs) and **off** once the speaker has been quiet for `AMP_OFF_SECONDS` (1 second), so the end of a sound is
  not cut off.  It stays on through the gaps of a ring.  The handset's sounds (dial tone, dialing) do not use it.
- While the phone program runs it holds GPIO 25 low.  At boot and whenever the phone program is not running, nothing drives the pin:
  unless the MOSFET's gate has a pull-down resistor, add `gpio=25=op,dl` to `/boot/firmware/config.txt` so the firmware holds it low
  from power-on.

**If the ringer is silent,** this switch is the first thing to check: without GPIO 25 high the amplifier is off, so the ringer, the
message beeps and the bongs all go quiet.  The phone's log says so at start if it cannot get the pin.  To test the switch, stop the
phone program (`sudo systemctl stop judicom-phone`), then `cd ~/Judicom/software && python3 -m judicom.ring_test` should ring
and `python3 -m judicom.ring_test --pin 25=0` should stay silent.  Start the phone again afterwards.

In the code: `AMP_PIN` and `AMP_OFF_SECONDS` in `software/judicom/config.py`, `Amp` and `Sounds` in `software/judicom/sound.py`.
**Do not remove the switching as an unneeded power-saving step:** it is what keeps the speaker quiet between sounds.

## Mechanical notes

- Display visible opening: approximately **155 × 88 mm**.
- Button housing/base: approximately **63 mm diameter**; mounting depth to lowest terminal approximately **48 mm**.
- Speaker: approximately **53 × 53 × 25 mm**, with reported mounting-hole spacing near **43 mm**.
- Earlier design targeted a roughly **50 mm high base** and removable bottom/rear access panels. Verify these dimensions against the latest FreeCAD model.
- Account for the Pi 3 B+ port locations, power distribution, strain relief, handset cradle, and service access before final print.

## Validation checklist

- [ ] Identify Merlin handset variant and connector contact mapping.
- [ ] Determine microphone type, bias requirements, and receiver impedance.
- [ ] Test clean, full-duplex USB handset audio under ALSA.
- [ ] Test independent ringtone routing through the analog output and the PAM8403.
- [ ] Measure operating and peak 5 V current draw with display, Pi, amplifier, and button LEDs.
- [ ] Verify GPIO pins, switch logic, LED resistors/drivers, and boot behavior.
- [ ] Confirm final FreeCAD dimensions, mounting holes, and cable clearances.

Record measured pinouts and wiring diagrams here once validated; do not substitute assumed values.
