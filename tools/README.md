# Project tools

[Workflow](../research/workflow.md) defines operating rules. Use [jetson.py](jetson.py) for all Mac-to-Jetson work.

| Tool | Purpose |
| --- | --- |
| [jetson.py](jetson.py) | Deploy immutable releases, run named locked jobs, collect results, and roll back. |
| [talk.py](talk.py), [talk.html](talk.html) | Serve the local robot monitor and proxy authenticated controls. |
| [models.py](models.py) | Download and verify artifacts pinned in [models.json](../models.json). |
| [gate.py](gate.py) | Run deterministic checks and read-only Codex gates. |
| [results.py](results.py) | Summarize replay and brain bake-off JSONL offline. |
| [record.py](record.py) | Record real fixture speech on the Mac. |
| [servo.py](servo.py) | Read or gently nudge the loose STS3215. Follow [the hardware guide](../hardware/SERVO.md). |
| [githooks/pre-commit](githooks/pre-commit) | Run required checks before commits. |
| [test_gate.py](test_gate.py), [test_results.py](test_results.py), [test_talk.py](test_talk.py), [test_servo.py](test_servo.py) | Exercise gates, evidence reporting, lifecycle, proxies, and the servo transport. |

`collect` copies the complete remote results directory. Preserve locally enriched history before collection and reconcile it before staging. Never discard raw benchmark evidence.

## UI development

The page is code-native HTML, CSS, and JavaScript in `talk.html`. The running Mac monitor reads it on page loads. Python proxy changes require a launcher restart. [Interface guidance](../research/mac-audio-interface.md) defines behavior.

```sh
npm --prefix tools/ui ci --ignore-scripts
npm --prefix tools/ui test
```

[ui/test_talk.cjs](ui/test_talk.cjs) runs the shipped page in jsdom with isolated responses. [package.json](ui/package.json) and [package-lock.json](ui/package-lock.json) pin development dependencies. The Jetson needs no Node runtime. [assets/OFL.txt](assets/OFL.txt) licenses the locally served [Mona Sans font](assets/mona-sans-latin.woff2).
