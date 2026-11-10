# Judicom Hardware

This page records the hardware as built and the questions still open. It is **not yet a finalized wiring diagram**.

## Computing platforms

| Device | Hardware | Function |
|---|---|---|
| Judicom endpoint | Raspberry Pi 3 Model A+ Rev 1.0 | Local display, controls, and audio |
| NAS | Raspberry Pi 4 Model B Rev 1.5 | Storage and network/application services, including Asterisk |

Both models were read from the boards themselves (`cat /proc/device-tree/model`, 2026-11-10). The Pi 3 A+ has a single USB-A
port, so the USB sound adapter and the touch panel share a small USB hub. Check connector placement, current draw, and mounting
against the actual board before finalizing the enclosure.

## Endpoint components

| Component | Details | State |
|---|---|---|
| Display | 7-inch HDMI IPS (HS-007), 1024 × 600, mounted sideways (portrait): the software draws 600 × 1024 and turns it 90°. Touch over USB (`1a86:e5e3` USB2IIC_CTP_CONTROL) | In use |
| Physical controls | Two large illuminated pushbuttons (EG STARTS, 60 mm), on GPIO 23 (left) and 24 (right) | In use; LED wiring and supply not yet recorded here |
| Hook switch | Three contacts: two normally closed (GPIO 17, 27) and one normally open (GPIO 22); the three vote | In use |
| Handset | Vintage AT&T Merlin handset; its original microphone replaced with an electret capsule | In use |
| Handset audio | C-Media USB audio adapter (Unitek Y-247A, `0d8c:0014`), ALSA card `Device`; mono mic | In use |
| Ringtone speaker | 4 Ω, 3 W speaker; approximately 53 × 53 × 25 mm | In use; final mounting TBD |
| Ringtone amplifier | PAM8403 (class-D) module driven from the Pi's 3.5 mm analog output (ALSA card `Headphones`), switched by GPIO 25 | In use |
| Microphone prototype | INMP441 I²S microphone | Not used by the phone; its overlay (`dtoverlay=inmp441`) is still in `config.txt`, so it still appears as an ALSA capture card |
| Enclosure | Custom 3D-printed enclosure designed in FreeCAD | In development; mounting geometry may change |
| Power | External regulated 5 V supply and internal distribution | Final supply rating and wiring TBD |

## GPIO assignments (BCM numbering)

| GPIO | Direction | Connected to |
|---|---|---|
| 17 | input, internal pull-up | hook switch, normally-closed contact 1 (switch to ground) |
| 27 | input, internal pull-up | hook switch, normally-closed contact 2 (switch to ground) |
| 22 | input, internal pull-up | hook switch, normally-open contact (switch to ground) |
| 23 | input, internal pull-up | left button (switch to ground) |
| 24 | input, internal pull-up | right button (switch to ground) |
| 25 | output | MOSFET switch for the PAM8403 (high = amplifier on) |

The same pins are in `software/judicom/config.py` (`HOOK_NC_PINS`, `HOOK_NO_PINS`, `BUTTON_PINS`, `AMP_PIN`) and
`software/tools/gpio_test.py`. Never drive a switch pin high: it is wired to ground.

## Audio paths

```text
Merlin handset receiver  <-  USB sound adapter (green socket)  <-> Pi 3 A+  (via the USB hub)
Merlin handset electret  ->  USB sound adapter (pink socket)
Pi 3 A+ analog 3.5 mm output -> PAM8403 amplifier -> ringtone speaker
GPIO 25 (high = on) -> MOSFET switch for the PAM8403: the phone switches the amplifier on only while the speaker plays
```

The handset's green and white wires go to its receiver (earpiece), the black and red to the electret microphone that replaced
the original (the Merlin's own microphone is not an electret and was cut out).

The Pi's analog jack is a four-pole A/V connector; confirm the correct audio contacts using the Pi's documented pinout or a
known-compatible breakout. Do not short stereo outputs together to form mono; use software mono routing or an appropriate
summing network.

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
- Account for the Pi 3 A+ port locations (and the USB hub), power distribution, strain relief, handset cradle, and service access before final print.

## Validation checklist

- [x] Identify the Merlin handset's wiring (green/white receiver, black/red microphone).
- [x] Determine microphone type and bias (replaced with an electret, biased by the USB adapter).
- [x] Test clean, full-duplex USB handset audio under ALSA.
- [x] Test independent ringtone routing through the analog output and the PAM8403.
- [ ] Measure operating and peak 5 V current draw with display, Pi, amplifier, and button LEDs. (On 2026-11-10 the Pi reported
      that under-voltage and throttling had occurred since boot: `vcgencmd get_throttled` = `0x50000`.)
- [x] GPIO pins and switch logic (above).
- [ ] LED resistors/drivers for the buttons, and boot behavior of GPIO 25 (see "Ringer amplifier switch").
- [ ] Confirm final FreeCAD dimensions, mounting holes, and cable clearances.

Record measured pinouts and wiring diagrams here once validated; do not substitute assumed values.
