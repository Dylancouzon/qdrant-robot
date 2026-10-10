# Claude Code Review

Target: working tree diff

I have read the full record diff (all 337 lines). Next I spot-check the detection and paging numbers against the audit JSON.**Verdict: PASS.** The diff changes only records, and every number I spot-checked matches the audit JSON. The fixes from the second review are in place. Three small text issues remain, and none of them blocks the commit.

## What I checked

- **Coverage.** I read the full diff of `DECISIONS.md`, `STATE.md`, and the four `research/` files. I did not open the judge-cache lines or the audit JSON in full. The two earlier reviews already checked them, and I spot-checked the JSON.
- **Spot-check against the audit.**
  - Qwen/CUDA detection is 14.31 fps during synthesis and 15.03 fps during playback. Detection during generation is `null` for both Qwen arms.
  - Paging windows are 36, 23, 9, 5, 10, and 5. Each recorded arm has 48 actual turns, and each stress arm has 120.
  - Headroom minima are 558.38, 1,026.28, and 992.20 MiB.
- **Arithmetic.**
  - Latency gaps: 3.377 − 1.587 = 1.790 s and 4.998 − 2.088 = 2.910 s.
  - Gemma's two wins and 10 losses turn 39 into 31.
  - The capability rows add up to 39 and 31.
  - On stress joint passes, six losses and one win give a net loss of five.
- **Second-review findings.**
  1. Fixed: `research/experiments.md:13` now reports the measured paging miss and the reserve pass.
  2. Fixed: `STATE.md` and `research/gemma-fit.md` state that the kept Qwen/CUDA arm measures 14.31 fps, below 15 fps.
  3. Rejected, and the rejection is recorded: the decision log names the append-only rule as the reason, as `CLAUDE.md` requires for a rejected finding.
  4. Partly addressed: the spacing is kept on purpose. The resolution entry still ends with decision text after its evidence list, which the append-only choice also covers.

## Findings

1. **Low: `research/gemma-fit.md:298` is a review log inside a topic file.**
   - The paragraph has 12 sentences of review chronology: which reviewer ran, what each pass found, and that "a final review follows these corrections."
   - The `research/` rule says to replace outdated findings and not stack corrections. This sentence goes stale as soon as the final review lands.
   - `DECISIONS.md` and `STATE.md` already hold this history.
   - **Fix:** cut it to one sentence that links the design review and the final review verdict. Leave the review history in `DECISIONS.md`.

2. **Nit: the index row reports the paging miss but not the detection miss.**
   - `research/experiments.md:13` says "sustained detection ... unqualified."
   - It omits that every arm, including the kept Qwen/CUDA arm, measures below 15 fps during synthesis. The follow-up decision says to mark exactly that.
   - **Fix:** add "and all arms detect below 15 fps during synthesis" to the row.

3. **Nit: "15 fps synthesis floor" is a new term.**
   - `STATE.md:86` and `research/gemma-fit.md:200` use it. The target is "15 fps or more, sustained, while talking."
   - **Fix:** write "below the 15 fps detection target during synthesis."

## Before the commit

- `STATE.md:120` and `STATE.md:129` still say that this review is pending and give the command to start it. After this review, record its verdict, then update the "Exact next command" to the commit hook and the push.
