# Concept A: dimensioned packaging study

Build a reviewable internal layout and STEP assembly for the visor concept. This task does not release a complete enclosure for printing. Dylan authorized a rotating head on 2026-10-11, replacing the no-servo requirement for this enclosure. Preserve press-fit component installation with removable positive catches. Fit, acoustics, cooling, and motion remain unverified on hardware (U).

## Alternatives and measurements

A body-mounted speaker keeps the head light. A head-mounted speaker adds a 100 × 45 × 21 mm envelope. Compare head size, moving mass, and cable count in the same layout. Select the body-mounted speaker for this packaging study.

A pair of 15 × 24 × 5 mm bearings supports a hollow shaft with an offset geared servo. A printed plain bearing is cheaper but depends on sliding friction and print finish. Compare radial play, turning resistance with camera cables installed, noise, and wear in a small physical joint test. Use the ball-bearing envelope in the layout; release neither joint until tested.

A compatible USB TTL bus adapter can control the owned STS3215 from the Jetson. Direct UART would require a compatible half-duplex interface and verified signal levels. Reserve the USB-adapter route and independent servo power. Identify the owned adapter before selecting its supply. PCA9685 does not control STS3215.

## Deliverables

Create a parameter-driven STEP packaging assembly, dimensioned front/side/top drawings, an interactive cutaway with horizontal rotation, and a check report. Model hardware and connector reservations distinctly from printed parts. Show the source and confidence of every hardware measurement. Export only fit coupons as printable 3MF if their geometry and scale pass checks. Do not call an envelope model a printable enclosure.

## Proposed checks

Check solid validity, body/head containment, component separation, reserved plug and intake spaces, and head clearance across −80° to +80°. Calculate the head's rotation footprint. Check camera aperture geometry for the source's 100° diagonal field of view; confirm live framing later. Keep printable joints removable and cable insertion possible without removing or cutting connectors. Place air intake behind the stock fan and exhaust separately. Measure temperature and fan speed on the Jetson after a physical casing exists; a space reservation does not prove cooling.

## Source and unknowns

The reference is Dylancouzon/qdrant-edge-memory-robot at cfc0dd2c5bb540f08149213c43bd33ba2d0c27f9, hardware/claude-design.html and docs/hardware-parts.md. Jetson envelope: 103 × 90.5 × 35 mm. Camera: 37 × 37 × 1.6 mm board, 26 mm holder diameter, 27.5 mm maximum lens length, 26 × 26 × 10 mm rear heatsink. Carry forward the measured rear connector ranges, not just a board box.

Waveshare publishes 53 × 23.5 × 14.6 mm for the USB audio case, excluding its USB plug. Its speaker specification gives 100 × 45 × 21 mm, while its picture gives 92 × 36 mm. Reserve the larger speaker envelope pending measurement. The USB adapter needs an extension to put its microphones near the front.

Unknowns: physical print fits, camera cable ends and minimum bend radius, complete USB/barrel connector shapes, actual port and fan locations, power adapter rating, exact servo mating dimensions, adapter revision, regulator model, and actual speaker size. Dimensions assigned to these items are explicitly reservations (U). Do not freeze the mating parts against them.

## Design review changes

The fan inlet is a provisional rear-side reservation; its alignment must be checked against the actual kit. Reserve a separate outlet, then validate the physical airflow path. The source is Waveshare USB TO AUDIO, https://www.waveshare.com/usb-to-audio.htm, and its paired speaker, https://www.waveshare.com/8ohm-5w-speaker.htm. Manufacturer measurements are E; fit of Dylan's actual parts is U.

Use two bearings with 16 mm between their centers, a shaft shoulder, and a removable retaining collar. The layout models these reservations, not validated bearing fits. The load path is head flange, shaft shoulder, bearing inner ring, bearing outer ring, housing, and body frame. An axial keeper and lower collar capture both directions. Actual catches must be tested for release force and retention without PCB bending.

Reserve a cable loop below the shaft, a center passage through the neck, and routing behind the camera. Model a candidate deforming loop over the full ±80° range with fixed sample count, and check its conservative swept clearance against component envelopes. The visualization labels the cable curve as illustrative: path length, minimum bend radius, strain relief, and fatigue still need the selected cable and physical test. A connector-loading split in the shaft is a future interface requirement, not a validated printable part. Stops are reservations at ±80°; normal software travel is ±70°, pending selected servo travel.

Keep intended camera contacts on board edges and Jetson contacts on the carrier's supported mounting regions. The current study contains no interference-fit mounts. The coupon checks select a later fit; a physical insertion test must establish safe force. Mark every drive, regulator, mount, fan, and cable dimension that lacks a selected part as U.

## Owned hardware update

Dylan has a Bambu Lab P1S with its default 0.4 mm nozzle, prefers PLA, and can use PETG. He owns 7.4 V STS3215 servos and may own the SO-ARM100 USB bus adapter. The small servo in the Uno starter kit has no confirmed model. Use the STS3215 housing as the candidate envelope instead of the PWM microservo; PCA9685 remains only a rejected alternative for that servo. Source: https://www.waveshare.com/wiki/ST3215_Servo and its linked mechanical drawing. The drawing's title is SCS215; confirm its applicability against the owned STS3215 before cutting mating features. The horn axis is 10.11 mm from the end of the 45.22 mm housing in that drawing.

The SO-ARM100 bill of materials at a758567c3978dfeefe282ede0500085a48fe8f78 lists a Waveshare motor control board with USB-C. https://www.waveshare.com/bus-servo-adapter-a.htm describes USB and UART modes. The current adapter version has a regulator and differs from older boards; identify Dylan's exact board before specifying its input supply. The proposed connection is Jetson USB-A to adapter USB-C, then adapter TTL bus to STS3215, with compatible independent servo power. No Uno sketch is needed with that adapter. This remains a connection proposal, not tested Jetson control.

The known cables are JUXINICE 4-inch down-angle USB-A extensions. Reserve connector and cable spaces rather than assuming their molded ends, direction, or usable length. Model a 62 × 16 × 43 mm controller/connector pocket, larger than the current adapter's 42 × 33 mm PCB. Actual board height, cables, and voltage configuration are U. PLA coupons use 0.2 mm layers and three walls without supports; select the final structural material after fit, retention, and thermal tests.
