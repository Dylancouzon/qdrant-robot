# State

Last updated: 2026-10-08 01:10, by the lead (overnight session). Rewrite, do not append.

## Active task

**M1.3 Decision run**: not met. Branch `spike/m1-3-quality` (pushed, review PASS `reviews/20261008-084259-59432-review.md`); `main` still at the M1.2 commit d998162. Merge to `main` after M1.3 passes.

- Latest dev run in MAXN_SUPER (`bench/results/2026-10-08-replay-1791463902.judged.jsonl`, synthetic voices): 41/47 judged (87%), speech 46/47; p50 from end of speech: transcript 0.73 s, first token 0.82 s, first phrase 1.04 s, first synthesized audio 1.47 s. Oracle (exact text) 41/47: the brain, not ASR, limits quality. Held-out baseline 15/26 at 15W (D29).
- Real voices recorded by Dylan 2026-10-08: `eval/dev/audio-real/` (47) and `eval/heldout/audio-real/` (26), fifine USB mic on the Mac.
- Next, in order:
  1. Real-voice runs: `python3 eval/run.py --audio audio-real`, then `python3 eval/run.py eval/heldout/sessions.jsonl --audio audio-real` (held-out use 2: count it in DECISIONS).
  2. MAXN thermal test (15 minutes of load in the enclosure, like the 15W one; the detector run peaked at 66.3 °C).
  3. Integrate the detector: branch `spike/detector` (4b6032e, builder report in `research/detector.md` there): YOLOE-26n booth vocabulary on raw TensorRT FP16, 15 fps with LLM decoding at 31.7 tok/s. Design gate first (`research/m2-design.md` needs the detector numbers and Dylan's naming and forgetting features), then object memory with exact regions, detections as grounding lines for the VLM, crops for SigLIP 2 later. Review the builder's diff before merging (the lead read `robot/detect.py`; it looked sound).
  4. LoRA fine-tune of Qwen3-VL-2B (counsel and researcher: text-only LoRA, merge, convert with llama.cpp, Q4_K_M, keep the mmproj) on Dylan's 3080 machine (32 GB RAM): needs its OS and SSH access from Dylan. The same machine enables TensorRT Edge-LLM INT4 builds and is a recovery host for the Jetson.
- Open for Dylan: three judge rulings (see Human checklist); audio hardware purchase (approved).
- Running jobs: none. caffeinate runs on the Mac.

## Robot access

- `ssh robot` works with a key (Host entry in `~/.ssh/config`: `qdrant-robot.local`, user `qdrant`). Passwordless sudo works. Internet works.
- Serial fallback only when Dylan plugs in the debug USB-C cable (unplugged now): `/dev/cu.usbmodem*`, 115200 baud, user `qdrant`, password in `.env`.
- Network: Wi-Fi on the home LAN ("FBI surveillance van #4", 192.168.1.238 by DHCP). The course robot's `l6-hotspot` does not autoconnect. Never re-enable the hotspot over SSH.
- Workflow: `tools/jetson.py deploy | run NAME [--wait] -- ARGS | collect | rollback`. Releases in `/home/qdrant/qdrant-robot/releases/<hash>`, `current` and `previous` symlinks; models, memory, results, llama.cpp in `shared/`. Models: `python -m tools.models` verifies `models.json`.

## Robot facts (2026-10-08)

- L4T R39.2.0, Ubuntu 24.04.4, Python 3.12.3, headless. CUDA 13.2.2, cuDNN 9.20, TensorRT 10.16.2 from apt. llama.cpp 9c2e0e4 built with `GGML_CUDA_NO_VMM=ON` in `shared/src/llama.cpp`. Details: `research/stack.md`.
- Power: MAXN_SUPER since 2026-10-08 08:36 (D31: bootloader slot B, `/etc/nvpmodel.conf` links the Super profile, `nvpmodel -m 2`): GPU 1,020 MHz, EMC 3,199 MHz, CPU 1,728 MHz. Qwen3-VL-2B decode 36.0 tok/s, prefill 1,492 tok/s (`bench/results/2026-10-08-llama-bench-maxn-super.jsonl`). The 15W thermal test peaked at 59.9 °C; a MAXN thermal test is pending.
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

All CLAUDE.md targets unmeasured at acceptance scale. Interim (dev, 47 turns, no speaker, 15W): first synthesized audio 1.56 to 1.63 s p50 against the 1.2 s final target (not yet re-measured in MAXN_SUPER). Decode now 36.0 tok/s, which meets 30 tok/s. Held-out answers 15/26 (D29).

## Milestones and acceptance

Each milestone ends with a robot a visitor can use. Interim numbers are proposed targets (D16); the final targets are in CLAUDE.md.

| ID | Milestone | Visitor experience and acceptance |
| --- | --- | --- |
| M1 | It talks | Answers questions about the current camera view and about Qdrant aloud, on the Jetson alone. 90% correct or more; audio latency 2 s median, 4 s p95 or better; 30 minutes without restart |
| M2 | It remembers | Recalls removed objects, left and right observations, and evicted conversation, including after a restart. Dylan (2026-10-08): name a specific object by voice ("this is my phone": several crops as one multivector point, MaxSim) and recall it by that name, labels shown on the video view, "forget my phone" deletes it, "ignore the chair" stops remembering it. 90% per capability; Edge search 10 ms p99; M1 speech targets held |
| M3 | It knows you | Enrolls a face with consent, recognizes returning visitors (face multivector, MaxSim), handles a new visitor replacing the last, forgets on request. 90% known-person recognition; zero false identities on held-out strangers |
| M4 | Booth-ready | Every capability offline with Jetson-connected audio for eight hours. Final CLAUDE.md targets: 1.2 s p50 and 2 s p95 audible latency, 15 fps tracking while talking, 500 MB headroom with no swap, held-out eval at target |
| M5 | Add-on | Offline Wikipedia knowledge shard, only if every M4 target still holds |

## M1 tasks

- [x] **M1.1 Stack qualification.** Done 2026-10-08 except Super mode (needs Dylan).
- [x] **M1.2 Vertical slice.** Done 2026-10-08 (C3).
- [ ] **M1.3 Decision run.** In review: dev 35/39 judged, no swap, 1,886 MB headroom (D27, D28).
- [ ] **M1.4 It talks.** Knowledge shard and current-camera questions to M1 acceptance, with dev fixtures and scored replays. Knowledge shard is built (`knowledge/build.py`, Qdrant v1.19.0 server snapshot restored into Edge 0.8.0).
- [ ] **M1.5 Milestone gate.**

## Human checklist (2026-10-08, Dylan present)

1. Super mode: done (D31).
2. Audio hardware: approved. Get a directional dynamic USB microphone for the booth and any small USB speaker; meanwhile use the Mac through `tools/talk.py`.
3. Real voices: recorded (47 dev, 26 held-out).
4. Judge rulings pending: held-out "sunny, no snow", "chicken, rice, vegetables, not stir fry", dev "stuffed animals for teddy bears".
5. The 3080 machine (32 GB): OS and SSH access needed for LoRA training and TensorRT Edge-LLM INT4 builds.
6. Calibrate `SCENE_CHANGE` on a lit, static scene.
7. Camera: the USB hub disabled its port once after the Super reboot ("EMI?"); Dylan moved it to another port, capture works (16.2 fps). Watch for recurrence (D32).

## Facts from Dylan

- The Mac's microphone and speaker may be used during development; the camera microphone is on the Jetson.
- Gemma license accepted on Hugging Face; the token is on the Mac (`~/.cache/huggingface/token`).
- Persona and voice: free choice. Room lights may be off at night; a light is left on tonight.
- 2026-10-07 night: "Don't stop at good"; targets are a floor; keep improving models and capabilities overnight.
