# Wake word

As of 2026-10-08 (researcher). Labels: J measured on an Orin Nano, E measured elsewhere, U unverified.

## Summary

- Recommendation: spot the robot's name in the Parakeet transcript of each VAD line first (no new model; Parakeet already runs at 0.22 s p50 per line, J, D24; fuzzy or phonetic aliases for mishearings); train an openWakeWord model only if that arm misses or false-triggers on booth babble.
- "Edgy" is a weak wake word at a Qdrant Edge booth: staff say "edge" all day, "edgy" is an ordinary word, and it has about three phonemes (U; Picovoice advises at least six). Candidates: "Kodiak" (6 phonemes, U), "Juniper" (6 to 7, U), "Hey Edgy" (5, U, still collides with "edge").
- openWakeWord: custom models from synthetic Piper TTS in under an hour (E); a classifier about 0.42 MB (E); 15 to 20 models in real time on one Raspberry Pi 3 core (E), under 5% of one Orin core expected (U); aim under 5% false rejects and 0.5 false accepts per hour on far-field party audio (E); Apache 2.0 code; our own trained model avoids the CC BY-NC-SA pretrained weights.
- microWakeWord: no published false-accept or false-reject numbers; training needs tuning; no gain over openWakeWord here. sherpa-onnx keyword spotter: keyword typed as text, about 3.3M parameters (U), no accuracy numbers. Porcupine: free tier ended 2026-06-30, no Linux aarch64. Silero: no public custom keyword model.

## Bake-off (both arms use the same 20 s follow-up window)

| Measure | A: name in the transcript | B: openWakeWord, custom |
| --- | --- | --- |
| False accepts per hour | 1 hour or more of recorded booth babble, with "Qdrant Edge" spoken | same audio |
| False rejects | 50 or more real utterances at 1 m with babble: name alone, name plus question | same |
| Added CPU | about zero (tegrastats) | per-frame time on one core while the VLM decodes |
| Latency to first answer word | end of speech to first audio vs today | same, plus detection to the first UI cue |

## Sources

- https://github.com/dscripka/openWakeWord
- https://github.com/dscripka/openWakeWord/blob/main/docs/models/hey_jarvis.md
- https://www.home-assistant.io/voice_control/create_wake_word/
- https://github.com/OHF-Voice/micro-wake-word
- https://esphome.io/components/micro_wake_word/
- https://k2-fsa.github.io/sherpa/onnx/kws/index.html
- https://github.com/Picovoice/porcupine
- https://community.home-assistant.io/t/fyi-picovoice-confirmed-free-tier-accesskeys-will-stop-working-after-june-30-2026/1012744
- https://picovoice.ai/docs/tips/choosing-a-wake-word/
