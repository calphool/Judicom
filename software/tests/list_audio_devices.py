#!/usr/bin/env python3
"""
list_audio.py - enumerate every audio device on the Judicom's Raspberry Pi.
 
Run:   python3 list_audio.py            list everything
       python3 list_audio.py --probe    also test which sample rates / channel counts each device accepts
 
It looks at the system two ways, so you can see whether a problem is in ALSA (the OS) or in the Python layer:
  1. ALSA itself: /proc/asound/cards, aplay -l, arecord -l  (no Python audio library needed)
  2. PortAudio, through the `sounddevice` package (or `pyaudio` if that is what you have)
 
Install the Python side if it is missing:
       sudo apt install python3-sounddevice        (also pulls in libportaudio2)
   or  sudo apt install libportaudio2 && pip install sounddevice
"""
import os
import shutil
import subprocess
import sys
 
PROBE = "--probe" in sys.argv
RATES = (8000, 16000, 22050, 44100, 48000)
 
 
def heading(text):
    print("\n" + "=" * 78 + "\n" + text + "\n" + "=" * 78)
 
 
def run(cmd):
    """Run a command, return its output (or a short note if it is missing / fails)."""
    if shutil.which(cmd[0]) is None:
        return "(%s not installed)" % cmd[0]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return (out.stdout + out.stderr).strip() or "(no output)"
    except Exception as exc:                        # noqa: BLE001 - this is a diagnostic tool
        return "(%s failed: %s)" % (" ".join(cmd), exc)
 
 
def alsa():
    heading("1. ALSA (what the operating system sees)")
    print("--- /proc/asound/cards ---")
    try:
        with open("/proc/asound/cards") as fh:
            print(fh.read().strip() or "(empty - no sound cards)")
    except OSError as exc:
        print("(cannot read: %s)" % exc)
    print("\n--- aplay -l  (playback devices) ---")
    print(run(["aplay", "-l"]))
    print("\n--- arecord -l  (capture devices) ---")
    print(run(["arecord", "-l"]))
    print("\n--- USB audio devices (lsusb) ---")
    usb = run(["lsusb"])
    keep = [ln for ln in usb.splitlines() if any(k in ln.lower() for k in ("audio", "sound", "mic", "headset", "c-media", "usb pnp"))]
    print("\n".join(keep) if keep else "(no obvious audio device by name; full list below)\n" + usb)
    print("\nDefault ALSA PCM names, if configured: ", end="")
    for path in (os.path.expanduser("~/.asoundrc"), "/etc/asound.conf"):
        print("\n  %s %s" % (path, "exists" if os.path.exists(path) else "not present"), end="")
    print()
 
 
def probe_sd(sd, index, ch_in, ch_out):
    ok_in, ok_out = [], []
    for rate in RATES:
        if ch_in:
            try:
                sd.check_input_settings(device=index, channels=1, samplerate=rate)
                ok_in.append(rate)
            except Exception:                       # noqa: BLE001
                pass
        if ch_out:
            try:
                sd.check_output_settings(device=index, channels=1, samplerate=rate)
                ok_out.append(rate)
            except Exception:                       # noqa: BLE001
                pass
    return ok_in, ok_out
 
 
def with_sounddevice():
    try:
        import sounddevice as sd
    except Exception as exc:                        # noqa: BLE001
        print("sounddevice not available (%s)" % exc)
        return False
    heading("2. PortAudio via sounddevice %s" % getattr(sd, "__version__", ""))
    print("PortAudio:", sd.get_portaudio_version()[1])
    apis = sd.query_hostapis()
    print("Host APIs:", ", ".join("%d=%s" % (i, a["name"]) for i, a in enumerate(apis)))
    try:
        din, dout = sd.default.device
    except Exception:                               # noqa: BLE001
        din = dout = None
    print("Default input device index: %s    Default output device index: %s\n" % (din, dout))
    print("%-4s %-46s %-6s %-4s %-4s %-8s %s" % ("idx", "name", "api", "in", "out", "def.rate", "flags"))
    print("-" * 90)
    for i, d in enumerate(sd.query_devices()):
        flags = []
        if i == din:
            flags.append("DEFAULT-IN")
        if i == dout:
            flags.append("DEFAULT-OUT")
        print("%-4d %-46s %-6s %-4d %-4d %-8d %s" % (
            i, d["name"][:46], apis[d["hostapi"]]["name"][:6], d["max_input_channels"], d["max_output_channels"],
            int(d["default_samplerate"]), " ".join(flags)))
        if PROBE:
            ok_in, ok_out = probe_sd(sd, i, d["max_input_channels"], d["max_output_channels"])
            if d["max_input_channels"]:
                print("       mono input rates accepted : %s" % (ok_in or "none"))
            if d["max_output_channels"]:
                print("       mono output rates accepted: %s" % (ok_out or "none"))
    return True
 
 
def with_pyaudio():
    try:
        import pyaudio
    except Exception as exc:                        # noqa: BLE001
        print("pyaudio not available (%s)" % exc)
        return False
    heading("2. PortAudio via pyaudio")
    pa = pyaudio.PyAudio()
    try:
        try:
            print("Default input :", pa.get_default_input_device_info()["name"])
        except Exception:                           # noqa: BLE001
            print("Default input : none")
        try:
            print("Default output:", pa.get_default_output_device_info()["name"])
        except Exception:                           # noqa: BLE001
            print("Default output: none")
        print("\n%-4s %-46s %-4s %-4s %s" % ("idx", "name", "in", "out", "def.rate"))
        print("-" * 70)
        for i in range(pa.get_device_count()):
            d = pa.get_device_info_by_index(i)
            print("%-4d %-46s %-4d %-4d %d" % (i, d["name"][:46], d["maxInputChannels"], d["maxOutputChannels"], int(d["defaultSampleRate"])))
            if PROBE:
                for kind, chans in (("input", d["maxInputChannels"]), ("output", d["maxOutputChannels"])):
                    if not chans:
                        continue
                    good = []
                    for rate in RATES:
                        try:
                            kw = dict(rate=rate, channels=1, format=pyaudio.paInt16)
                            ok = pa.is_format_supported(input_device=i, **kw) if kind == "input" else pa.is_format_supported(output_device=i, **kw)
                            if ok:
                                good.append(rate)
                        except Exception:           # noqa: BLE001
                            pass
                    print("       mono %s rates accepted: %s" % (kind, good or "none"))
    finally:
        pa.terminate()
    return True
 
 
def main():
    alsa()
    if not with_sounddevice():
        if not with_pyaudio():
            heading("2. PortAudio")
            print("Neither sounddevice nor pyaudio could be imported.  Install one:")
            print("    sudo apt install python3-sounddevice")
            print("The ALSA section above does not need either of them.")
    print("\nTip: the number to use in code is the 'idx' column (or the device name, which survives reboots better than the index).")
 
 
if __name__ == "__main__":
    main()
