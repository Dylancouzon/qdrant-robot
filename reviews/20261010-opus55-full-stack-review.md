# Claude Code Review

Target: working tree diff

I am checking the published audit numbers against the prose in STATE.md and research/gemma-fit.md.The records match the audit JSON, with one exception: the docs call the turn-paging target "unqualified", but the audit shows it was missed in every arm. Fix that wording before you commit. The diff changes no runtime code, so the review covers accuracy and record-keeping only.

## What I checked

- **Diff contents.** The change touches only records: `STATE.md`, `DECISIONS.md`, the `research/` notes, 92 new lines appended to `bench/judge-cache.jsonl`, and the new audit and review files.
- **Number agreement.** I compared the headline numbers in `STATE.md`, `research/gemma-fit.md`, and `DECISIONS.md` against `bench/results/2026-10-10-gemma-full-stack.json`. These all agree: judged and joint passes, capability splits, headroom minima, paging pages, detection fps, decode tok/s, and first-WAV p50.
- **Arithmetic.**
  - Each arm's capability scores add up to its total (6+3+23+7=39 and 6+1+15+9=31).
  - Gemma's two wins and 10 losses turn 39 into 31.
  - The latency deltas are correct: 1.790/2.910 s for CPU Qwen and 1.526/2.558 s for Gemma.
  - 500 MB equals 476.84 MiB.
- **Private content.** The audit JSON has no answer, reply, question, or prompt fields.
- **Format.** The new `DECISIONS.md` entries stay within five lines. The unnumbered headings follow the precedent since "Main reconciliation". `STATE.md` is about 60 lines, under the 120-line limit.

## Findings

1. **Medium: the docs call turn paging "unqualified", but the audit shows it was missed.**
   - `STATE.md`, `research/gemma-fit.md`, and `research/lessons.md` say system paging "overlaps turns, so zero-turn paging remains unqualified."
   - The audit counts `turns_with_system_swap`:

     | Arm | Recorded turns with swap | Stress turns with swap |
     | --- | --- | --- |
     | Current Qwen/CUDA | 36 of 47 | 23 of 120 |
     | Gemma | 9 of 47 | 5 of 120 |
     | Qwen/CPU | 10 of 47 | 5 of 120 |

   - The target is "no swap during a turn", for the whole board. A counter that cannot name the responsible process still shows that swap happened during the turn. That is a measured miss.
   - The retained Qwen/CUDA arm is the worst case. It wrote 24,093 swap pages during recorded turns, and its own process tree had a 113.74 MiB swap peak.
   - None of the prose reports the per-turn counts. Project rules say unmet targets must stay visible.
   - **Fix:** report the per-turn counts and mark the target as missed for all three arms. In the result entry in `DECISIONS.md`, say that Qwen/CPU nearly removes the paging but costs 1.79 s of p50 latency. That is the real tradeoff behind keeping Qwen/CUDA.

2. **Low: one sentence in `research/lessons.md` is now out of date.**
   - The rewritten paragraph still says "CPU Kokoro/full-stack fit, speech latency, stranger safeguards, and sustained paging remain unqualified."
   - The paragraphs that follow it measure fit and speech latency.
   - **Fix:** cut that clause down to the items still unmeasured, which are stranger safeguards and sustained paging.

3. **Low: the "unchanged quality" wording for Qwen/CPU is selective.**
   - The result entry in `DECISIONS.md` says "unchanged 39/47 quality". That is true for recorded turns only.
   - In the stress run, Qwen/CPU loses four judged answers (108 to 104, zero wins) and six joint passes (93 to 88).
   - The model is the same, so the different texts come from the removed pause/resume path or from run-to-run variation. The audit notes say the control covers pause removal, but the records do not explain the lost answers.
   - **Fix:** add the stress result to the entry, or say "recorded quality unchanged" and add the stress losses. Name the likely cause or mark it as unverified.

4. **Low: detection while the model generates was not measured for either Qwen arm.**
   - The audit sets `detection_during_llm_native` to `null` for both Qwen arms. Only Gemma has this measurement, at 15.01 fps.
   - The 15 fps target is "while talking". The current headers ("during synthesis/playback") are accurate.
   - **Fix:** add one sentence to `research/gemma-fit.md` saying that detection during Qwen generation is unmeasured. Otherwise, readers will compare the 14.31 fps figure with Gemma as if the two were equivalent.

5. **Nit: the audit filename does not follow the stated convention.**
   - `CLAUDE.md` asks for `bench/results/YYYY-MM-DD-<what>-<run id>.jsonl`. The new file is a `.json` with no run ID.
   - The earlier `gemma-litert-screen.json` set the same precedent, so this does not block anything.
   - Check that `tools/results.py` can read the file, or record the exception.

## Verdict

**PASS WITH CHANGES.** Retaining Qwen/CUDA follows from the evidence: Gemma loses eight net recorded answers and adds about 3.3 s p50 to first audio. Fix finding 1 before the commit, because it hides a target miss in the arm being kept. Findings 2 to 5 are small text edits.
