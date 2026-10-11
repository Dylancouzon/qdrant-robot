# Concept A removable casing prototype

Complete robot bounds are 148.6 × 127.2 × 236 mm. The 152 × 130 mm figures used by the generator are raw construction section limits.

The body tapers from 152 × 130 mm at its base to 128 × 110 mm at Z 160, with a 22 mm base roll and 20 mm shoulder roll. The 116 × 80 × 56 mm capsule head starts at Z 180 and ends at Z 236. White parts surround the black visor, integral light baffle and 40.4 mm camera opening. The raised black speaker grille centers at Z 48. All dimensions are millimeters.

This is a mechanical measurement prototype. CAD checks run on the Mac (E). Physical fits, retention, connector geometry, cooling, acoustics, and material life remain U. Inspect and slice each part in Bambu Studio before printing. Keep the prototype unpowered until its interfaces pass physical checks.

## Files and printing

Run `build/hardware-layout/venv/bin/python hardware/concept-a/casing.py` from the repository root. This rebuilds the checks, STEP assemblies, render, part manifest, and closed 3MF meshes under `output/casing/`. The manifest records each print orientation, bed size, flat contact area, and support requirement. The generator checks raw indexed mesh edges as well as imported mesh closure and millimeter dimensions.

Print `panel-socket-coupon.3mf` and `panel-tongue-coupon.3mf` first. Socket columns have total clearances of 0, 0.1, 0.2, and 0.3 mm, from left to right. Insert the tongue horizontally into each edge-open socket. The modeled panels use 0.2 mm total clearance. Select retention by coupon results before using real hardware. Adjust the source dimensions and regenerate if the coupon needs a different fit.

Print the body front shell with its front exterior on the bed. Print the rear cover with its rear exterior on the bed. Print the port panel with its outside face on the bed. Print the roof with its flat underside on the bed. Keep the joint posts upright. Inspect their 1.8 mm slot bridges. Print the roof bridge flat. Print its long pins upright on their heads with a brim. Print the keepers on their broad faces. Test the small keeper barbs before assembly.

Print the head front shell and visor with their front faces on the bed. Print the head rear cover with its rear face on the bed. The shallow decorative visor recess needs local support. Print the camera gauge frame with its front face on the bed. Print the other cradles and gauges with their floors on the bed. Some casing sockets and support blocks need local supports. The source exports these orientations directly.

## Body assembly

1. Test panel retention and release on printed parts before installing components. Rear tongues enter sockets along Y. The right panel enters along X. The roof lowers onto four perimeter posts.
2. Remove the roof, rear cover, right panel, and loose cradles. Keep the panel catches accessible.
3. Test the speaker and audio housings in the separate envelope gauges. Stop if a gauge loads a populated circuit board.
4. Install the speaker tray over its two base posts. Slide the speaker through the open rear at its final height, before installing the Jetson. The tray has front and side guides; its open rear avoids lifting the speaker into the audio support beams.
5. Fit the audio shelf over its two front support posts. Its front and left lips locate the reference housing. The right side stays open for the reserved USB extension.
6. Check servo admission with a dummy reference envelope before placing the Jetson. Its rear path crosses the Jetson location. Keep the owned servo separate until an installed mount and safe contact lands are defined. Install the Jetson tray over its four base posts. Its left and front lips locate the envelope. Its rear and right sides preserve the fan and plug reservations.
7. Use the joint instructions for the separate servo housing gauge and manual drive. Connect and grip plugs with the complete right panel removed.
8. Follow the open roof channel sequence below. Refit the right panel and rear cover. Remove the rear cover first when servicing the right rear sockets. Pull panels directly along their insertion directions. Do not pry against a circuit board.

The four component cradles are captured modules, rather than floating STEP parts. Body pedestals support the speaker and Jetson trays. Front-wall blocks support the audio shelf. The head floor supports the camera frame. Their nominal 0.4 mm envelope gaps permit gauge tests. They establish proposed locations; they do not certify housing contacts, PCB support lands, or final component retention. Verify safe contact lands before changing these gaps or adding contact shims.

## Head and joint interface

The structural roof occupies Z 156.8 to Z 160. Its central opening is 32.4 mm in diameter and opens to the rear edge. A separate bridge closes this admission channel. Only the two joint mounting posts enter the reserved 50 mm flange footprint. Their centers are X−21 and X 21, Y 0. Each post is 3 × 4 mm and extends to Z 165. Its through-slot is 1.8 × 6 × 1.8 mm, centered at Z 163.4. The joint builder supplies the flange and closure keys. Two long transverse pins retain the bridge at Y 25, Z 158.4. Their heads sit in roof edge recesses. Vertical keepers capture their inner ends at X±13.3. Keeper heads and barbs retain them above and below the bridge. Compress the barbs for removal. Verify their flex and retention with PLA before use.

The head floor occupies Z 180 to Z 183. It has a 15.2 mm central opening and 3.4 × 4.4 mm openings at X±18, Y 0. These receive the detachable joint flange posts. The 44 mm flange space below the head remains clear. Keep the rear cover open while inserting or removing the joint keys.


### Open roof channel assembly

1. Remove the rear cover, roof bridge, bridge pins, bridge keepers, and joint roof keys. Fit the roof plate onto its four perimeter posts.
2. Hold the preassembled joint 5.2 mm above its final position. Keep the complete head casing separate. Introduce the joint horizontally from the rear. The lower gear remains below the roof. The flange clears the roof post tops.
3. Center the joint at X 0, Y 0. Lower it 5.2 mm onto the roof posts. Insert the joint flange closure keys from the rear.
4. Slide the roof bridge forward from the rear at its final height. It enters beneath the seated flange. Insert each long transverse bridge pin from its roof edge recess.
5. Press the two vertical keepers through the bridge and pin slots. Their barbs capture the underside. Verify both keepers and pin heads before lifting the assembly.
6. Fit the neck cover, then install the head casing onto the flange posts with its rear cover open. Insert the head closure keys from the rear. Follow the camera sequence below.

Remove the head and reverse this sequence for service. Lift the joint 5.2 mm before sliding it rearward. The integrated checks sample rear joint and bridge admission every 0.5 mm, and joint lowering every 0.1 mm. These samples clear the modeled casing and cradles. The separate bridge admission check uses continuous prisms against the roof. Confirm physical removal and cable clearance between sampled positions.

1. Remove the visor, rear head cover, and camera cradle. Confirm camera thickness and edge contact lands with gauges.
2. Introduce the empty camera frame through the rear at 1.5 mm above its final height. Lower it onto the 0.8 mm floor posts at X−43.9 and X−10, Y−4. The frame clears the PCB envelope by 0.4 mm.
3. Insert the complete source camera through the installed frame from the rear. Its 37.8 mm opening clears the board, holder, heatsink, and both rear connector envelopes. The lower crossbar has a notch for the complete left head key and its insertion path.
4. Install the camera only after confirming safe edge support and release. Keep the full rear connector and cable pocket open.
5. Fit the black visor into its front opening. Its four tongues enter the front sockets. Refit the rear cover using its four small locator tongues. Neck-cover service requires removing the head, then lifting the cover 60 mm over the retained mechanism.

## External cable and port access

Use external camera routing for this prototype. The body rear and roof have aligned 10 mm edge-open exits at X 24. The head floor and rear cover have corresponding exits at X 24. Remove their covers to admit the complete connector. These exits clear the source camera cable pocket and the rear intake reservation. Physical cable slack, bend radius, pinching, and movement remain pending across the full yaw range. No strain-relief clamp is claimed until the actual cable jacket and safe contact are known.

The right panel has a large 24 mm wide, edge-open service opening. It preserves plug access and accepts later replaceable inserts. It does not establish the final power or USB socket coordinates. Use the existing standalone power-exit trial to measure the recessed upward elbow interface before designing a matching insert.

Rear vents align with the fan reservation. Left vents align with the outlet reservation. The speaker grille and two microphone holes stay open. Compare microphone placement, airflow, and acoustics against the owned hardware before selecting final channels or vent area.

## Check limits

The checker tests every assembled casing and cradle pair, all source hardware and reserved spaces, and both camera focus limits. It tests continuous component insertion prisms against the open casing and each matching cradle. The camera frame enters before the camera. Its 1.5 mm raised admission uses a continuous prism, followed by lowering checks every 0.1 mm. It permits only zero-volume mating surface contacts. Separate gauges stay outside the assembly. The component order and panel removals above are part of the admission procedure.

The STEP ghost assembly includes the source camera holder, board, heatsink, both rear connectors, and all source reservations. The exterior PNG uses triangles from these casing solids. Joint geometry is exported and checked separately by the integrating builder. Powered operation and physical print readiness require the remaining measurements and Bambu Studio inspection.

The component trays currently establish locations for an unpowered fit prototype. They do not provide verified positive retention. Do not power or move the assembled robot until safe contact lands and retention prevent components entering fan, cable, or PCB regions. Rear and right covers have sampled CAD removal checks with the roof, head, joint, neck and bridge removed. Actual release forces and cables remain unverified.

The installed robot STEP and viewer omit the loose hand-held drive gear coupon. Its separate joint export remains available for tooth-mesh tests; it has no installed pivot or powered horn coupling.
