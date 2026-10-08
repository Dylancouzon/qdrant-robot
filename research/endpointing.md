# Endpointing: detecting the end of a visitor's turn

As of 2026-10-07. Labels: J measured on an Orin Nano, E measured elsewhere, U unverified. Nothing here is measured on our robot yet.

## Summary

- Plan: Silero VAD with a short hangover (about 200 ms), then Pipecat Smart Turn v3.2 on the last 8 s of audio to decide "turn complete". Start the LLM speculatively on that decision and cancel it if speech resumes. Force "complete" after about 3 s of silence.
- Smart Turn v3.2: 8 MB int8, audio input, BSD-2. English accuracy 94.3%, 2.6% cut-offs, 3.1% waits too long (E). CPU time 15 to 95 ms on cloud ARM and x86 (E); expect 60 to 150 ms on our A78AE cores (U).
- Moonshine's transcriber has its own Silero-based VAD: a line ends when the mean VAD score over `vad_window_duration` (default 0.5 s) drops to `vad_threshold` (0.5), about 0.25 s of effective hangover (U). Its "end of line latency" goal is under 200 ms after that decision (E).
- Booth noise: raise the VAD threshold to 0.7 to 0.8, require about 250 ms of speech, gate on volume, and use a close-talk microphone. No source tests these against babble; record real booth noise and measure false triggers.
- LiveKit's preemptive generation publishes no measured gain (E). We measure our own.

## Sources

- https://github.com/pipecat-ai/smart-turn
- https://huggingface.co/pipecat-ai/smart-turn-v3
- https://docs.pipecat.ai/server/utilities/audio/silero-vad-analyzer
- https://developers.openai.com/api/docs/guides/realtime-vad
- https://docs.livekit.io/agents/logic/turns/turn-detector/
- https://moonshine-voice.readthedocs.io/en/latest/api/options/
- https://github.com/moonshine-ai/moonshine/blob/main/core/voice-activity-detector.cpp
