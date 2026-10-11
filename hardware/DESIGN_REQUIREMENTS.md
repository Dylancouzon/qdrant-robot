# Robot enclosure design requirements

Updated 2026-10-11 from Dylan's instructions. Read this file before continuing the enclosure design. Keep user requirements separate from proposed dimensions and untested fits.

## Required outcome

Dylan requested the simplest practical design on 2026-10-11. Reduce parts and assembly steps where fit, service, and retention permit. Provide a simple preview that shows printed parts, assembled views, internal components, and their connections. The preview must explain assembly without requiring CAD experience.

- Redesign the enclosure completely from the [original robot hardware](https://github.com/Dylancouzon/qdrant-edge-memory-robot/tree/main/hardware).
- Use its `claude-design.html` as a reference for component dimensions. Verify dimensions against the actual parts before completing their mounts.
- Provide printable 3MF files for the final enclosure and joint. Keep editable design sources and assembly instructions in this repository.
- Make the robot compact, easy to print, assemble, and service.
- Let the camera head turn horizontally to see other directions. Specify the actuator, joint, retention, mechanical connection, and cable routing.
- Preserve press-fit component installation with removable catches. Test retention and release without bending populated circuit boards.
- Provide access and clearance for the Jetson power plug, USB plugs, and installed cables.
- Provide an intake and exhaust path for the Jetson. Verify cooling with the assembled robot under its normal workload.
- Keep the microphone openings clear. Check speaker echo, fan noise, and motor noise during listening.

Dylan authorized head rotation despite the older no-servo rule. Decision H1 records this exception. Arms and other motion remain outside this enclosure task.

## Appearance and size preferences

Dylan clarified the appearance again on 2026-10-11. Use a neutral white body with a black visor and speaker grille. This supersedes the cream shell preference and the temporary graphite instruction. Use a clear trapezoid silhouette with wider lower body, narrower shoulders, and rounded shoulders and base. Raise the speaker grille and its component position above the earlier low placement. The rounded rectangular revision remains rejected. Review the actual tapered CAD silhouette before rebuilding detailed mounts or print exports.

Dylan liked Concept A, with a visor camera head and a stationary body. The current study places one speaker in the body to reduce moving bulk. Speaker eyes were considered, and Dylan accepts using one speaker because the speakers are bulky.

Dylan approved the updated [exterior concept](concept-a/output/exterior-concept.png) on 2026-10-11. Preserve its neutral white shell, matte black visor, smaller head, body speaker grille, and removable panel seams. The visor has one camera opening and a decorative right-hand circle. The picture sets the appearance target. CAD determines exact proportions, corner shapes, vents, and joints.

Dylan rejected the actual CAD exterior on 2026-10-11 because it resembles a "1980s computer" and needs substantial refinement. The mechanical prototype remains a fit study. Its boxy shell is not an approved final appearance. In the next session, Dylan plans to use an Astra agent to refine the exterior. Preserve the approved concept as the appearance target, and reassess the mechanical interfaces where that refinement requires changes.

Dylan identified servo height as a problem. Select a short servo with its output shaft pointing upward for head rotation. Restrict purchases to Amazon and favor inexpensive options. Dylan rejected the Hitec D145SW because of its cost and the direction of its thin dimension. Keep the owned STS3215 unless an alternative gives a substantial improvement. Dylan rejected replacing it for only 6 mm of height reduction. Prioritize rearranging the existing hardware; no replacement purchase has been authorized.

## Owned equipment

| Item | Confirmed information | Information still needed |
| --- | --- | --- |
| Printer | Bambu Lab P1S with the default 0.4 mm nozzle. Bambu Studio is set up. | Physical coupon results. |
| Filament | PLA is preferred. PETG is available as an alternative. | Thermal suitability and retention after repeated assembly. |
| Main computer | Jetson Orin Nano Super 8 GB. | Actual port coordinates, fan orientation, and complete installed plug shapes. |
| Camera | Arducam IMX291 USB camera from the reference design. | Actual board thickness, connector dimensions, focus travel, and cable bend radius. |
| Audio | Waveshare USB TO AUDIO with an 8 Ω, 5 W speaker. | Actual speaker size, microphone opening positions, and acoustic performance. |
| Servos | STS3215 servos rated for 7.4 V. Parts from an Uno R3 super starter kit are also available. | Starter-kit servo model and exact STS3215 mounting geometry. |
| Servo adapter | Dylan may have the adapter used in SO-ARM100. | Board identity, revision, supply requirements, and connector clearances. |
| Power plug | Dylan reports an 11 mm outside diameter and 21 mm added connector length: 11 mm straight outward reach, followed by a 10 mm right-angle section. The elbow rotates in any direction. | Exact elbow shape and socket coordinates. |
| USB cables | JUXINICE 4-inch, down-angle, 90° USB 2.0 A male-to-female flat extensions. Dylan reports 10 mm protrusion when plugged into the USB socket. | Full connector width and height, socket datums, and insertion travel. |

## Cable installation and service access

Dylan measured 10 mm installed USB cable protrusion on 2026-10-11 and reports that every cable is flexible. Apply this measurement to the measured USB connection. Verify other plug types separately. Flexibility does not establish a minimum bend radius or resistance to repeated head movement.

- Separate installed plug clearance from the space needed to insert and remove the plug.
- Use a removable panel on the Jetson port side so plugs can enter along the socket axis from outside the body.
- Keep each plug accessible for gripping its housing during insertion and removal.
- Close the panel after connecting cables. Provide clearance for the installed connector, cable turn, and strain relief.
- Shape the power cable exit to follow its right-angle bend. Keep the rigid elbow clear of the case wall.
- Split the exit at the removable panel edge so the rigid elbow can enter without threading through a closed hole.
- Use edge-open cable exits or split covers where a cable passes through a removable panel. Avoid threading large plugs through small cable holes.
- Make the camera connector accessible through the rear head cover. Use a split neck passage for assembled cable connectors.
- Preserve slack for service and head rotation. Check the closed covers throughout the complete rotation range.
- Keep the existing 24 mm combined USB/power reservation until the power connector and complete access geometry are verified.

Dylan clarified the installed power plug on 2026-10-11. Its outside diameter is 11 mm. Its added connector length comprises an 11 mm straight section and a 10 mm right-angle section. The elbow rotates in any direction. Route the last section outside the case. Treat 21 mm as the described connector length, not a straight outward clearance requirement. Prototype an upward exit through an edge-open recessed insert. The wall position and exit dimensions remain U until the installed shape and socket position are checked.

The removable port-side panel now has prototype geometry and checked casing clearances (E). Actual USB plug insertion remains U. The 10 mm protrusion informs its installed pocket after the complete connector shape is measured.

## Component dimension references

These dimensions come from reference designs or manufacturers (E). Fit against Dylan's parts remains unverified (U).

| Component | Reference envelope | Source and qualification |
| --- | --- | --- |
| Jetson | 103 × 90.5 × 35 mm. | Original Claude design; include separate plug and airflow spaces. |
| Camera board | 37 × 37 mm; nominal thickness 1.6 mm, reference range 1.4–1.8 mm. | Original Claude design. |
| Camera optics | Holder diameter 26 mm; lens length 26–27.5 mm; about 100° diagonal field of view. | Original Claude design; verify aperture clearance throughout focus travel. |
| Camera rear heatsink | 26 × 26 × 10 mm. | Original Claude design; include both rear connector envelopes as well. |
| USB audio case | 53 × 23.5 × 14.6 mm, excluding its USB plug. | [Waveshare USB TO AUDIO](https://www.waveshare.com/usb-to-audio.htm). |
| Speaker | Reserve 100 × 45 × 21 mm. | [Waveshare speaker](https://www.waveshare.com/8ohm-5w-speaker.htm); its image gives smaller dimensions, so measure the owned speaker. |
| STS3215 housing | 45.22 × 24.72 × 35 mm. | [Waveshare documentation](https://www.waveshare.com/wiki/ST3215_Servo); confirm the linked drawing against the owned servo. |

The complete reference dimensions, connector envelopes, and proposed coordinates are documented in [the prototype](concept-a/README.md), its manifests, and its assembled STEP.

## Joint and electrical requirements

- Support the head with a defined bearing and retention arrangement. Avoid placing the head's entire structural load on the servo output.
- Keep the servo horn mechanically retained. Press-fit component installation does not imply a friction-only horn connection.
- Provide mechanical travel limits and controlled acceleration. Verify clearance through the complete permitted movement.
- Admit the complete camera connectors during assembly. Provide cable strain relief, bend clearance, and accessible release features.
- Use limited rotation with a cable loop unless a different cable interface is selected and validated.
- Select the controller after selecting the actuator. STS3215 uses a TTL serial bus; PCA9685 controls PWM servos.
- Prefer Jetson control through a compatible interface without a separately programmed Uno when practical.
- Give the servo a compatible power supply. Identify the adapter revision before specifying its input voltage.
- Verify electrical compatibility, available current, and grounding before powered tests.

The study proposes ±70° normal travel and ±80° mechanical limits. These angles, bearing dimensions, gear geometry, and shaft dimensions remain prototype choices.

## Printing and release checks

- Design parts for the P1S bed and 0.4 mm nozzle. Prefer flat print bases and simple orientations with little support material.
- Select press-fit clearances from physical coupons printed with the intended filament and settings.
- Verify each final 3MF has correct millimeter scale, closed meshes, and the intended part orientation.
- Inspect and slice each final part in Bambu Studio before marking it ready to print.
- Check component insertion, removal, connector access, and bearing retention on a joint prototype.
- Test cable movement, pinching, backlash, and physical stops over the full travel range.
- Check camera framing at both ends of focus travel and at the head's travel limits.
- Compare open and enclosed Jetson temperatures, fan behavior, and throttling under the same workload.
- Test microphone pickup during playback, fan operation, and head movement.

## Current delivery status

The [Concept A mechanical prototype](concept-a/README.md) now includes an actual removable casing, four detachable gauge cradles, a split bearing tower, retained keys, manual gears, and solid stops. Its complete STEP and CAD-derived preview show the assembled design. An offline viewer uses actual triangles and provides head yaw and service-cover controls.

There are 46 generic prototype 3MF files and 46 individually sliced P1S projects. Casing checks pass 582 checks, joint checks pass 286, and integrated checks pass 332 (E). The shared mesh exporter checks welded indexed seams, millimeter scale, and closed volumes. Physical fit remains U.

The roof uses a removable bridge to admit the assembled joint. The camera frame enters before the camera. The manual prototype uses an external camera cable loop. Both closed bearing bores must admit the complete connector before adopting a hidden cable route.

Keep the servo separate until its contact lands, mounting ears, horn holes, and supplied retaining hardware are verified. Its housing gauge and drive gear are separate manual test pieces. The power-exit trial remains separate until socket positions and installed plug shapes are measured. Component retention, cable motion, strain relief, cooling, acoustics, and powered load tests remain U.
