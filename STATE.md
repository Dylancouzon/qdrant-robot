# State

Last updated: 2026-10-07, by the setup session. The lead rewrites this file at every handoff point listed in CLAUDE.md.

## Active task

**M1.1 Stack qualification.** Not started. No product code exists.

- Changed paths: none beyond the committed harness (architecture rethink D14, milestones D16, light safety net D17).
- Unresolved findings: none open. Harness reviews in `reviews/`; owner decisions recorded in D17.
- Running jobs (last observed 2026-10-07): `l6-robot.service` and `memory-robot-clock.service`, the course robot. Refresh their status before changing them.
- Next command: `ssh robot 'systemctl status --no-pager l6-robot.service memory-robot-clock.service; sudo nvpmodel -q --verbose; df -h /; free -m'`

## Robot access

- `ssh robot` works with a key (Host entry in `~/.ssh/config`: `qdrant-robot.local`, user `qdrant`). Passwordless sudo works. Internet works.
- Serial fallback only when Dylan plugs in the debug USB-C cable (unplugged now): `/dev/cu.usbmodem*`, 115200 baud, user `qdrant`, password in `.env`.
- Network: Wi-Fi on the home LAN ("FBI surveillance van #4", autoconnect, 192.168.1.238 by DHCP). The course robot's `l6-hotspot` is set to not autoconnect. Ethernet has link but no DHCP lease. Never re-enable the hotspot over SSH.

## Robot facts (quick inventory, 2026-10-07)

- L4T R39.2.0 (a recent JetPack 7 release with a rewritten kernel; Dylan saw compatibility issues a few weeks ago), Ubuntu 24.04.4, Python 3.12.3, headless, Docker installed, `uv` at `~/.local/bin/uv`.
- **No CUDA toolkit, cuDNN, or TensorRT packages are installed system-wide** (only `nvidia-l4t-core`). The course robot got CUDA through pip wheels (torch 2.13).
- **Power modes offered: 15W (ID 0, current) and 7W (ID 1) only. No MAXN_SUPER profile.** Dylan: Super mode may need better cooling in the enclosure.
- RAM 7,485 MB total; 4,441 MB available while `l6-robot.service` runs. 8 GB swap file on NVMe. NVMe 233 GB, 162 GB free. `~/.cache` holds 8.5 GB (course robot models).
- Audio in: the camera has a microphone (`Arducam 1080P Low Light`, ALSA card 0). Audio out: HDMI and I2S only.
- Keep the course robot's memory backups in `~` (`edge-data.bak-20260812`, `edge-data-backup-2026-08-20.tgz`).

## Git

Standing approval to commit and push (see CLAUDE.md). Remote: `origin` = github.com/Dylancouzon/qdrant-robot (private), branch `main`.

## Checkpoints

- C0: the harness, committed and pushed.
- C1: architecture rethink and light safety net, committed and pushed.

## Unmet targets

All targets in CLAUDE.md are unmeasured.

## Milestones and acceptance

Each milestone ends with a robot a visitor can use. Interim numbers are proposed targets (D16); the final targets are in CLAUDE.md.

| ID | Milestone | Visitor experience and acceptance |
| --- | --- | --- |
| M1 | It talks | Answers questions about the current camera view and about Qdrant aloud, on the Jetson alone. 90% correct or more; audio latency 2 s median, 4 s p95 or better; 30 minutes without restart |
| M2 | It remembers | Recalls removed objects, left and right observations, and evicted conversation through `remember`, including after a restart. 90% per capability; Edge search 10 ms p99; M1 speech targets held |
| M3 | It knows you | Enrolls a face with consent, recognizes returning visitors (face multivector, MaxSim), handles a new visitor replacing the last, forgets on request. 90% known-person recognition; zero false identities on held-out strangers |
| M4 | Booth-ready | Every capability offline with Jetson-connected audio for eight hours. Final CLAUDE.md targets: 1.2 s p50 and 2 s p95 audible latency, 15 fps tracking while talking, 500 MB headroom with no swap, held-out eval at target |
| M5 | Add-on | Offline Wikipedia knowledge shard, only if every M4 target still holds |

## M1 tasks

- [ ] **M1.1 Stack qualification.**
    1. Preserve the course robot: copy its unit files, environment, and code revision into `shared/legacy/`, then stop and disable `l6-robot.service` and `memory-robot-clock.service`.
    2. Record the GPU, driver, and reachable CUDA, cuDNN, and TensorRT. Known for JetPack 7 (see `research/models.md`): torch from the `cu130` index, `onnxruntime-gpu` 1.24, native TensorRT 10.16 works; CUDA 12.6 builds fail or give NaN; the Ultralytics container ships TensorRT 11.2, which JetPack does not support.
    3. Power: check for a 25W or MAXN_SUPER profile on this release; run a 15-minute GPU load in the closed enclosure at each mode with `tegrastats`; record throttling; propose cooling if a faster mode throttles.
    4. Build the deploy, run, and collect workflow.
- [ ] **M1.2 Vertical slice.** Design gate first (two alternatives: Gemma 4 E2B omni, and Moonshine plus Qwen3-VL-2B). Build the thinnest robot that does one real thing: a visitor asks about an object, hears the answer, removes the object, and asks what they showed. One process, one real Edge lookup, streaming TTS. Reserve memory for the components not yet built (detector, face models, embedders) so the budget stays honest.
- [ ] **M1.3 Decision run.** 20 mixed turns on the Jetson: direct sight, one tool round trip, long speech, and repeated turns near the context limit. Pass: 18 or more correct, no swap, 1 GB headroom. Record correctness, end of speech to first playable audio, peak available RAM, swap, and detection gaps. If the brain fails, swap only its path to the fallback and keep everything else.
- [ ] **M1.4 It talks.** Knowledge shard (snapshot) and current-camera questions to M1 acceptance, with `eval/` dev fixtures and scored replays.
- [ ] **M1.5 Milestone gate.** `tools/gate.py milestone "M1"`.

## Human checklist for 2026-10-08 (Dylan at the robot)

Prepare before he arrives: record 20 real spoken questions per fixture set, show five personal objects to the camera with their names, confirm the camera microphone level, and note where a USB speaker and a fan could mount.

## Facts from Dylan (2026-10-07)

- The Mac's microphone and speaker may be used during development; the camera microphone is on the Jetson.
- Gemma license accepted on Hugging Face; the token is on the Mac (`~/.cache/huggingface/token`).
- Persona and voice: free choice.
- Room lights may be off at night.
- Dylan is near the robot on 2026-10-08 for human tests: prepare a checklist here before then.
