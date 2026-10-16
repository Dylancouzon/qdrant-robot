# Simplified enclosure brief

Dylan rejected Concept A for printing and assembly on 2026-10-12. It has too many small parts, too much overhang, studs too thin to hold, and a roof catch on `body-front` that hangs on almost nothing. This design keeps the same robot and the same appearance, with far fewer and stronger parts.

## Root causes in Concept A

- Printed fasteners: 25 of the 38 required parts are pins, keys, and keepers. The roof-bridge keepers measure 2.8 × 6 × 0.8 mm. The head keys have 1.3 × 1.2 mm sections.
- Studs on cantilevers: the roof sits on four 2 × 3 × 3 mm posts. Each post stands on a 6 × 6 mm beam that the CAD trims to the tapered wall at Z 137.
- Orientation follows the panel split: every shell prints with a rounded exterior on the bed, so each roll starts as a flat overhang.
- Indirect joint: a split bearing tower, eight cross pins and keepers, two gears, and a servo that is not installed.

## Fixed inputs

- Exterior: `hardware/enclosure/geometry.py` body and head envelopes (152 × 130 mm base, 128 × 110 mm shoulders at Z 160, head 116 × 80 × 56 mm at Z 180 to 236). Approved concept image and colors stay. Envelope stays at or under 148.6 × 127.2 × 236 mm.
- Hardware reservations: `hardware/enclosure/geometry.py` (Jetson standing on edge, speaker, audio case, plug side, fan intake, outlet, camera, bus).
- Owned parts: two 15 × 24 × 5 mm bearings; M2 and M3 screws (4 to 16 mm) with nuts; STS3215 servo. No heat-set inserts.
- Measured and sourced sizes: `hardware/enclosure/MEASUREMENTS.md` (camera 38 × 38 mm with a 15 mm lens holder, speaker 100 × 45 × 21 mm, servo horn holes).
- Requirements: `hardware/DESIGN_REQUIREMENTS.md` (press-fit electronics with removable catches, port-side plug access, camera cable through the neck gap (H6), ±80° yaw with hard stops, cooling path, microphone holes).

## Proposed design

| Part | Color | Print orientation |
| --- | --- | --- |
| Body shell, roof and servo pocket included | White | Upside down, roof on the bed |
| Base plate with component pockets | White | Flat, underside on the bed |
| Port panel | White | Outside face on the bed |
| Head shell, open front | White | Rear face on the bed |
| Visor, carries the camera | Black | Front face on the bed |
| Speaker grille, inserted from inside | Black | Inside face on the bed |
| Neck hub, holds both bearings | Black | Lower face on the bed |
| Head shaft with top flange | Black | Flange on the bed |
| Horn disc | Black | Flat on the bed |

Nine printed parts. Fasteners are M3 screws into hex-nut pockets, and M2 screws for the camera. No printed pin, key, keeper, strap, or gear remains.

### Design rules

- Walls are at least 2.4 mm. Screw bosses are at least 7 mm across for M3. Every flexing catch is at least 2.5 mm thick and 15 mm long, and it flexes in the print plane.
- No acute solid edges. Every feature that hangs from a wall in print orientation has a 45° underside.
- Electronics sit in loose pockets with about 1 mm clearance on each side (the bus board has 0.55 mm front and back), using the sizes in `MEASUREMENTS.md`. A pocket holds a part by its walls and gravity, plus one catch where the part could fall out when the robot tips over. Only the camera uses screws.

### Body

The shell drops over the populated base plate. Four M3 screws pass up through the base plate into nut pockets in the shell's corner bosses. The shell's cut edge gets a flat seat, at least 3 mm wide, where the base plate sits. This seat replaces the knife edge that causes A1's thin area in the study.

Everything on the base plate must pass straight up through the 131.7 × 110.3 mm opening and fit inside the tapering cavity. The builder checks this as a vertical sweep of every component and pocket. The Jetson stands on edge in a pocket, and its ports face the port panel. Internal cables connect before the shell closes; only the power cable leaves through the port window. The servo lead runs to the bus board with enough slack to lift the shell 60 mm before you unplug it.

### Neck joint

- **Hub:** it sits on the roof between Z 160 and Z 178. Three M3 screws pass down through the hub into nut pockets under the roof. The bore has a central inner shoulder that touches only the outer races. The upper bearing presses down onto the shoulder, and the lower bearing presses up onto it.
- **Shaft:** a 14.9 mm journal passes through both bearings. Its top flange rests on the upper bearing's inner race through a narrow ring that touches only the inner race, so the bearings carry the head's weight. A square boss on the horn disc fits a socket in the shaft's lower end. The shaft length leaves 0.5 mm of axial play, so no screw can clamp the bearings.
- **Horn disc:** it is 31 mm across, so it fits through the 32.4 mm roof opening. Four M3 screws fix it to the servo horn (9.9 mm square, on a 14 mm circle, U). One M3 screw runs from the top of the flange down the shaft's center into a nut under the disc. This screw pulls the disc against the shaft's end face, not against a bearing.
- **Servo:** it hangs from the horn disc inside a pocket under the roof. The pocket's two long walls stop it from turning, and 1 mm of vertical clearance keeps the head load off the servo. It needs no strap: the shaft holds it.
- **Stops:** a slot under the flange meets a post on top of the hub at ±80°.
- **Head:** two M3 screws pass down through the head floor into nut pockets in the flange. You reach them through the front opening with the visor removed.

Assembly order:
1. Press the bearings into the hub.
2. Screw the hub to the roof.
3. Fix the horn disc to the horn.
4. Insert the servo into its pocket from below, with the disc entering the roof opening.
5. Lower the shaft through the bearings onto the disc's square boss, and drive the center screw.
6. Screw on the head.
7. Fit the camera to the visor, and press the visor in.
8. Plug in the servo lead, and close the shell over the base plate.

Service is the same steps in reverse.

### Head and camera

The head is one white shell, open at the front. The visor closes the front and carries the camera on four M2 screws (34 mm square). Clearance checks use the measured camera: a 38 × 38 mm board, a lens holder 15 mm across and 23 mm tall, a 6 mm heatsink, and a 4 mm connector. The camera cable leaves through a 17 × 10 mm hole in the head floor, crosses the neck gap behind the hub, and enters the body through a matching roof hole. A 30 × 30 × 30 mm slack loop inside the body absorbs the ±80° turn, and the Jetson plug space below it leads to a USB port. The horn disc holds its nut with two 0.4 mm lips at the pocket mouth.

## Measured alternatives

`hardware/enclosure/study.py` builds bare 3.2 mm shells and scores them with `hardware/printcheck.py` (results in `build/enclosure-study/study.json`, E). Concept A's 38 required parts total 34,887 mm² of overhang, 20 floating islands, and 11,075 mm² of thin surface (`hardware/printcheck-baseline.json`).

| Body split | Pieces | Overhang mm² | Floating islands | Outline change |
| --- | --- | --- | --- | --- |
| A0: one shell on its roof, plain shoulder fillet | 1 | 5,790 | 0 | 0 mm |
| **A1: one shell on its roof, 45° chamfer at the bed edge** | 1 | **0** | 0 | 1.8 mm |
| B: upright shell plus roof lid | 2 | 9 | 0 | 2.0 mm |
| C: front and rear halves, as in Concept A | 2 | 15,992 | 0 | 0 mm |

The design gate preferred B because the study shell A1 shows 617 mm² of thin surface. That thin area is the knife edge left where the cut crosses the 46° roll. The 3 mm flat seat removes it, while B would add a lid seam and its fasteners. Choose A1. Its open bottom is cut at Z 7.6 (`CUT_Z` in `body.py`). The opening is 131.7 × 110.3 mm, and the base plate covers the 140.0 × 118.6 mm outer edge.

| Servo drive | Minimum clearance | Closest |
| --- | --- | --- |
| **A: on the neck axis, turned 180°, 28.8 mm case (U)** | **4.0 mm** | Cavity roll |
| A: same, 35 mm datasheet height | 2.0 mm | Roof and cavity roll |
| B: offset at (12.5, −34) with two gears | 2.0 mm | USB extension |

Choose A. It removes both gears and the gear mount. In print orientation, the servo pocket rises from the roof, so it needs no support. The 4.0 mm clearance does not yet include the pocket walls. The pocket therefore has walls only on the servo's two long sides, and the builder checks them against the cavity.

## Acceptance

- Required printed parts: nine, down from 38.
- `printcheck.py`: zero floating islands and zero thin area under 2 mm on every required part. The checker skips a 1 mm band along sharp edges, except on parts that are mostly edges. Total overhang under 10% of the Concept A baseline (3,489 mm²) in `hardware/printcheck-baseline.json`. Each remaining exception is named: `base-plate` keeps 1 mm² at 1.87 mm on the acute end of the port skirt (`THIN_OK` in `body.py`).
- Every Concept A clearance check that applies still passes: hardware and reservations, plug access, fan and outlet paths, camera focus travel, microphone holes, and the head through ±80°. The vertical sweep of the populated base plate through the opening also passes.
- All parts slice in Bambu Studio on the P1S with 0.4 mm nozzle, PLA, 0.2 mm layers.
- Test pieces print first: one M3 nut pocket and screw boss, one catch, the hub with its bearing seats, and the horn disc on the horn.

Concept A outputs are tagged for archive and deleted once this design passes. Physical fit, cooling, acoustics, and powered motion stay U until printed tests.
