You are the task review gate for this repo. Read CLAUDE.md and STATE.md first. Review the uncommitted changes (`git diff HEAD` and new files from `git status`) and the files named below.
Read the tracked harness and product code plus the evidence cited below; read refs/ only when relevant; skip model files and bulk logs. Judge the code at the current commit plus uncommitted changes. Separate blocking findings from optional improvements.

Check, in this order:
1. Correctness: bugs, races, resource leaks, wrong numbers, broken edge cases.
2. Performance on a Jetson Orin Nano 8 GB: memory, latency, wasted work.
3. Cleanliness: dead code, duplication, an abstraction with one implementation, a config value that never changes, a missing runnable check for non-trivial logic.
4. Is this the smallest change that does the job? Is there a better approach the author missed?
5. Process: if the change adds a runtime module under robot/, a dependency, or a model, or changes an approach (a benchmark or tool script needs no design verdict), a design verdict in reviews/ (GO, or GO WITH CHANGES with the changes applied) must cover it; otherwise FIX. A claim that something is faster needs a result in bench/results/; otherwise FIX. Every finding cites file:line.
List findings most severe first, each with file:line and a concrete fix. Under 600 words. Do not edit files. End with exactly one last line: `VERDICT: PASS` or `VERDICT: FIX`.
