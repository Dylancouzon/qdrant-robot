# Robot enclosure design requirements

Updated 2026-10-12 from Dylan's instructions. Read this file before continuing the enclosure design. Keep user requirements separate from proposed dimensions and untested fits.

## Required outcome

Dylan requested the simplest practical design on 2026-10-11. Reduce parts and assembly steps where fit, service, and retention permit. Provide a simple preview that shows printed parts, assembled views, internal components, and their connections. The preview must explain assembly without requiring CAD experience.

- Redesign the enclosure completely from the [original robot hardware](https://github.com/Dylancouzon/qdrant-edge-memory-robot/tree/main/hardware).
- Use its `claude-design.html` as a reference for component dimensions. Verify dimensions against the actual parts before completing their mounts.
- Provide printable 3MF files for the final enclosure and joint. Keep editable design sources and assembly instructions in this repository.
- Make the robot compact, easy to print, assemble, and service.
- Let the camera head turn horizontally to see other directions. Specify the actuator, joint, retention, mechanical connection, and cable routing.
- Electronics sit in loose pockets with clearance, held by walls, gravity, and a rib where they could fall (Dylan, 2026-10-12). Nothing is bolted except the camera board, which fastens with M2 screws through its own mounting holes.
- Provide access and clearance for the Jetson power plug, USB plugs, and installed cables.
- Provide an intake and exhaust path for the Jetson. Verify cooling with the assembled robot under its normal workload.
- Keep the microphone openings clear. Check speaker echo, fan noise, and motor noise during listening.

Dylan authorized head rotation despite the older no-servo rule. Decision H1 records this exception. Arms and other motion remain outside this enclosure task.

## Appearance and size preferences

Dylan clarified the appearance again on 2026-10-11. Use a neutral white body with a black visor and speaker grille. This supersedes the cream shell preference and the temporary graphite instruction. Use a clear trapezoid silhouette with wider lower body, narrower shoulders, and rounded shoulders and base. Raise the speaker grille and its component position above the earlier low placement. The rounded rectangular revision remains rejected. Review the actual tapered CAD silhouette before rebuilding detailed mounts or print exports.

Dylan liked Concept A, with a visor camera head and a stationary body. The current study places one speaker in the body to reduce moving bulk. Speaker eyes were considered, and Dylan accepts using one speaker because the speakers are bulky.

Dylan approved the updated [exterior concept](enclosure/exterior-concept.png) on 2026-10-11. Preserve its neutral white shell, matte black visor, smaller head, body speaker grille, and removable panel seams. The visor has one camera opening and a decorative right-hand circle. The picture sets the appearance target. CAD determines exact proportions, corner shapes, vents, and joints.

Dylan rejected the Concept A CAD exterior on 2026-10-11 because it resembled a "1980s computer". The simplified design of 2026-10-12 supersedes that shell and the planned exterior refinement. It keeps the appearance above: the tapered white body, the black visor head, the speaker grille, and the decorative circle.

The removable port-side panel now has prototype geometry and checked casing clearances (E). Actual USB plug insertion remains U. The 10 mm protrusion informs its installed pocket after the complete connector shape is measured.

## Electronics retention

Dylan requested press-fit retention for all electronics on 2026-10-11, and relaxed it on 2026-10-12. Parts now sit in loose pockets with clearance, held by walls, gravity, and a rib where they could fall. Most component housings are rectangular. The Jetson plastic edge opposite its connectors is 6 mm thick and extends 8 mm inward from that edge, as measured by Dylan. It slides straight down into a vertical slot that grips 6 mm of that strip. Preserve connector, fan, lens, and cable clearance. Printed pocket clearances still require coupon tests.

## Component dimension references

These dimensions come from reference designs or manufacturers (E). Fit against Dylan's parts remains unverified (U).

| Component | Reference envelope | Source and qualification |
| --- | --- | --- |
| Jetson | 103 × 90.5 × 34.77 mm, as a 6 × 8 mm tray strip, an 11 mm flat board, an I/O band, and a heatsink block. | NVIDIA kit drawing (O) and Dylan; the body holds the strip opposite the connectors in a slot. |
| Camera board | 37 × 37 mm; nominal thickness 1.6 mm, reference range 1.4–1.8 mm. | Original Claude design. |
| Camera optics | Holder diameter 26 mm; lens length 26–27.5 mm; about 100° diagonal field of view. | Original Claude design; verify aperture clearance throughout focus travel. |
| Camera rear heatsink | 26 × 26 × 10 mm. | Original Claude design; include both rear connector envelopes as well. |
| USB audio case | 53 × 23.5 × 14.6 mm, excluding its USB plug. | [Waveshare USB TO AUDIO](https://www.waveshare.com/usb-to-audio.htm). |
| Speaker | Reserve 100 × 45 × 21 mm. | [Waveshare speaker](https://www.waveshare.com/8ohm-5w-speaker.htm); its image gives smaller dimensions, so measure the owned speaker. |
| STS3215 housing | 45.22 × 24.72 × 35 mm. | [Waveshare documentation](https://www.waveshare.com/wiki/ST3215_Servo); confirm the linked drawing against the owned servo. |

The measured and sourced sizes are in [MEASUREMENTS.md](enclosure/MEASUREMENTS.md). The hardware boxes and their coordinates are in `enclosure/geometry.py`.

## Joint and electrical requirements

- Support the head with a defined bearing and retention arrangement. Avoid placing the head's entire structural load on the servo output.
- Keep the servo horn mechanically retained. Loose component pockets do not imply a friction-only horn connection.
- Provide mechanical travel limits and controlled acceleration. Verify clearance through the complete permitted movement.
- Admit the complete camera connectors during assembly. Provide cable strain relief, bend clearance, and accessible release features.
- Route the camera cable through the neck gap with a slack loop in the body (H6). Limit rotation to ±80°.
- Select the controller after selecting the actuator. STS3215 uses a TTL serial bus; PCA9685 controls PWM servos.
- Prefer Jetson control through a compatible interface without a separately programmed Uno when practical.
- Give the servo a compatible power supply. Identify the adapter revision before specifying its input voltage.
- Verify electrical compatibility, available current, and grounding before powered tests.

The study proposes ±70° normal travel and ±80° mechanical limits. These angles, bearing dimensions, gear geometry, and shaft dimensions remain prototype choices.

## Printing and release checks

- Design parts for the P1S bed and 0.4 mm nozzle. Prefer flat print bases and simple orientations with little support material.
- Select pocket clearances from physical coupons printed with the intended filament and settings.
- Verify each final 3MF has correct millimeter scale, closed meshes, and the intended part orientation.
- Inspect and slice each final part in Bambu Studio before marking it ready to print.
- Check component insertion, removal, connector access, and bearing retention on a joint prototype.
- Test cable movement, pinching, backlash, and physical stops over the full travel range.
- Check camera framing at both ends of focus travel and at the head's travel limits.
- Compare open and enclosed Jetson temperatures, fan behavior, and throttling under the same workload.
- Test microphone pickup during playback, fan operation, and head movement.

## Current delivery status

The [simplified enclosure](enclosure/README.md) replaced Concept A on 2026-10-12. Concept A is tagged `archive/concept-a-enclosure`. The new design has nine printed parts, 17 M3 screws, four M2 screws, and 13 M3 nuts. It keeps the approved exterior and uses no printed pin, key, keeper, strap, or gear.

All nine parts pass `printcheck.py` with zero floating islands and zero thin area, and 719.0 mm² of total overhang against 34,887 mm² for Concept A (E). Every part slices for the P1S in Bambu Studio and prints in 13.3 h with 490 g of PLA (E). The body and neck checks pass: hardware clearances, plug access, the vertical sweep of the populated base plate, and the head through ±80°. An [offline viewer](enclosure/output/robot-viewer.html) shows the assembled robot, turns the head, and lists the parts, fasteners, and steps.

The camera cable runs through the neck gap from a head floor hole to a roof hole, then through a slack loop to a Jetson USB port. A coupon plate and a Jetson slot coupon print first. Physical fit, cooling, acoustics, and powered motion stay U until printed tests.
