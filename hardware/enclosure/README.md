# Robot enclosure

This is the simplified enclosure for the Qdrant Edge robot. It keeps the approved tapered white body, black visor head, speaker grille, and ±80° head turn. Nine printed parts replace Concept A's 38. Fasteners are M3 and M2 screws with M3 nuts, and no printed pin, key, keeper, strap, or gear remains. Concept A is tagged `archive/concept-a-enclosure`.

Open [the viewer](output/robot-viewer.html) to see the assembled robot, turn the head, and read the parts, fasteners, and steps. Read [ASSEMBLY.md](ASSEMBLY.md) to build it. Read [BRIEF.md](BRIEF.md) for the design reasons and [MEASUREMENTS.md](MEASUREMENTS.md) for the part sizes. Physical fit, cooling, acoustics, and powered motion stay U (unverified) until you print and test.

## Printed parts

Print every part in the orientation shown. The STL files in `output/print/Required` already have that orientation. Times and grams are Bambu Studio estimates for the P1S (E).

| Part | Color | Orientation | Size (mm) | Time | PLA |
| --- | --- | --- | --- | --- | --- |
| `body-shell` | White | Upside down, roof on the bed | 148.6 × 127.1 × 152.4 | 6.5 h | 241 g |
| `base-plate` | White | Flat, underside on the bed | 143.2 × 116.5 × 48 | 2.0 h | 95 g |
| `port-panel` | White | Outside face on the bed | 91.9 × 49.3 × 8.2 | 0.4 h | 12 g |
| `head-shell` | White | Rear face on the bed | 116 × 56 × 77 | 1.8 h | 92 g |
| `visor` | Black | Front face on the bed | 112 × 52 × 23.5 | 0.7 h | 21 g |
| `speaker-grille` | Black | Inside face on the bed | 101.2 × 49.2 × 4.3 | 1.0 h | 17 g |
| `neck-hub` | Black | Lower face on the bed | 50.3 × 50.7 × 17.1 | 0.4 h | 11 g |
| `head-shaft` | Black | Flange on the bed | 50 × 50 × 21.3 | 0.4 h | 10 g |
| `horn-disc` | Black | Flat on the bed | 31 × 31 × 7.8 | 0.2 h | 3 g |

The nine parts take 13.4 h and 500 g of PLA. The shell is the largest part and fits the 256 mm bed.

## Fasteners

The robot uses 17 M3 screws, four M2 screws, and 13 M3 nuts. Lengths are stock sizes.

| Screw | Count | Length | Nut | Holds | Tool |
| --- | --- | --- | --- | --- | --- |
| M3 | 3 | 16 mm | yes | Hub to the roof | 2.5 mm hex key from above |
| M3 | 1 | 16 mm | yes | Shaft to the horn disc | 2.5 mm hex key from above |
| M3 | 4 | 6 mm | no | Horn disc to the servo horn | 2.5 mm hex key through the disc |
| M3 | 2 | 8 mm | yes | Head to the shaft flange | 2.5 mm ball-end key through the front opening, about 20° |
| M3 | 2 | 8 mm | yes | Visor to the head | 2.5 mm short-arm L-key from below |
| M3 | 4 | 10 mm | yes | Base plate to the shell | 2.5 mm hex key from below |
| M3 | 1 | 12 mm | yes | Port panel to the plate ear | 2.5 mm hex key from outside |
| M2 | 4 | 8 mm | no | Camera to the visor posts | Driver for the M2 head |

The M2 screws cut their own thread in 1.7 mm pilot holes in the visor posts. The servo kit supplies its own horn screw, which this list does not count. M3 lengths: four of 6 mm, four of 8 mm, four of 10 mm, one of 12 mm, and four of 16 mm.

The plate and panel screws sit in counterbores (6.5 mm and 6.0 mm wide) that take socket, button, pan, or flat M3 heads. The plate counterbore is 3.2 mm deep, so no head stands below the plate. Engagement is 3.6 mm past the nut's first face for both screws, measured from the counterbore floor.

## Print settings

Use a Bambu Lab P1S with a 0.4 mm nozzle and PLA. Set 0.2 mm layers, three walls, 15% grid infill, and supports off. `bambu.py` packages these settings into one native project per part.

`printcheck.py` reports zero floating islands and zero thin area (under 2 mm) on all nine parts. The total overhang is 719.0 mm² (E), against 34,887 mm² for Concept A. All of it is flat bridges over pockets and openings, except 63 mm² of gently sloped faces in `body-shell`. Three bridges are long: the 60.6 × 2.4 mm lintel above the grille window in `body-shell`, the 24 mm bearing seat roof in `neck-hub`, and the 22 mm eye ring in `visor`. Watch these three on the first print.

## Print the coupon plate first

`output/print/Coupons/coupon-plate.stl` (40 × 52 × 11.2 mm, 21 min, 8 g) holds the three fits that can fail:

- **Hub-style nut channel:** a nut channel with a 2 mm floor, the 0.3 mm ridge, and a screw hole that passes through. Slide an M3 nut in from the open end. It must click past the ridge and stay.
- **Corner-style pocket:** the same channel, with the screw hole blind above the nut, as in the shell's corner bosses.
- **Camera posts:** four posts, 7 mm across and 7 mm tall, at 32.3 mm spacing on a 40 × 40 mm frame, with 1.7 mm pilot holes. An M2 screw must bite without splitting the post.

The hub is the bearing coupon, because its seats take both bearings. The horn disc is the horn coupon, because it fits the servo horn. Press the bearings in and set the disc on the horn before you print the large parts.

## Regenerate

Use the pinned environment (`requirements.lock`, Python 3.12) at `build/hardware-layout/venv`. Run these from the repository root, in order.

1. `build/hardware-layout/venv/bin/python hardware/enclosure/body.py` builds the body and runs its checks (about 2 min).
2. `build/hardware-layout/venv/bin/python hardware/enclosure/head.py` builds the neck and head and runs their checks.
3. `build/hardware-layout/venv/bin/python hardware/enclosure/coupons.py` builds the coupon plate.
4. `build/hardware-layout/venv/bin/python hardware/enclosure/bambu.py` packages and slices every STL with the installed Bambu Studio. It writes `output/bambu/` and `slice-checks.json`.
5. `build/hardware-layout/venv/bin/python hardware/enclosure/preview.py` writes `output/robot-viewer.html`.
6. `node hardware/enclosure/check-viewer.cjs` checks the viewer data and controls.

`study.py` holds the measured body split and servo drive choices from BRIEF.md. It writes to `build/enclosure-study/`.

## Files

- `geometry.py`: tapered body and head envelopes, and the hardware boxes.
- `interface.py`: positions shared by the body and the neck.
- `body.py`, `neck.py`, `head.py`: the printed parts and their checks.
- `coupons.py`, `bambu.py`, `preview.py`, `check-viewer.cjs`: coupon, slicing, and viewer.
- `p1s-template.3mf`: the saved P1S settings that `bambu.py` fills with each part.
- `exterior-concept.png`: the approved appearance target.
- `../printcheck.py`: the overhang, island, and thin-wall checker.
