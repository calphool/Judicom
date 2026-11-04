#!/bin/bash
# Makes the two messages callers hear (as 8 kHz mono WAV for Asterisk) from protected.txt and unavailable.txt, with the Piper
# text-to-speech voice en_US-lessac-medium.  The contact number is given on the command line, so it is not kept in git:
#
#     bash make_prompts.sh 312-555-0123          -> judicom-protected.wav, judicom-unavailable.wav in this folder
#
# Needs ffmpeg, and Piper in a Python virtual environment (made on first run in ./.tts, about 60 MB with the voice; not in git).
# Then put them on the NAS (see docs/DEPLOYMENT.md):
#     scp judicom-*.wav pi@naspi.local:/tmp/
#     ssh pi@naspi.local 'for f in /tmp/judicom-*.wav; do docker cp $f asterisk-test:/var/lib/asterisk/sounds/custom/; done'
set -euo pipefail
cd "$(dirname "$0")"
number="${1:-}"
digits="$(printf '%s' "$number" | tr -cd '0-9')"
[ ${#digits} -eq 10 ] || { echo "Give the contact number (10 digits), e.g.  bash make_prompts.sh 312-555-0123" >&2; exit 1; }
spoken="$(echo "${digits:0:1} ${digits:1:1} ${digits:2:1}, ${digits:3:1} ${digits:4:1} ${digits:5:1}, ${digits:6:1} ${digits:7:1} ${digits:8:1} ${digits:9:1}")"
command -v ffmpeg >/dev/null || { echo "ffmpeg is missing:  sudo apt install ffmpeg" >&2; exit 1; }
if [ ! -x .tts/bin/python ]; then
  python3 -m venv .tts
  .tts/bin/pip install -q piper-tts
fi
[ -f .tts/voices/en_US-lessac-medium.onnx ] || .tts/bin/python -I -m piper.download_voices --download-dir .tts/voices en_US-lessac-medium
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
sed "s/{DIGITS}/$spoken/g" protected.txt > "$tmp/protected.txt"
cp unavailable.txt "$tmp/unavailable.txt"
for n in protected unavailable; do
  .tts/bin/python -I -m piper -m .tts/voices/en_US-lessac-medium.onnx --length-scale 1.1 --sentence-silence 0.4 \
      -i "$tmp/$n.txt" -f "$tmp/$n.wav" 2>/dev/null
  ffmpeg -loglevel error -y -i "$tmp/$n.wav" -af "adelay=500,apad=pad_dur=0.5" -ar 8000 -ac 1 -c:a pcm_s16le "judicom-$n.wav"
  echo "made judicom-$n.wav"
done
