# Frozen F0e speech inputs

These63 synthetic utterances reproduce the D91 schedule, with48 scored questions and15 auxiliary statements. Generate the original visits through eval/make_wavs.py, using the heldout voice group and this separate audio directory. Rotate the six installed voices over every spoken step in schedule order. Manifest entries pin source text, voice, WAV bytes, and duration. Candidate and baseline use these exact WAVs.

The complete audio preflight passes without changing any visit time or source rubric. Synthetic inputs exercise VAD and ASR; first synthesized output remains distinct from physical audible latency. This folder is evaluator/reviewer-only and is excluded from training with all eval sources.
