#!/usr/bin/env python3
"""Turn the "say" text of fixture cases into 16 kHz mono WAVs with macOS `say` (Mac only).

    eval/make_wavs.py eval/dev/brain.jsonl     writes eval/dev/audio/<id>.wav, skips existing
    eval/make_wavs.py eval/dev/sessions.jsonl  the same for every "say" step of each session
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

# Several synthetic voices, rotated per case; real recorded voices join them later.
VOICES = ["Samantha", "Daniel", "Karen", "Moira", "Rishi"]
# How people say it; `say` mispronounces the written name.
SPOKEN = {"Qdrant": "quadrant"}


def main(cases: Path) -> None:
    out = cases.parent / "audio"
    out.mkdir(exist_ok=True)
    records = [json.loads(line) for line in cases.read_text().splitlines()]
    says = [s for r in records for s in r.get("steps", [r]) if "say" in s]
    for k, case in enumerate(says):
        wav = out / f"{case['id']}.wav"
        if wav.exists():
            continue
        with tempfile.TemporaryDirectory() as tmp:
            aiff = Path(tmp) / "q.aiff"
            text = case["say"]
            for written, spoken in SPOKEN.items():
                text = text.replace(written, spoken)
            subprocess.run(["say", "-v", VOICES[k % len(VOICES)], "-o", aiff, text], check=True)
            subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1",
                            aiff, wav], check=True)
        print(wav)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
