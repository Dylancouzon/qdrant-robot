#!/usr/bin/env python3
"""Turn the "say" text of fixture cases into 16 kHz mono WAVs with macOS `say` (Mac only).

    eval/make_wavs.py eval/dev/brain.jsonl     writes eval/dev/audio/<id>.wav, skips existing
    eval/make_wavs.py eval/dev/sessions.jsonl  the same for every "say" step of each session
    eval/make_wavs.py eval/heldout/sessions.jsonl --voices heldout   voices the dev set never uses
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

# Several synthetic voices, rotated per case; real recorded voices join them later.
VOICES = {"dev": ["Samantha", "Daniel", "Karen", "Moira", "Rishi", "Fred", "Kathy", "Ralph",
                  "Grandpa (English (US))"],
          "heldout": ["Eddy (English (US))", "Flo (English (UK))", "Reed (English (US))",
                      "Sandy (English (UK))", "Rocko (English (US))", "Shelley (English (US))"]}
# How people say it; `say` mispronounces the written name.
SPOKEN = {"Qdrant": "quadrant"}


def main(cases: Path, voices: list[str], out: Path | None = None) -> None:
    out = out or cases.parent / "audio"
    out.mkdir(parents=True, exist_ok=True)
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
            subprocess.run(["say", "-v", voices[k % len(voices)], "-o", aiff, text],
                           check=True, timeout=60)
            subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1",
                            aiff, wav], check=True, timeout=60)
        print(wav)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("cases", type=Path)
    p.add_argument("--voices", choices=VOICES, default="dev")
    p.add_argument("--output-dir", type=Path)
    a = p.parse_args()
    main(a.cases, VOICES[a.voices], a.output_dir)
