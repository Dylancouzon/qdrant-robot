# Manual yaw joint prototype

This joint supports manual fit tests with two 15 × 24 × 5 mm closed bearings. CAD dimensions are E. Physical fit and bearing contact lands are U. Inspect and slice every part in Bambu Studio before printing.

Run `build/hardware-layout/venv/bin/python hardware/concept-a/joint.py` from the repository root. The generator writes separate closed, millimeter 3MF meshes, an assembled STEP, hardware ghosts, a manifest, checks, and dimensions into `output/joint/`. STEP retains assembly coordinates. Each 3MF uses its listed bed orientation.

## Parts and interfaces

The one-piece gear shaft has a 14.8 mm journal and a 10 mm bore. Both bearings enter from its open upper end. The lower collar is integral. The head flange is detachable and uses a D-shaped bore plus a retained transverse key. That key blocks the shaft bore. Route the camera cable externally during manual tests.

The stationary tower has two halves. Each 24.2 mm seat is 5.2 mm high. Keeper lips have 22 mm openings. Rotating collars and the middle spacer have 20 mm outside diameters. These dimensions provide one mm radial separation between stationary lips and rotating collars. Each lip overlaps a bearing outside diameter by one mm. Confirm that this overlap lands on the actual outer race.

The lower collar ends at Z151.2. The upper collar begins at Z172.8. Two bearings and the 11 mm spacer occupy 21 mm. Their collar span is 21.6 mm. The resulting nominal axial freedom is 0.6 mm. Select optional 0.2 or 0.4 mm shims only after measuring the assembled movement. Keep measurable axial freedom. Confirm every rotating contact touches only the actual inner race.

The tower passes through a 32.4 mm roof opening. Its 50 mm flange sits at Z160. Two casing posts at X±21 pass through its rectangular holes. Retained roof keys enter along Y. The tower has an upper transverse notch for shaft-key installation. The tower halves use four cross pins along X. Each pin has a head and a separate keeper outside the lug face. The two closure rows sit at Z164 and Z170. Their keepers have external tapered barbs.

The 44 mm head flange ends at Z180. Its two torque posts sit at X±18. They enter the head floor and end at Z185.5. Retained head keys enter along Y at Z183.8. Their 1.3 × 1.2 mm sections enter 1.6 × 1.4 mm slots. Their barbs sit outside the post. Verify barb flex and removal on printed spare keys. The camera board begins at Z186.5, above these posts.

Both gears have 34 involute teeth, module one, and a 20-degree pressure angle. Their pitch diameters are 34 mm. Their centers are 34 mm apart. Each tooth loses 0.125 mm tangential thickness, providing 0.25 mm nominal combined backlash. The driven gear starts at zero degrees. The drive gear starts at 180/34 degrees. It turns by the opposite yaw angle. A fine clearance check samples one tooth period and compares solid distance with an angular displacement bound.

The drive gear is a loose hand-held meshing coupon. Its displayed position defines the gear mesh test. It has no stationary pivot or structural retention. Its center opening provides no servo horn retention. The separate horn coupon checks only the proposed 19.2 mm horn outside diameter against a 19.6 mm opening. Source holes lie on a 14 mm pitch circle, but their threads and screw lengths remain U. Do not connect servo power through this prototype.

The servo housing gauge is a separate open-top fit coupon. It checks the proposed 45.22 × 24.72 mm housing footprint. It provides no installed servo retention. Its contact regions remain U. Check the gauge before defining the housing supports or mounting ears.

## Assembly

1. Inspect both bearing race faces. Mark their inner and outer contact lands.
2. Print the keys and housing gauge first. Check fit, barb flex, and accessible release with spare parts.
3. Slide the lower bearing over the open journal until it reaches its lower position.
4. Slide the middle spacer over the same open journal.
5. Slide the upper bearing over the open journal.
6. Close both tower halves around the bearings. Fit all four cross pins, then fit their keepers.
7. Remove the casing neck bridge. Lift the preassembled joint 5.2 mm above its final position.
8. Slide the joint through the rear channel. Keep its gear below the roof and flange above the post tops.
9. Lower the joint 5.2 mm at the final axis position.
10. Seat the tower flange over the casing posts. Fit both roof keys from the open service side.
11. Slide the detachable head flange over the shaft D-flat. Fit its transverse shaft key through the hub and shaft.
12. Measure axial movement. Add a selected adjustment shim only after disassembly if clearance requires it.
13. Lower the head floor over the two torque posts. Fit the head keys along Y with its cover removed.
14. Keep the camera cable external. Leave enough slack for manual movement and watch the complete cable throughout travel.
15. Align the manual drive blank at its specified initial phase. Turn both gears by hand without attaching a powered servo.

Release the barbs with accessible tools before withdrawing keys. Do not force a populated board, bearing race, or camera connector during assembly.

## Verification and printing limits

`checks.json` records exact-solid printed part intersections, hardware separation, bearing admission, gear mesh samples, and complete stop-web intersections. Gear clearance samples cover ±80 degrees at two-degree intervals. The fine gear check uses 109 positions across one tooth period. It bounds motion between adjacent samples with both gear outside radii. Read its minimum distance and motion bound in the generated checks. Check physical tooth mesh through the complete travel after printing.

The rotating stop tab occupies R18 to R23 at Z173.5 to Z177. Fixed ribs include their supporting webs. A binary search measures first solid contact in each direction. The selected rib angle is ±92.7 degrees. Read the measured contact angles from the generated checks.

Print tower halves with the seam against the bed. Their bearing seat ceilings and closure lugs require support inspection. Print the head flange upright on its annular hub base. Support its flange underside, stop tab, and transverse channel. Print the gear shaft upright with support beneath its collar. Print rectangular keys and pins on their flat faces. The manifest describes each orientation and support requirement. Remove support without changing bearing lands or tooth profiles.

Physical bearing fits, race lands, key retention, PLA wear, backlash, servo mounting, cable motion, and camera cable strain relief remain U. The final external cable route requires a separate physical movement test. Powered motion remains pending verified horn geometry, installed servo retention, electrical compatibility, and load testing.
