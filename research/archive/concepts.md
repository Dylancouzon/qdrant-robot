# Concepts considered (2026-10-07)

Six research rounds (15 Sonnet researchers, five Codex passes) compared these. D1 chose the first.

| Concept | Verdict | Why |
| --- | --- | --- |
| Reachy capabilities on the Jetson alone | **Chosen** | Strongest "how does this run on Edge?" moment; no laptop |
| Offline Wikipedia knowledge shard | Add-on (M5) | 10M 768-d vectors at 2 bits need about 1.92 GB of codes alone; total RAM unmeasured; competes with the LLM |
| Impossible Museum (silhouette rebuilt from 490k CC0 Met artifacts) | Alternative | Strong visual, but a new concept rather than an Edge feat |
| Doodle Oracle (10M Quick, Draw! doodles) | Alternative | Charming; reviewers rated it "cute to strong" |
| Object heist (DINOv2 plus patch MaxSim) | Folded into M2 | Better instance recognition helps "What did I show you?" |
| Total recall of a booth day | Folded into M2 | Small LLMs fail time questions; answer them with filters in code |
| Arm, pen plotter, Reachy Mini head, second robot | Rejected | Fragile to travel; hardware would steal the show |
| Face-to-painting, personal VLM | Rejected | GDPR risk; confident wrong answers |

The Qdrant June 2026 demo (qdrant-labs/edge-mission-control) already showed hybrid RRF, facets, and 0.51 ms queries on a recorded video. Anything we show must go beyond it.
