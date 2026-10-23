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
| Ringtone amplifier | LM386 module driven from Pi's 3.5 mm analog output | Proposed; gain, noise and output level to test |
| Microphone prototype | INMP441 I²S microphone | Previously functional; likely to be retired for handset design |
| Enclosure | Custom 3D-printed enclosure designed in FreeCAD | In development; mounting geometry may change |
| Power | External regulated 5 V supply and internal distribution | Final supply rating and wiring TBD |

## Planned audio paths

```text
Merlin handset mic/receiver <-> compatible analog interface <-> USB sound device <-> Pi 3 B+
Pi 3 B+ analog 3.5 mm output -> LM386 amplifier -> external ringtone speaker
```

Do **not** assume the original Merlin microphone is an electret capsule, that its receiver is suitable for direct connection to a USB adapter, or that the handset's four contacts have a standard pinout. Identify the actual handset and measure its circuits first. Do not connect an unknown transducer directly to a powered mic input.

The Pi 3 B+ analog jack is a four-pole A/V connector; confirm the correct audio contacts using the Pi's documented pinout or a known-compatible breakout. Do not short stereo outputs together to form mono; use software mono routing or an appropriate summing network.

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
- [ ] Test independent ringtone routing through the analog output and LM386.
- [ ] Measure operating and peak 5 V current draw with display, Pi, amplifier, and button LEDs.
- [ ] Verify GPIO pins, switch logic, LED resistors/drivers, and boot behavior.
- [ ] Confirm final FreeCAD dimensions, mounting holes, and cable clearances.

Record measured pinouts and wiring diagrams here once validated; do not substitute assumed values.
