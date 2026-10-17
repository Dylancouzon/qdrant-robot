# Robot enclosure

This is the simplified enclosure for the Qdrant Edge robot. It keeps the approved tapered white body, black visor head, speaker grille, and ±80° head turn. Nine printed parts replace Concept A's 38. Fasteners are M3 and M2 screws with M3 nuts, and no printed pin, key, keeper, strap, or gear remains. Concept A is tagged `archive/concept-a-enclosure`.

Open [the viewer](output/robot-viewer.html) to see the assembled robot, turn the head, and read the parts, fasteners, and steps. Read [ASSEMBLY.md](ASSEMBLY.md) to build it. Read [BRIEF.md](BRIEF.md) for the design reasons and [MEASUREMENTS.md](MEASUREMENTS.md) for the part sizes. Dylan confirmed robot assembly on 2026-10-16. Watched mounted motion and cable clearance passed through ±60° at 40°/s. Cooling, acoustics, transient servo temperature feedback, and prolonged loaded power remain unqualified. The ±80° value describes modeled mechanical travel; runtime travel is ±60°.

The revised base plate lowers the Jetson retaining lip to clear the bottom GPIO header by 1 mm (E). The tray slot keeps its confirmed 6.6 mm fit. Physical fit of this revision remains U. Reprint only `base-plate` for this correction. The saved `assembly-white.3mf` session predates the correction; use the updated STL or generated `output/bambu/White.3mf` instead.

To modify an existing print, disconnect power and remove the electronics first. Lower the shallow retaining lip on the fan side of the Jetson pocket to 4.3 mm above the plate's flat top. This removes about 8.1 mm from that lip (E). Keep the tall tray slot, its walls, and the supporting floor intact. Remove debris before checking the fit by hand.

The saved [assembly print session](assembly-white.3mf) preserves the local Bambu Studio edits from the enclosure worktree. It has three plates, support settings enabled, and no sliced G-code. The generated projects and estimates below remain the reproducible design outputs. Re-slice the saved session before printing; `bambu.py` does not regenerate it.

## Printed parts

Print every part in the orientation shown. The STL files in `output/print/Required` already have that orientation. Sizes are the measured STL sizes. Times and grams are Bambu Studio estimates for the P1S (E).

| Part | Color | Orientation | Size (mm) | Plate |
| --- | --- | --- | --- | --- |
| `body-shell` | White | Upside down, roof on the bed | 148.6 × 127.1 × 152.4 | White 1 |
| `port-panel` | White | Outside face on the bed | 91.9 × 49.3 × 8.2 | White 1 |
| `base-plate` | White | Flat, underside on the bed | 143.2 × 116.5 × 48 | White 2 |
| `head-shell` | White | Rear face on the bed | 116 × 56 × 77 | White 2 |
| `visor` | Black | Front face on the bed | 112 × 52 × 23.5 | Black |
| `speaker-grille` | Black | Inside face on the bed | 101.2 × 49.2 × 4.3 | Black |
| `neck-hub` | Black | Lower face on the bed | 50.3 × 50.7 × 17.1 | Black |
| `head-shaft` | Black | Flange on the bed | 50 × 50 × 21.3 | Black |
| `horn-disc` | Black | Flat on the bed | 31 × 31 × 7.8 | Black |

`bambu.py` lays the parts out on the plates of three Bambu Studio projects in `output/bambu/`. Open a project, check the plate, and send it to the P1S. Parts sit at least 10 mm apart, and every part keeps the orientation of its STL.

| Project | Plate | Parts | Time | PLA |
| --- | --- | --- | --- | --- |
| `Test pieces/Test pieces.3mf` | Test pieces | `fit-test-plate`, `slot-test-piece` | 0.4 h | 12 g |
| `White.3mf` | White 1 | `body-shell`, `port-panel` | 6.7 h | 252 g |
| `White.3mf` | White 2 | `base-plate`, `head-shell` | 3.5 h | 175 g |
| `Black.3mf` | Black | `visor`, `speaker-grille`, `neck-hub`, `head-shaft`, `horn-disc` | 2.2 h | 61 g |

The nine parts take 12.5 h and 487 g of PLA. The shell is the largest part and fits the 256 mm bed. Four 1.5 mm ridges on the grille window's top wall wedge the grille 0.3 mm tight (U) until the speaker sits behind it. To remove it, press it inward from outside.

## Fasteners

The robot uses 17 M3 screws, four M2 screws, and 13 M3 nuts. Lengths are stock sizes.

| Screw | Count | Length | Nut | Holds | Tool |
| --- | --- | --- | --- | --- | --- |
| M3 | 3 | 16 mm | yes | Hub to the roof | 2.5 mm hex key from above |
| M3 | 1 | 16 mm | yes | Shaft to the horn disc | 2.5 mm hex key from above |
| M3 | 4 | 6 mm | no | Horn disc to the servo horn | 2.5 mm hex key through the disc |
| M3 | 2 | 8 mm | yes | Head to the shaft flange | 2.5 mm ball-end key through the front opening, about 25° |
| M3 | 2 | 8 mm | yes | Visor to the head | 2.5 mm short-arm L-key from below |
| M3 | 4 | 10 mm | yes | Base plate to the shell | 2.5 mm hex key from the plate side |
| M3 | 1 | 12 mm | yes | Port panel to the plate ear | 2.5 mm hex key from outside |
| M2 | 4 | 8 mm | no | Camera to the visor posts | Driver for the M2 head |

The M2 screws cut their own thread in 2.1 mm pilot holes in the visor posts. The servo kit supplies its own horn screw, which this list does not count. M3 lengths: four of 6 mm, four of 8 mm, four of 10 mm, one of 12 mm, and four of 16 mm.

Use socket-head (hex) M3 screws, so the 2.5 mm hex keys fit every screw. The plate and panel screws sit in counterbores (6.5 mm and 6.0 mm wide). The plate counterbore is 3.2 mm deep, so no head stands below the plate. Engagement is 3.6 mm past the nut's first face for both screws, measured from the counterbore floor.

## Print settings

Use a Bambu Lab P1S with a 0.4 mm nozzle and PLA. Set 0.2 mm layers, three walls, 15% grid infill, and supports off. `bambu.py` packages these settings into the three native projects.

`printcheck.py` reports zero floating islands and zero thin area (under 2 mm) on all nine parts. The revised base plate has a minimum checked thickness of 2.4 mm (E). The total overhang is 732.7 mm² (E), against 34,887 mm² for Concept A. All of it is flat bridges over pockets and openings, except 63 mm² of gently sloped faces in `body-shell`. Three bridges are long: the 60.6 × 2.4 mm lintel above the grille window in `body-shell`, the 24 mm bearing seat roof in `neck-hub`, and the 22 mm eye ring in `visor`. Watch these three on the first print.

## Print the test pieces first

Test pieces are small prints that check the fits (nut snaps, screw bite, the Jetson slot) before the large parts. They are not part of the robot. Print `Test pieces/Test pieces.3mf` first. Then print `Black.3mf`, then `White.3mf`. The neck hub and the horn disc in the Black project also show whether the bearings and the servo horn fit, so print that project early.

`output/print/Test pieces/slot-test-piece.stl` (40.4 × 13 × 9.7 mm, printed on its back) is the full height of the Jetson slot. Slide it over the plastic strip on the edge of the real Jetson, opposite the connectors. The strip is 6 mm thick and 8 mm deep (Dylan, measured), so the slot is 6.6 mm wide and 6 mm deep. A 7 mm slot held the Jetson loosely, a 6.2 mm slot did not fit, and 6.6 mm fits (Dylan, 2026-10-15). It must slide on by hand along its whole height. If your strip differs, set `JETSON_STRIP_T` and `JETSON_STRIP_D` in `geometry.py` and rebuild before you print the base plate.

`output/print/Test pieces/fit-test-plate.stl` (43.0 × 53.5 × 11.2 mm) holds the three fits that can fail:

- **Hub-style nut channel:** a nut channel with a 2 mm floor, the 0.4 mm ridge, and a screw hole that passes through. Slide an M3 nut in from the open end. It must click past the ridge and stay.
- **Corner-style pocket:** the same channel, with the screw hole blind above the nut, as in the shell's corner bosses.
- **Camera posts:** four posts, 7 mm across and 7 mm tall, at 34 mm spacing, with 2.1 mm pilot holes. An M2 screw must bite without splitting the post.

The hub seats take both bearings, and the horn disc fits the servo horn. Its nut pocket also tests the two 0.4 mm lips: an M3 nut must snap in and stay when the pocket faces down. Press the bearings in and set the disc on the horn before you print the large parts.

## Regenerate

Use the pinned environment (`requirements.lock`, Python 3.12) at `build/hardware-layout/venv`. Run these from the repository root, in order.

1. `build/hardware-layout/venv/bin/python hardware/enclosure/body.py` builds the body and runs its checks (about 2 min).
2. `build/hardware-layout/venv/bin/python hardware/enclosure/head.py` builds the neck and head and runs their checks.
3. `build/hardware-layout/venv/bin/python hardware/enclosure/coupons.py` builds the test pieces.
4. `build/hardware-layout/venv/bin/python hardware/enclosure/bambu.py` lays out, packages, and slices every STL with the installed Bambu Studio. It rebuilds `output/bambu/` and `slice-checks.json`.
5. `build/hardware-layout/venv/bin/python hardware/enclosure/preview.py` writes `output/robot-viewer.html`.
6. `node hardware/enclosure/check-viewer.cjs` checks the viewer data and controls.

`study.py` holds the measured body split and servo drive choices from BRIEF.md. It writes to `build/enclosure-study/`.

## Files

- `geometry.py`: tapered body and head envelopes, and the hardware boxes, including the Jetson's real shape and its strip thickness.
- `interface.py`: positions shared by the body and the neck.
- `body.py`, `neck.py`, `head.py`: the printed parts and their checks.
- `coupons.py`, `bambu.py`, `preview.py`, `check-viewer.cjs`: test pieces, plate layout and slicing, and viewer.
- `p1s-template.3mf`: the saved P1S settings that `bambu.py` copies into each project.
- `exterior-concept.png`: the approved appearance target.
- `../printcheck.py`: the overhang, island, and thin-wall checker.
