# Concept A packaging study

The visor concept keeps one speaker and the Jetson in a stationary body. The camera head rotates on a bearing-supported neck. This study reserves the hardware, plugs, cables, and airflow spaces. It does not contain a finished printable casing or component mounts.

## Review the layout

Open `output/layout-viewer.html` in a browser. Select a component to see its dimensions and source. Change the view or head angle to inspect the layout. Joint outlines are simplified; STEP includes the spacer, collar, and keeper. Reserved spaces have translucent fills. The viewer works offline and uses no external libraries.

The body envelope is 136 × 112 × 160 mm. The head envelope is 100 × 72 × 50 mm. Overall height is 230 mm. The rotating head sweeps a 123.22 mm diameter. These are calculated Mac dimensions (E), not a measured assembled robot. The final rounded casing may need more room.

`output/layout-study.step` contains the same component envelopes, shaft, bearings, flange, keeper, collar, and drive reservations. The drive circles reserve two module-one, 34-tooth gears at 34 mm center spacing. They do not contain gear teeth. Shell blocks deliberately overlap their contents because they describe the outside envelope. STEP viewing transparency depends on the receiving CAD application.

`output/layout-dimensions.png` and `.svg` show front, side, and top projections. `output/checks.json` records the checks and unresolved physical requirements.

## Print the fit coupons

Use the Bambu Lab P1S, a 0.4 mm nozzle, PLA, 0.2 mm layers, and three walls. Keep scale at 100%. Place the flat base on the bed. Both coupons have open vertical holes or slots and need no supports. The 3MF files contain geometry and millimeter units; select the P1S and filament profile in Bambu Studio. They contain no saved slicing settings.

- `output/bearing-fit.3mf` has four through holes. From left to right, their modeled diameters are 23.9, 24.0, 24.1, and 24.2 mm. The coupon is 152 × 36 × 6 mm. Use a 24 mm bearing or measured gauge. Select a fit that seats without damaging the bearing. Retention still needs a shoulder and keeper.
- `output/camera-thickness-fit.3mf` has three 38 mm-wide slots. From front to rear in CAD Y, their widths are 1.8, 1.9, and 2.0 mm. The coupon is 44 × 36 × 10 mm. Start with a measured scrap gauge, then test a bare camera-board edge without force. These slots establish clearance; a later removable clamp supplies retention.

The camera board reference permits 1.4–1.8 mm thickness. A tight slot can damage a populated board. These coupons do not validate the Jetson cradle, servo cradle, complete neck, or casing.

## Revised arrangement

Keep the owned STS3215 upright, with its output shaft vertical. Rotate its housing 90° around that axis and move it into the front upper body. Lower the bus-interface reservation by 6 mm. The resulting head envelope and neck reduce overall height by 25 mm, from 255 to 230 mm (E), without replacing the servo. The body envelope stays unchanged.

The drive now sits forward of the central shaft. Its addendum circle leaves 1.6 mm to the nominal inner front wall. The camera rear pocket leaves 1.1 mm vertically and 2.1 mm at the left inner wall. These are envelope clearances; final catches, rounded corners, and gear housing may require enlargement. Do not freeze these dimensions before modeling their mounts.

Joint solid checks now include bearings, shaft, flange, upper spacer, collar, keeper, and gear reservations against stationary components and each other. The complete illustrative cable tube clears these joint solids across 81 yaw positions. A conservative distance check covers every straight segment; this verifies geometric separation, not physical bend behavior. The shaft gear bore is 15 mm to match the shaft envelope. Addendum-circle overlap at the intended tooth mesh is excluded; actual teeth and coupling remain unmodeled. Both 26 mm and 27.5 mm lens lengths pass the revised ideal aperture check.

The shorter illustrative lower cable loop occupies Z116–132 and contracts gradually to the shaft center. Its length still varies with rotation. A physical cable and its bend specification must establish whether this reduced space works.

## Connection proposal

Use the owned 7.4 V STS3215 as the actuator candidate. Its housing uses the manufacturer envelope. The linked drawing labels the part SCS215; verify the owned servo before building its cradle. The source horn offset puts its axis 10.11 mm from the end. The layout aligns that proposed axis with the offset drive reservation.

The SO-ARM100 project lists a Waveshare USB-C motor control board. If Dylan owns a compatible board, connect a Jetson USB-A port to its USB-C port, then connect the servo to its TTL bus. The adapter handles the bus interface. This route needs no separately programmed Uno. The PCA9685 proposal applies to PWM servos and does not control the STS3215.

Identify the board version before selecting power. The current Waveshare adapter differs from older boards and includes regulated servo power. Match its input and servo output to the owned hardware. Reserve a separate power branch; check the adapter, supply rating, stall current, and common-ground connection before any powered test. The Jetson GPIO header does not power the servo.

Two 15 × 24 × 5 mm bearings have centers at Z154 and Z170. The proposed shaft has a 15 mm outside diameter and 10 mm passage. Its flange, upper spacer, lower collar, and housing keeper reserve a load path independent of the servo. Bearing contact lands and positive shaft coupling need actual component drawings. A shaft split and side-loading head opening must admit complete camera connectors. Software travel targets ±70°, with mechanical stops beyond that at ±80°. Stop strength, horn coupling, gear backlash, and bearing fit remain U.

## Component retention and access

Keep component installation as press fits with removable positive catches. Support the camera on its board edges. Support the Jetson at verified carrier-board mounting regions. Hold the servo housing in a keyed cradle and retain it at supported case features. Keep release tabs accessible through the open body or head cover. Do not transfer the old rigid Jetson squeeze into this layout without a force test. The servo horn retains its supplied screw; a friction-only horn connection is not proposed.

The packaging model does not yet include these mounts, snap catches, the split shaft, the bearing housing, physical stops, or cable strain relief. Assembly access remains a planned sequence in the viewer, not a tested insertion sweep.

## Cable and cooling requirements

Dylan owns JUXINICE 4-inch down-angle USB-A extensions. Their molded connector sizes and bend directions remain U. The model reserves side plug space and an audio extension pocket. Confirm socket coordinates, complete plug shapes, and installed cable paths before shrinking the body.

The orange cable curve samples a loop below the shaft and routing through the head. The coil is tested against expanded stationary boxes every 2° over ±80°. Its length changes across angles, so it does not simulate a constant-length physical cable. The upper route, minimum bend radius, connector insertion, strain relief at both ends, pinching, and fatigue still need physical verification. Its changing length is recorded in `checks.json`.

The 22 mm inlet reservation must align with the actual fan inlet. A separate side outlet reserves exhaust space. The layout establishes space only. Shape the actual vent and airflow path after confirming the kit orientation. Compare open and enclosed Jetson temperature, fan speed, and throttling under the same robot workload. Test microphone noise and speaker playback as well. Check PLA retention and deformation under those temperatures; use PETG for affected mounts if the physical tests require it.

## Reproduce the study

Create a Python 3.12 environment outside the runtime environment. Install `requirements.lock` there. Run `layout.py`, then `node check-viewer.cjs` from this directory. The generator checks solid validity, envelope containment, component intersections, ideal optical clearance, bearing spacing, and the illustrative lower cable loop. It independently reloads each 3MF and checks closed volume and exported scale. The Node check exercises viewer logic with a simulated canvas, not browser appearance.

The generator and exports passed their Mac checks. Browser opening was blocked by the local-file URL policy. Bambu Studio inspection timed out. Slicer appearance and printing remain unverified; neither tool failure is a print approval.

## Sources

- [Original hardware design](https://github.com/Dylancouzon/qdrant-edge-memory-robot/blob/cfc0dd2c5bb540f08149213c43bd33ba2d0c27f9/hardware/claude-design.html) supplies the Jetson and camera dimensions, including both rear connector envelopes.
- [Waveshare USB audio](https://www.waveshare.com/usb-to-audio.htm) supplies the 53 × 23.5 × 14.6 mm case dimensions, excluding the USB plug.
- [Waveshare speaker](https://www.waveshare.com/8ohm-5w-speaker.htm) specifies 100 × 45 × 21 mm, while its image labels 92 × 36 mm. The layout uses the larger envelope pending physical measurement.
- [Waveshare servo documentation](https://www.waveshare.com/wiki/ST3215_Servo) links the 2D drawing. The source envelope is 45.22 × 24.72 × 35 mm; owned-hardware fit is U.
- [SO-ARM100 bill of materials](https://github.com/TheRobotStudio/SO-ARM100/blob/a758567c3978dfeefe282ede0500085a48fe8f78/README.md) lists the USB-C bus-servo board and 7.4 V servos.
- [Waveshare Bus Servo Adapter A](https://www.waveshare.com/bus-servo-adapter-a.htm) supplies USB/UART modes and the current 42 × 33 mm PCB drawing. Thickness and owned-board identity remain U.
