#!/usr/bin/env python3
"""Live ALSA microphone meters for an SSH terminal. Ctrl+C to quit."""
import array
import math
import re
import shutil
import subprocess
import sys
import threading
import time

RATE = 16000
SAMPLES = 1024


def capture_devices():
    result = subprocess.run(['arecord', '-l'], capture_output=True, text=True, check=True)
    devices = []
    for line in result.stdout.splitlines():
        match = re.match(r'card (\d+): ([^\[]+)\[([^]]+)\], device (\d+):', line)
        if match:
            card, _, label, dev = match.groups()
            devices.append((f'plughw:{card},{dev}', label.strip()))
    return devices


def monitor(device, state, stop):
    cmd = ['arecord', '-q', '-D', device, '-t', 'raw', '-f', 'S16_LE',
           '-r', str(RATE), '-c', '1']
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        state['error'] = str(exc)
        return
    state['proc'] = proc
    try:
        while not stop.is_set():
            data = proc.stdout.read(SAMPLES * 2)
            if not data:
                details = proc.stderr.read().decode(errors='replace').strip()
                state['error'] = details or f'arecord exited ({proc.poll()})'
                break
            data = data[:len(data) // 2 * 2]
            samples = array.array('h')
            samples.frombytes(data)
            if sys.byteorder != 'little':
                samples.byteswap()
            peak = max((abs(s) for s in samples), default=0) / 32768.0
            state['peak'] = peak
            state['updated'] = time.monotonic()
    finally:
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()


def main():
    try:
        devices = capture_devices()
    except (OSError, subprocess.CalledProcessError) as exc:
        sys.exit(f'Cannot list ALSA capture devices: {exc}\nInstall alsa-utils.')
    if not devices:
        sys.exit('No ALSA capture devices found.')
    stop = threading.Event()
    states = []
    for device, name in devices:
        state = {'device': device, 'name': name, 'peak': 0.0,
                 'updated': 0.0, 'error': None, 'proc': None}
        states.append(state)
        threading.Thread(target=monitor, args=(device, state, stop), daemon=True).start()
    print('\033[?25l', end='', flush=True)
    try:
        while True:
            width = max(10, min(40, shutil.get_terminal_size((80, 24)).columns - 43))
            lines = ['Live microphone peak levels (Ctrl+C to quit)', '']
            now = time.monotonic()
            for st in states:
                label = f"{st['name'][:18]:18} {st['device']:11}"
                if st['error']:
                    lines.append(f'{label} ERROR: {st["error"].splitlines()[-1][:70]}')
                    continue
                if not st['updated']:
                    lines.append(f'{label} starting capture...')
                    continue
                peak = st['peak'] if now - st['updated'] < 1 else 0
                db = 20 * math.log10(peak) if peak > 0 else float('-inf')
                # Display dBFS on a scale from -60 dBFS to 0 dBFS.
                fill = max(0, min(width, round((db + 60) / 60 * width)))
                bar = '█' * fill + '░' * (width - fill)
                level = f'{db:5.1f} dBFS' if peak > 0 else '  -inf dBFS'
                lines.append(f'{label} {bar} {level}')
            sys.stdout.write('\033[H\033[J' + '\n'.join(lines) + '\n')
            sys.stdout.flush()
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        for st in states:
            proc = st['proc']
            if proc and proc.poll() is None:
                proc.terminate()
        print('\033[?25h', end='', flush=True)


if __name__ == '__main__':
    main()
