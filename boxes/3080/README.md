# The 3080 box: how the robot's lead and this machine work together

Superseded 2026-10-09: the lead reaches the box directly with `ssh dylan@192.168.1.74`, and the `box/3080` mailbox branch is deleted. Read [STATE.md](../../STATE.md) and [machine-access notes](../../research/lessons.md#machine-and-environment-pitfalls) before work. The protocol below is historical.

The WSL2 project is `/home/dylan/qdrant-robot-box`. GPU jobs must use `/home/dylan/qdrant-robot-box/gpu.lock`. Preserve other owners' jobs and Docker/Ollama services; the lock coordinates only participants that use it.

This folder records the former mailbox between the Mac lead and a Claude session on Dylan's Windows PC with an RTX 3080. Those sessions exchanged tasks and results through the branch.

## Archived protocol

- Branch: `box/3080`. Pull it before starting work, and push after every finished step. Never push to `main` or any other branch.
- The lead writes tasks in `boxes/3080/BRIEF.md`. Do not edit that file.
- You write results in `boxes/3080/REPORT.md`: rewrite it (do not append) with a summary first, then what you ran, numbers, problems, and the exact state you left things in. Raw logs go in `boxes/3080/logs/` (keep them small: tails, not full logs).
- Code you write for a task goes where the brief says. Never edit `STATE.md`, `DECISIONS.md`, or `CLAUDE.md`: those belong to the lead.
- Large files (model weights, GGUF, engines, datasets over 50 MB) never go into git. Copy finished artifacts to the robot: `scp <file> robot:/home/qdrant/qdrant-robot/shared/models/<subdir>/`, and record their sha256 in REPORT.md.
- Never write passwords, tokens, or keys into the repo.
- When a step fails or the brief looks wrong, stop, write what you found in REPORT.md, push, and wait for a new brief rather than working around it.

## The robot

- A Jetson Orin Nano Super 8 GB, reachable as `qdrant-robot.local` (user `qdrant`) on Dylan's home network. The lead also uses it: before running anything heavy on the robot, take the shared lock with `flock /home/qdrant/qdrant-robot/shared/gpu.lock <command>`, and never stop services or jobs you did not start.
- Project rules and context: `CLAUDE.md` (read it; you act as a builder, not the lead), `STATE.md` (read-only for you).
