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
| Physical controls | Two square photo arcade buttons (33 mm lip, 27 mm square collar, a 21 × 21 mm photo under a clear cap), shortened to 3 mm travel with printed parts and pressing a BLEE microswitch each; on GPIO 23 (left) and 24 (right). Not lit (an LED could be fitted in each later) | In use |
| Hook switch | BIS-10 switch (37 × 29 × 14 mm) in a printed holder under the cradle; three contacts: two normally closed (GPIO 17, 27) and one normally open (GPIO 22); the three vote | In use |
| Handset | Vintage AT&T Merlin handset; its original microphone replaced with an electret capsule | In use |
| Handset audio | C-Media USB audio adapter (Unitek Y-247A, `0d8c:0014`), ALSA card `Device`; mono mic | In use |
| Ringtone speaker | 4 Ω, 3 W speaker, about 52 mm square; on four standoffs behind a grille in the right side wall | In use |
| Ringtone amplifier | PAM8403 (class-D) module driven from the Pi's 3.5 mm analog output (ALSA card `Headphones`), switched by GPIO 25 | In use |
| Microphone prototype | INMP441 I²S microphone | Not used by the phone; its overlay (`dtoverlay=inmp441`) is still in `config.txt`, so it still appears as an ALSA capture card |
| Enclosure | Custom 3D-printed, bolt-together enclosure: `hardware/freecad/enclosure/judicom_freecad_macro.py` builds `Judicom.FCStd` and the STLs | In development |
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

From `hardware/freecad/enclosure/judicom_freecad_macro.py`, which builds `Judicom.FCStd`; the macro is the source, so change
dimensions there.  Its header lists the measurements that are still assumed ("Things I could NOT take from your drawings").

- Body: about **230 wide × 203 deep × 160 tall**; the front is a 35° slope, 248 mm long (so the Panel prints flat on a
  256 mm bed), above an 18 mm vertical front face.
- Screen window in the Panel: **87 × 154 mm** (across × along the slope), finished by the press-in ScreenBezel.
- Buttons: two **27 × 27 mm** square holes, **10 mm apart** (centres **37 mm** apart, which `BUTTON_X` in
  `software/judicom/config.py` matches), 20 mm below the screen window and 12 mm from the front edge of the slope.
  The buttons' long barrels and springs are replaced by printed parts (ButtonSlider ×2, ButtonBracket, ButtonBarDirect): 3 mm travel,
  the microswitch body is the hard stop.  BLEE switch size and hole spacing (27 × 15.9 × 10.3 mm, holes 22.2 × 10.3 mm apart) are
  taken from a photo, not measured.
- Speaker: four standoffs on a **42 mm** square (the speaker's ear holes), M3 inserts; the 52 mm frame and the magnet are estimated.
- Pi 3 A+: snaps onto the four posts of the PiCradle, which is glued to the BottomPlate.
- Account for the Pi 3 A+ port locations (and the USB hub), power distribution, strain relief, and service access before final print.

## Validation checklist

- [x] Identify the Merlin handset's wiring (green/white receiver, black/red microphone).
- [x] Determine microphone type and bias (replaced with an electret, biased by the USB adapter).
- [x] Test clean, full-duplex USB handset audio under ALSA.
- [x] Test independent ringtone routing through the analog output and the PAM8403.
- [ ] Measure the 5 V at the Pi (GPIO header pins 2/4 and 6) while the handset is lifted and while it rings. On the evening of
      2026-11-09 the kernel logged 27 "Undervoltage detected!" dips, each lasting 4-7 s (`journalctl -k | grep -i voltage`).
      In the latest boot every one came 1-2 s after the handset was lifted (dial tone starting on the USB adapter) or the
      ringer started; nothing in the 14 idle hours after that. The supply is rated 5.5 V / 6 A, so the loss is probably
      between the supply and the Pi, or the supply sagging when a load switches on.
- [x] GPIO pins and switch logic (above).
- [ ] Boot behavior of GPIO 25 (see "Ringer amplifier switch").
- [ ] Confirm final FreeCAD dimensions, mounting holes, and cable clearances.

Record measured pinouts and wiring diagrams here once validated; do not substitute assumed values.
