# State

Last updated: 2026-10-07, by the setup session. Rewrite this file at every handoff point listed in CLAUDE.md.

## Active task

**M0.1 Inventory and fixtures.** Not started. No product code exists.

- Changed paths: the harness itself (all files in the repo), uncommitted. It is checkpoint C0.
- Unresolved findings: none.
- Running jobs: none.
- Next command: `ssh -o BatchMode=yes robot true` (works once `Host robot` exists in `~/.ssh/config`). Then: `ssh robot 'cat /etc/nv_tegra_release; sudo nvpmodel -q; free -m; df -h; arecord -l; aplay -l; v4l2-ctl --list-devices'`

## Robot access

- Hostname `qdrant-robot`, Ubuntu 24.04.4 LTS (so likely JetPack 7). On 2026-10-07 it did not answer on the LAN (no SSH on 192.168.1.0/24, no 192.168.55.1 USB network). The serial console works from the Mac at `/dev/cu.usbmodem17905260463333`, 115200 baud (debug USB-C port).
- SSH target: TBD. Diagnose the LAN link over serial first, then add `Host robot` to `~/.ssh/config`.
- User: TBD. Sudo: passwordless expected; fallback password in `.env` (`ROBOT_SUDO_PASSWORD`).
- Network: same LAN as the Mac (192.168.1.0/24). Internet on the Jetson: expected through that LAN; confirm in M0.1.
- JetPack, CUDA, TensorRT, Python, power mode, audio devices, camera modes: unknown until M0.1.
- Deployed release and services: none of ours yet. The course robot's `memory-robot.service` may still be installed; stop and disable it before M0.3.

## Git

Standing approval to commit and push (see CLAUDE.md). No remote exists yet; ask Dylan which GitHub repo to create before the first push.

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

- No microphone or speaker on the Jetson yet. Use the Mac's microphone and speaker. The USB camera may or may not have a microphone; check in M0.1.
- Gemma license accepted on Hugging Face; the token is on the Mac (`~/.cache/huggingface/token`).
- Persona and voice: free choice.
- Dylan is near the robot on 2026-10-08 for human tests.
