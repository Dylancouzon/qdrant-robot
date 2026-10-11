# Concept A mechanical prototype

Speaker and audio retention pass 182 targeted CAD checks; the casing passes 665 checks. Editable CAD and checked meshes are regenerated. The final viewer and all 57 P1S projects are current. Jetson and camera retainers remain dependent on contact measurements.

The tapered revision follows the requested rounded reference, with a neutral white body, black visor and raised removable black speaker grille. The finished body measures 148.6 × 127.2 × 160 mm and narrows toward 128 × 110 mm shoulder construction sections. The base roll is 22 mm and shoulder roll 20 mm. The capsule head measures 116 × 80 × 56 mm. Overall height is 236 mm (E). Complete component and cable reservations remain modeled. Physical retention and powered coupling require measurements.

The casing has 20 structural, cover, cradle, and retaining-key pieces. Separate rear and port covers give simpler service paths than one combined cover. The visor includes its camera light baffle and blind second-eye recess, without separate decorative parts. Four detachable cradles retain provisional interfaces so safe contact lands can be verified before populated electronics are installed.

![Actual robot casing and manual joint, shown from the front and rear](output/assembly/robot-preview.png)

## View the complete design

Open [the offline CAD viewer](output/assembly/robot-viewer.html) in a browser. The page includes an offline assembly guide, hardware quantities and status, and the printed parts list. Select front, rear, side, or 3D views. Turn the head through ±80°. Open the service covers and show component envelopes. The viewer draws the actual printed triangles. Hardware blocks represent reference envelopes and reserved spaces. Browser appearance remains U; the viewer control checks pass.

Use [the complete assembled STEP](output/assembly/robot-assembled.step) in a CAD application. The installed assembly includes casing, detachable cradles and retained joint parts. The loose hand-held drive gear is a separate mesh-test coupon; it has no installed pivot or powered coupling. The [approved exterior concept](output/exterior-concept.png) provides the appearance target. The CAD preview shows the current mechanical prototype, with a tapered body, compound shoulder/base rolls and a capsule head.

## Print files and assembly

Use [the organized STL files](output/Print-files/README.md) or [native P1S 3MF projects](output/Print-projects/README.md): Required first, then Optional, with White and Black folders. The 38 required pieces and 19 optional tests preserve their checked print orientations. All 57 STL files and repaired native P1S projects pass Bambu geometry import checks.

[Bambu P1S projects](output/bambu/) contain casing, joint, cradle, gauge, and coupon parts. Each project uses PLA, the 0.4 mm nozzle, 0.2 mm layers, three walls, and automatic tree supports. All 57 projects slice without warnings and pass native geometry import. Source and project hashes match the delivered files. Inspect supports and their removal paths before printing. Start with the small gauges and spare keys. Physical fits remain U.

The separate [casing meshes](output/casing/) and [joint meshes](output/joint/) use millimeter units and checked print orientations. These generic 3MF files contain geometry. Select printer settings when importing them directly. The P1S projects include settings and sliced previews. No print was sent.

Read [casing assembly](CASING_ASSEMBLY.md) and [joint assembly](JOINT_ASSEMBLY.md) before printing. The roof uses a removable bridge. Lift the preassembled joint 5.2 mm, slide it through the rear roof channel, and lower its flange onto the roof posts. Install the bridge and its retained pins afterward. Install the camera frame before the camera.

Four detachable cradles define the proposed Jetson, speaker, audio-case, and camera positions. Speaker and audio have removable keys with passing bounded CAD capture and service checks. Jetson and camera remain location gauges pending safe contact measurements. Verify housing contacts, release, and holding strength with the [retention coupons and guide](RETENTION_BRIEF.md) before installing populated electronics. Keep the owned servo separate until its installed retention is defined. The manual drive gear is a loose tooth-meshing coupon.

## Joint specification

Two 15 × 24 × 5 mm bearings support a 14.8 mm journal. Their centers are Z 154 and Z 170. Split tower seats measure 24.2 mm. The tower has a 32 mm diameter within the 32.4 mm roof channel. Its 50 mm flange sits at Z 160. The 44 mm rotating flange supports the head floor at Z 180.

Stationary keeper openings measure 22 mm. Rotating spacers measure 20 mm. Their radial separation is one mm. The initial axial freedom is 0.6 mm. Optional 0.2 and 0.4 mm shims are separate gauge parts. Verify actual race contact lands before using these dimensions.

Both gears have 34 teeth, module one, a 20° pressure angle, and 34 mm center spacing. Combined nominal tangential backlash is 0.25 mm. Continuous CAD tooth clearance passes. Actual solid stops contact at ±80.02087°. The proposed normal software range remains ±70°. Stop strength and physical tooth behavior remain U.

Use external camera routing for this manual prototype. Transverse retention keys occupy the proposed shaft passage. Complete connector admission through both closed bearing bores remains pending. Check cable slack, pinching, bend radius, and connector loading throughout physical movement.

## Power, USB, and cooling

Remove the right panel to grip and connect Jetson plugs. Its split service opening preserves access; final inserts require actual socket and connector measurements. The separate [power-exit trial](output/power-exit-trial-p1s.3mf) remains a hand-held gauge without casing attachment.

Keep the rear intake, left outlet, microphone holes, and speaker grille clear. Verify fan direction and compare open/enclosed cooling and acoustics under the same workload. Identify the bus adapter and supply before specifying servo wiring. Physical tests remain U.

## Checks and regeneration

[Integrated checks](output/assembly/checks.json) cover actual casing/joint intersections, full yaw separation bounds, rear key access, and sampled joint/bridge admission. [Casing checks](output/casing/checks.json) cover panel and cradle separation, hardware reservations, component admission, and both reference lens lengths. [Joint checks](output/joint/checks.json) cover bearings, retained keys, stops, and real teeth. [Slicing checks](output/bambu/slice-checks.json) record each source hash, project hash, result, warning, and estimate.

Use Python 3.12 with [requirements.lock](requirements.lock). Run `layout.py`, `power_exit.py`, `casing.py`, `joint.py`, `check_retention.py`, `assembly.py`, and `bambu.py` in that order. Run `node hardware/concept-a/check-assembly-viewer.cjs` from the repository root. The CAD environment is `build/hardware-layout/venv/bin/python`. Bambu packaging uses the installed macOS application and the saved native P1S power-trial project as its settings template.

The shared exporter welds indexed CAD face seams and checks every mesh edge twice. Generators check millimeter scale, closed volume, connected solids, and bed fit. Automatic slicing establishes printable paths. Physical coupon results, safe electronics support, material life, cable movement, powered motion, cooling, and acoustics remain U.

Development history and rejected evidence are in [the build log](BUILD_LOG.md). Next-session constraints are in [the handoff](HANDOFF.md).

## Sources

- [Original hardware design](https://github.com/Dylancouzon/qdrant-edge-memory-robot/blob/cfc0dd2c5bb540f08149213c43bd33ba2d0c27f9/hardware/claude-design.html) supplies the Jetson and complete camera reference dimensions.
- [Waveshare USB audio](https://www.waveshare.com/usb-to-audio.htm) supplies the 53 × 23.5 × 14.6 mm case, excluding its USB plug.
- [Waveshare speaker](https://www.waveshare.com/8ohm-5w-speaker.htm) specifies 100 × 45 × 21 mm. Its image gives smaller dimensions; measure the owned speaker.
- [Waveshare servo documentation](https://www.waveshare.com/wiki/ST3215_Servo) supplies the proposed 45.22 × 24.72 × 35 mm housing envelope. Verify it against the owned STS3215.
- [SO-ARM100 bill of materials](https://github.com/TheRobotStudio/SO-ARM100/blob/a758567c3978dfeefe282ede0500085a48fe8f78/README.md) lists the USB-C bus-servo board and 7.4 V servos.

Start with the 65 × 26 × 6 mm panel socket coupon and its separate tongue before printing the enclosure. Measure owned component sizes, safe support lands, servo ears and horn, bearing race lands, connector positions and camera cable bend before approving retention or powered operation. The full assembly remains an unpowered fit prototype until those interfaces are verified.
