# State

Last updated: 2026-10-08 01:10, by the lead (overnight session). Rewrite, do not append.

## Active task

**M1.3 Decision run** is next. M1.2 vertical slice is done (review PASS `reviews/20261008-020746-59698-review.md`).

- Reviews: design `reviews/20261008-004127-86650-design.md` and `reviews/20261008-014824-42570-design.md` (GO WITH CHANGES, applied); task review rounds `reviews/20261008-0142*`, `-0147*`, `-0152*` (FIX, fixed or rejected in D25).
- Pipeline: Silero VAD and Parakeet TDT 0.6B v2 int8 on the CPU (D24, provisional until real voices, D26); Qwen3-VL-2B on llama-server with a kept-warm frame prefix; retrieval in code (knowledge shard, captioned frame memory in Edge); Kokoro on ORT CUDA with early first phrases.
- Latest replay (`bench/results/2026-10-08-replay-1791439664.jsonl`, 12 spoken turns): 10/12, recall evidence 2/2; p50 from end of speech: line 0.39 s, transcript 0.66 s, first token 0.81 s, first phrase 1.17 s, first synthesized audio 1.72 s (max 1.97 s).
- Failures: 2B trusts its own previous answer over the frame (scene change) and skips a greeting; Qwen3-VL-4B passes both but is about 1 s slower at 15W. Keyword scoring is weak: build a larger judged dev set before choosing (D26).
- Next: M1.3 decision run with an expanded, judged dev set (2B against 4B), Kokoro TensorRT (needs ONNX shape inference), and a Mac live client.
- Next command: write `eval/dev/sessions.jsonl` additions (20 or more mixed turns) and a judge, then `scratchpad replay` for 2B and 4B.

## Robot access

- `ssh robot` works with a key (Host entry in `~/.ssh/config`: `qdrant-robot.local`, user `qdrant`). Passwordless sudo works. Internet works.
- Serial fallback only when Dylan plugs in the debug USB-C cable (unplugged now): `/dev/cu.usbmodem*`, 115200 baud, user `qdrant`, password in `.env`.
- Network: Wi-Fi on the home LAN ("FBI surveillance van #4", 192.168.1.238 by DHCP). The course robot's `l6-hotspot` does not autoconnect. Never re-enable the hotspot over SSH.
- Workflow: `tools/jetson.py deploy | run NAME [--wait] -- ARGS | collect | rollback`. Releases in `/home/qdrant/qdrant-robot/releases/<hash>`, `current` and `previous` symlinks; models, memory, results, llama.cpp in `shared/`. Models: `python -m tools.models` verifies `models.json`.

## Robot facts (2026-10-08)

- L4T R39.2.0, Ubuntu 24.04.4, Python 3.12.3, headless. CUDA 13.2.2, cuDNN 9.20, TensorRT 10.16.2 from apt. llama.cpp 9c2e0e4 built with `GGML_CUDA_NO_VMM=ON` in `shared/src/llama.cpp`. Details: `research/stack.md`.
- Power: 15W (current) and 7W only; the board was flashed without Super. 15 minutes of GPU load in the enclosure peaked at 59.9 °C with no throttling.
- RAM 7,485 MB; about 6,000 MB available idle (services trimmed, D20). Qwen3-VL-2B server leaves about 4,100 MB. 8 GB swap file. NVMe about 130 GB free.
- Camera: mounted upside down, frames rotated 180° in `robot/camera.py`; 15 fps at 1280x720 MJPG measured during a build. Microphone: the camera's (ALSA `plughw:CARD=Light`). No speaker: answers are saved as WAVs.
- Services: `l6-robot.service` stopped and disabled, backed up in `shared/legacy/` (D18); `memory-robot-clock.service` kept. Course robot memory backups stay in `~`.

## Git

Standing approval to commit and push (CLAUDE.md). Remote `origin` = github.com/Dylancouzon/qdrant-robot (private), branch `main`.

## Checkpoints

- C0, C1: harness and architecture rethink.
- C2: M1.1 stack qualification (review PASS `reviews/20261008-010719-8012-review.md`).
- C3: M1.2 vertical slice (review PASS `reviews/20261008-020746-59698-review.md`).

## Unmet targets

All CLAUDE.md targets unmeasured at acceptance scale. Interim (dev, 12 turns, no speaker): first synthesized audio 1.72 s p50 against the 1.2 s final target; decode 22 tok/s against 30 tok/s (15W caps the GPU at 625 MHz).

## Milestones and acceptance

Each milestone ends with a robot a visitor can use. Interim numbers are proposed targets (D16); the final targets are in CLAUDE.md.

| ID | Milestone | Visitor experience and acceptance |
| --- | --- | --- |
| M1 | It talks | Answers questions about the current camera view and about Qdrant aloud, on the Jetson alone. 90% correct or more; audio latency 2 s median, 4 s p95 or better; 30 minutes without restart |
| M2 | It remembers | Recalls removed objects, left and right observations, and evicted conversation, including after a restart. 90% per capability; Edge search 10 ms p99; M1 speech targets held |
| M3 | It knows you | Enrolls a face with consent, recognizes returning visitors (face multivector, MaxSim), handles a new visitor replacing the last, forgets on request. 90% known-person recognition; zero false identities on held-out strangers |
| M4 | Booth-ready | Every capability offline with Jetson-connected audio for eight hours. Final CLAUDE.md targets: 1.2 s p50 and 2 s p95 audible latency, 15 fps tracking while talking, 500 MB headroom with no swap, held-out eval at target |
| M5 | Add-on | Offline Wikipedia knowledge shard, only if every M4 target still holds |

## M1 tasks

- [x] **M1.1 Stack qualification.** Done 2026-10-08 except Super mode (needs Dylan).
- [x] **M1.2 Vertical slice.** Done 2026-10-08 (C3).
- [ ] **M1.3 Decision run.** 20 mixed turns on the Jetson; pass: 18 or more correct, no swap, 1 GB headroom.
- [ ] **M1.4 It talks.** Knowledge shard and current-camera questions to M1 acceptance, with dev fixtures and scored replays. Knowledge shard is built (`knowledge/build.py`, Qdrant v1.19.0 server snapshot restored into Edge 0.8.0).
- [ ] **M1.5 Milestone gate.**

## Human checklist for 2026-10-08 (Dylan at the robot)

1. **Super mode (decision and presence needed).** Option A: on-device UEFI capsule `TEGRA_BL_3767_super.Cap` (NVIDIA package, unofficial switch procedure, needs a reboot; if boot fails, recovery needs an x86 Ubuntu host). Option B: NVIDIA's QSPI-only flash from an x86 Ubuntu host in recovery mode. Expected: GPU 625 to 1,020 MHz, EMC 2,133 to 3,199 MHz, roughly 1.5x decode. Back up the NVMe first. Thermal headroom exists (59.9 °C peak at 15W).
2. **Audio hardware (spending).** A USB speaker and a close-talk USB microphone for the booth. The Jetson has no analog audio out.
3. Record 20 real spoken questions (the `eval/dev/brain.jsonl` texts) on the camera mic and on the Mac.
4. Show five personal objects to the camera with their names.
5. Calibrate the scene-change threshold (`SCENE_CHANGE` in `robot/main.py`) on a lit, static scene; tonight's frames were dark.

## Facts from Dylan

- The Mac's microphone and speaker may be used during development; the camera microphone is on the Jetson.
- Gemma license accepted on Hugging Face; the token is on the Mac (`~/.cache/huggingface/token`).
- Persona and voice: free choice. Room lights may be off at night; a light is left on tonight.
- 2026-10-07 night: "Don't stop at good"; targets are a floor; keep improving models and capabilities overnight.
