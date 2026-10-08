# State

Last updated: 2026-10-07, by the setup session. Rewrite this file at every handoff point listed in CLAUDE.md.

## Active task

**M0.1 Inventory and fixtures.** Not started. No product code exists.

- Changed paths: the harness itself (all files in the repo), uncommitted. It is checkpoint C0.
- Unresolved findings: none.
- Running jobs: none.
- Next command: `ssh robot 'sudo systemctl disable --now l6-robot.service memory-robot-clock.service; sudo nvpmodel -q --verbose | grep -i -E "MAXN|POWER_MODEL"'`, then switch to MAXN_SUPER.

## Robot access

- `ssh robot` works with a key (Host entry in `~/.ssh/config`: `qdrant-robot.local`, user `qdrant`). Passwordless sudo works. Fallback, only when Dylan plugs in the debug USB-C cable: the serial console at `/dev/cu.usbmodem*`, 115200 baud, user `qdrant`, password in `.env`. The cable is unplugged as of 2026-10-07; SSH, sudo, and internet were verified without it.
- Network: Wi-Fi on the home LAN ("FBI surveillance van #4", autoconnect, 192.168.1.238 by DHCP). The course robot's `l6-hotspot` is set to not autoconnect. Ethernet has link but no DHCP lease. Never re-enable the hotspot over SSH.

## Robot facts (quick inventory, 2026-10-07)

- L4T R39.2.0, Ubuntu 24.04.4, Python 3.12.3, headless (`multi-user.target`), Docker installed, `uv` at `~/.local/bin/uv`. `nvcc` is not on PATH; find CUDA and TensorRT versions in M0.1.
- **Power mode is 15W, not MAXN_SUPER.** Switch it in M0.1 before any benchmark.
- RAM 7,485 MB total; 4,441 MB available while `l6-robot.service` runs. 8 GB swap file on NVMe. NVMe 233 GB, 162 GB free.
- Audio in: the camera has a microphone (`Arducam 1080P Low Light`, ALSA card 0). Audio out: HDMI and I2S only, so play answers on the Mac until a USB speaker is attached.
- Old services still running: `l6-robot.service` (the course robot, from `~/Documents/github/l6-robot`) and `memory-robot-clock.service`. Stop and disable both before benchmarks. Old memory backups in `~` (`edge-data.bak-20260812`, `edge-data-backup-2026-08-20.tgz`): keep them.

## Git

Standing approval to commit and push (see CLAUDE.md). Remote: `origin` = github.com/Dylancouzon/qdrant-robot (private), branch `main`.

## Checkpoints

- C0: the harness (CLAUDE.md, STATE.md, DECISIONS.md, research/, gates/, tools/gate.py, .claude/agents/, .gitignore). Reviewed by Codex gpt-6.1-sol and the review gate.

## Unmet targets

All targets in CLAUDE.md are unmeasured.

## Milestones and acceptance

| ID | Milestone | Acceptance |
| --- | --- | --- |
| M0 | Feasibility | One integrated loop (speech in, camera, VLM, TTS, one Edge shard) runs on the Jetson for 30 minutes; stack and memory budget recorded with evidence; Edge 0.8.0 checks saved; Astra gate passed |
| M1 | Talk about now | Spoken questions get spoken answers on the Jetson; "What do you see?" uses the current frame; basic Qdrant knowledge shard answers "What is Qdrant Edge?"; latency per stage logged |
| M2 | Remember | Conversation moves to the memory shard and returns through `remember`; frames stored on change with image and text vectors; "What did I show you?" and "What was on your left?" pass dev fixtures; restart keeps memory |
| M3 | People | "Do you remember me?" works; faces stored only after the visitor agrees, as a multivector with MaxSim; "forget me" deletes and shows the count; zero false identity claims on stranger fixtures |
| M4 | Booth-ready | Held-out `eval/` at target; all CLAUDE.md targets met; dashboard on a separate screen; offline cold start; deletion checks; 8-hour active run with no restart |
| M5 | Add-on | Offline Wikipedia knowledge shard, only if every M4 target still holds |

## M0 tasks

- [ ] **M0.1 Inventory and fixtures.** Record access, JetPack and library versions, services, audio devices, camera orientation, power mode (want MAXN_SUPER), free RAM, swap, storage. Draft the `eval/` dev and held-out fixture plan for all five capabilities, and the scripted-session format (see "Testing without a human" in CLAUDE.md).
- [ ] **M0.2 LLM pick.** Compare Qwen3-VL-2B and Cosmos-Reason2-2B with one runtime (llama.cpp CUDA first; TensorRT Edge-LLM if latency or memory justifies the build cost). Add Gemma 4 E2B only if its measured memory fits. Qwen3.5-0.8B is the memory fallback. Try 4B models only if 2B answer quality misses.
- [ ] **M0.3 Thin loop.** One process: VAD and ASR (WhisperTRT or Moonshine v2 streaming), current frame, VLM, streaming TTS (Kokoro; Piper only if needed), one Edge shard. Inputs from live devices or files; the Mac client streams mic audio in and plays answers. Run it on the Jetson and replay one scripted session end to end.
- [ ] **M0.4 Soak.** Run the loop for 30 minutes with `tegrastats`. Bound context, image tokens, output tokens, and memory growth.
- [ ] **M0.5 Edge checks.** On 0.8.0 on the Jetson: fusion, multivector MaxSim, persistence across restart, calls from two threads. Save them as runnable checks.
- [ ] **M0.6 Decide.** Write the stack and memory budget to `DECISIONS.md`, then run `tools/gate.py milestone "M0"`.

## Facts from Dylan (2026-10-07)

- No speaker on the Jetson yet; the camera's microphone is on the Jetson. The Mac's microphone and speaker are also available.
- Gemma license accepted on Hugging Face; the token is on the Mac (`~/.cache/huggingface/token`).
- Persona and voice: free choice.
- Dylan is near the robot on 2026-10-08 for human tests.
