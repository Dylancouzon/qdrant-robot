# Claude Code Review

Target: working tree diff

I am checking the corrected records against the audit JSON. Next I check the turn counts and detection fields.I re-ran the review on the corrected records. All numbers check out against the audit JSON, but one file still calls the paging target "unqualified" when every arm measurably misses it. The diff changes no runtime code.

## What I verified

- **Turn counts:** `actual_turns` is 48 for the recorded workload, so the 36/48, nine/48, and 10/48 paging counts are correct. Stress uses 120 turns.
- **Paired results:**
  - Gemma recorded: two wins and 10 losses give 31. On joint passes, three wins and 10 losses give 29.
  - Qwen/CPU stress: zero wins and four losses on judged answers give 104. One win and six losses on joint passes give 88.
  - The lead was right that the earlier review's "six" net joint loss is five.
- **Latency gaps:** 1.790/2.910 s and 1.526/2.558 s match the unrounded p50/p95 values in the JSON.
- **Paging and headroom:** the swap-in/swap-out page counts (139/24,093, 5/7, 20/42, 40/5,408, 10/1, 11/3) match the JSON. The headroom minima 715.49, 558.38, 1,045.34, 1,026.28, 999.09, and 992.20 MiB also match. Gemma detection during generation is 15.01 fps, and it is null for both Qwen arms.
- **Earlier findings:** all five are addressed in `STATE.md`, `research/gemma-fit.md`, and `research/lessons.md`.
- **Judge cache:** the new `bench/judge-cache.jsonl` lines contain only keys, verdicts, and short reasons.
- **`tools/results.py`:** it reads only `.jsonl` files, so the documented `.json` exception is correct.

## Findings

1. **Medium: `research/experiments.md:13` still says paging and headroom "remain unqualified."**
   - The Acceptance row was not updated. It reads "Physical audio, held-out quality, sustained detection, headroom, no paging, and M4 remain unqualified."
   - This contradicts the review fix in the other files. Paging is a measured miss in every arm, and the sampled model-stack reserve passes.
   - This is the index page that readers open first, so it repeats the problem the first review flagged.
   - **Fix:** "Zero-turn paging misses in every arm, and the sampled reserve passes (see gemma-fit.md). Physical audio, held-out quality, sustained detection, and M4 remain unqualified."

2. **Low: the kept Qwen/CUDA arm detects at 14.31 fps during synthesis, which is below the 15 fps floor.**
   - The records give the number and call sustained detection "unqualified." No file says that the arm you keep falls below the target here.
   - Both CPU arms reach about 14.95 fps, so the dip comes from CUDA Kokoro contention.
   - This follows the same reasoning as the paging finding. Caveats apply: the rate is aggregated, includes about 79 ms of telemetry per 250 ms, and uses file fixtures.
   - **Fix:** add one sentence to `research/gemma-fit.md` and `STATE.md`: "Current Qwen/CUDA measures 14.31 fps during synthesis, below 15 fps, under instrumentation."

3. **Nit: the `DECISIONS.md` entry "Gemma full-stack result" still says "unchanged 39/47 quality" and "small system paging remains."**
   - The later resolution entry corrects both statements.
   - Neither entry is committed yet, so you can edit the result entry directly. The append-only rule covers committed history, and a reader of that entry alone would get the wrong picture.

4. **Nit: formatting in `DECISIONS.md`.**
   - The resolution entry's last line puts decision text after the evidence list.
   - The spacing between entries switches between one and two blank lines.

## Verdict

**Pass with changes.** Keeping Qwen/CUDA follows from the evidence: Gemma has eight fewer correct recorded answers and adds 3.3 s p50 to first audio. Fix finding 1 before the commit, because it hides a measured miss again. Findings 2 to 4 are small text edits.
