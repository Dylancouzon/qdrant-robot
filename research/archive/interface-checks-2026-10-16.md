# Interface checks through 2026-10-16

These dated checks preserve measurements, releases, and limits. Read the [current interface guide](../mac-audio-interface.md) for behavior and [STATE.md](../../STATE.md) for the deployed release. Earlier search-flow drawings were replaced by the stored memory map.

## Evidence and limits

- [D147 box continuity](../../bench/results/2026-10-10-d147-box-continuity.json): accepted live behavior and the final one-condition "???" fix. Genuine losses and size expiry can still blink.
- [D143 face delivery](../../bench/results/2026-10-10-d143-face-delivery.json): completed-source publication and actual MJPEG accounting. Model budgets and source-specific identity guards remain fixed.
- [D144 false-claim suppression](../../bench/results/2026-10-10-d144-phone-recovery.json) and [D145 Ignore/Restore](../../bench/results/2026-10-10-d145-ignore-continuity.json): bounded development checks, with earlier native failures retained.
- [D146 detector default](../../bench/results/2026-10-10-d146-detector-default.json): all 12 original phone checks pass, with 91.43% movement and 91.47% Restore coverage. Conversation stalls and paging remain open.
- [External cup](../../bench/results/2026-10-10-d145-external-cup.json): 73.78% recognition across changed viewpoints. This remains a development gap, not a cue for scene-specific rules.

These bounded recordings and Dylan's live acceptance establish a usable checkpoint. They do not establish perfect smoothness, general instance recognition, sustained 15fps conversation, zero paging, or final milestone acceptance. Historical D134–D139 designs and rejected filters remain linked from ../../DECISIONS.md and ../lessons.md, not current implementation guidance.

## UI refresh checks, 2026-10-15

The brief compared the earlier expandable evidence strip with a dedicated evidence row and search map. The shared panel follows Dylan's requested 70/30 split and leaves conversation at full height. The existing models, storage, retrieval policy, consent, and deletion paths remain in place. The additive API fields expose visitor IDs, deletion events, and existing timing milestones.

The design review requires truthful entry counts, tracked DOM checks, current browser checks, and a paired isolated Jetson smoke test. The DOM harness is `tools/ui/test_talk.cjs`. Run `npm --prefix tools/ui ci --ignore-scripts`, then `npm --prefix tools/ui test`. `tools/gate.py checks` also runs it. jsdom is a pinned development dependency. The robot uses no Node runtime.

The task reviews passed. The deterministic checks passed, including Python regressions, the DOM harness, and module assertions (E). Browser checks cover desktop and 390 px phone layouts, loaded thumbnails, keyboard expansion, gallery retention after changing data, and automatic tips (E). Evidence: [browser checks](../../bench/results/2026-10-15-ui-browser.json).

The [accepted baseline](../../bench/results/2026-10-15-ui-refresh-baseline-1792120775.json) and [candidate](../../bench/results/2026-10-15-ui-refresh-candidate-1792121429.json) pass the same isolated naming, recall, thumbnail, queued view-removal, and deletion checks (J). The candidate also verifies separate visitor IDs and exact turn timing fields. Both runs use two typed turns, a repeated development image, and temporary memories. These checks establish interface behavior, rather than held-out answer quality or physical audible latency.

Live attachment on `b78d48ec189e` opens the camera and loads five existing objects with 15 saved views (J). The final local monitor refinements use singular counts and full-width images for objects with one saved view. These presentation changes keep the Jetson runtime unchanged.


## Stored memory map checks, 2026-10-16

The design compared bounded stored-ID snapshots with embedding projection. Stored IDs preserve object links without fitting incompatible embedding spaces. The design review required precise storage time, statement source IDs, bounded database reads, and a polling comparison. Each requirement is implemented. The DOM harness covers stable nodes, creation versus sample turnover, repeated recall, keyboard object links, deletion races, reconnect, tooltips, and retained Memory behavior. Browser checks cover a centered distinct tip, fuller desktop panels, and a 390 px layout without overflow (E). Screenshots remain in `build/memory-map/`.

The [Jetson check](../../bench/results/2026-10-16-memory-map-1792123869.json) passes teaching, true recall IDs, old recalled sources outside the recent sample, delayed storage, deletion, and forgotten links. It uses release `72dc153bd71d`, 5,000 temporary seen points, 200 temporary named objects, a repeated development image, and oracle input. The result embeds the harness source and reproduction command. An initial [harness failure](../../bench/results/2026-10-16-memory-map-failed.json) required ten polls before the short turns finished; the corrected run saves partial records and requires two polls.

Four alternating polling-off/on blocks contain three turns each (J). Eight map requests take 11.45 ms median and 69.34 ms maximum, including the Recognition queue and local HTTP. The seen-shard metadata read takes 3.23 ms median and 5.33 ms maximum across 12 calls. Response bodies are 33.1–33.5 KB. Detection medians are 14.61 fps without polling and 14.89 fps with polling. First synthesized phrase medians are 1.402 s and 1.486 s. These small samples establish interface operation, rather than a performance improvement.

Whole-block paging counters record 140/1 pages read and 13/853 pages written for polling off/on. Response lengths and history differ across blocks, so this run cannot attribute paging changes to polling. The existing paging target remains unmet. There is no held-out quality, physical audible latency, audio playback, or long-session acceptance claim.

Live attachment on `83dd4fb999f5` loads 70 stored points and four objects with 14 loaded thumbnails (J). The [browser receipt](../../bench/results/2026-10-16-memory-map-browser.json) records actual desktop and phone checks (E).

Task reviews passed. The final review verifies late-caption color updates and stable object positions after sample reentry. Both have DOM regression checks.
