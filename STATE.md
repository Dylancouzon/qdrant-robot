# State

Last updated: 2026-10-07, by the setup session. The lead rewrites this file at every handoff point listed in CLAUDE.md.

## Active task

**M0.1 Inventory and stack qualification.** Not started. No product code exists.

- Changed paths: none beyond the committed harness.
- Unresolved findings: none open. The harness passed two Codex gpt-6.1-sol reviews (D8, D11); the second review's fixes are applied.
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

## Unmet targets

All targets in CLAUDE.md are unmeasured.

## Milestones and acceptance

| ID | Milestone | Acceptance |
| --- | --- | --- |
| M0 | Feasibility | Stack qualified on this L4T release; one integrated loop (speech in, camera, VLM, TTS, one Edge shard) replays a scripted session and runs 30 minutes on the Jetson; memory budget with evidence; Astra gate passed |
| M1 | Talk about now | Spoken questions get spoken answers on the Jetson; "What do you see?" uses the current frame; basic Qdrant knowledge shard answers "What is Qdrant Edge?"; latency per stage logged |
| M2 | Remember | Conversation moves to the memory shard and returns through `remember`; frames stored on change with image and text vectors; "What did I show you?" and "What was on your left?" pass dev fixtures; restart keeps memory |
| M3 | People | "Do you remember me?" works; a face is stored only after explicit consent, as a multivector with MaxSim; "forget me" deletes and shows the count; zero false identity claims on stranger fixtures |
| M4 | Booth-ready | Held-out `eval/` at target; all CLAUDE.md targets met; Jetson-connected speaker and microphone pass spoken interaction with the Mac disconnected; offline cold start; deletion checks; 8-hour active run with no restart |
| M5 | Add-on | Offline Wikipedia knowledge shard, only if every M4 target still holds |

## M0 tasks

- [ ] **M0.1 Inventory and stack qualification.**
    1. Preserve the course robot first: copy its unit files, environment, and code revision into `shared/legacy/`, then stop and disable `l6-robot.service` and `memory-robot-clock.service`.
    2. Record the GPU, driver, and which CUDA, cuDNN, and TensorRT are reachable (system packages, pip wheels, or NVIDIA L4T containers). Decide the stack path: pip wheels, JetPack apt components, or containers. A reflash to an older JetPack needs Dylan and an x86 Ubuntu host; propose it only with evidence.
    3. Power: find whether a 25W or MAXN_SUPER profile exists for this release. Run a 15-minute GPU load in the closed enclosure at each available mode, log `tegrastats` temperatures and clocks, and record throttling. If a faster mode throttles, propose cooling (a Jetson-driven fan is allowed).
    4. Draft the `eval/` fixture plan and the scripted-session format.
    5. Build the deploy, run, and collect workflow (CLAUDE.md, "Mac-to-Jetson workflow").
- [ ] **M0.2 Edge checks.** `qdrant-edge-py` 0.8.0 on the Jetson: fusion, multivector MaxSim, persistence across restart, calls from two threads, query latency. Save them as runnable checks.
- [ ] **M0.3 Runtime qualification and first VLM.** Test the TensorRT Edge-LLM 0.11.0 aarch64 Python 3.12 wheel first: native loading, image inference from Python, token streaming, one validated tool call. If it fails, use a pinned llama.cpp CUDA build for SM87 and check its multimodal Python interface. Start with Qwen3-VL-2B-Instruct INT4. Compare Cosmos-Reason2-2B, Gemma 4 E2B, or larger models only after a measured quality, latency, or memory miss. Reserve memory for detection, retrieval encoders, faces, and all shards.
- [ ] **M0.4 Thin loop.** One process: VAD and ASR, current frame, VLM, streaming TTS, one Edge shard. Qualify each speech wheel on this stack with a real GPU run; fall back to CPU Moonshine and CPU Kokoro ONNX if needed. Replay one scripted session end to end and score it.
- [ ] **M0.5 Soak.** Run the loop for 30 minutes with `tegrastats`. Bound context, image tokens, output tokens, and memory growth.
- [ ] **M0.6 Decide.** Write the stack and memory budget to `DECISIONS.md`, then run `tools/gate.py milestone "M0"`.

## Facts from Dylan (2026-10-07)

- The Mac's microphone and speaker may be used during development; the camera microphone is on the Jetson.
- Gemma license accepted on Hugging Face; the token is on the Mac (`~/.cache/huggingface/token`).
- Persona and voice: free choice.
- Room lights may be off at night.
- Dylan is near the robot on 2026-10-08 for human tests: prepare a checklist here before then.
