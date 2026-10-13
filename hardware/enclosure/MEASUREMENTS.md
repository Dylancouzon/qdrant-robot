# Measurements

Parts sit in loose pockets with clearance, so reference sizes cover most of the design. Measured values are from Dylan (2026-10-12); others are labeled with their source.

## Camera

- Board: 38 × 38 mm.
- Mounting holes: four, each centered 4 mm from its corner point. That puts each center 2.83 mm from both edges, so the holes are 32.3 mm apart in both directions. Use 2.6 mm holes for M2 screws to absorb the error.
- Front: the lens holder is 15 mm in diameter, centered, and 23 mm tall from the board. Other parts are 3 mm tall or less.
- Back: a 6 mm heatsink, and a 4 mm connector on the opposite side, plus room for the cable.
- Cable (U): a USB-A plug overmold of about 16 × 9 mm with 4.5 mm cable. It passes a 17 × 10 mm hole in the head floor and one in the roof, 32 mm from the yaw axis. At ±80° the cable needs 32.2 mm more length than at yaw 0 (E).

## Jetson

- Envelope: 103 × 90.5 × 34.77 mm. The carrier board is 100 × 79 × 1.57 mm, and the I/O connectors run along a 100 mm edge (O, NVIDIA).
- Tray: a flat black plastic tray under the board overhangs it by about 11.5 mm on the edge opposite the I/O (E, derived from 90.5 − 79), and about 1.5 mm on each short end (E, derived from 103 − 100).
- Strip (Dylan, measured 2026-10-13): the plastic strip on the edge opposite the connectors is 6.0 mm thick and 8 mm deep, on the tray's outer face (the -Y face). The flat tray and board beside it are 11 mm thick. The constants `JETSON_STRIP_T`, `JETSON_STRIP_D` and `JETSON_SLAB_T` in `geometry.py` set them, and the slot derives from them: 7 mm wide, gripping 6 of the 8 mm so 2 mm stay clear of the board edge.
- Sources: the [Carrier Board Specification SP-11324-001 v1.3](https://developer.nvidia.com/downloads/assets/embedded/secure/jetson/orin_nano/docs/jetson_orin_nano_devkit_carrier_board_specification_sp.pdf) (Figures 4-1 and 4-2) and the [Super Developer Kit datasheet](https://dam-cdn.nvd.orangelogic.com/AssetLink/2ug686w80406gxf6q8uv7r3l7265m2n8.pdf).
- Heights above the board top: USB-A stacks and the RJ45 stand 16.7 mm (O) along the I/O edge, about 20 mm deep (E). The heatsink and fan top is about 25 mm (E).
- Heatsink: about 58 × 39 mm footprint near the board center (E, about ±4 mm). The reservation is 47 mm along X and 66 mm along Z.
- Split of the 11 mm plus the 24 mm above it: tray and feet about 7.6 mm (E), then the board, then components. The board edge is 8 mm from the tray's outer edge, so the heatsink block sits 1.75 mm farther toward -X than with the earlier 11.5 mm estimate (E).

## Servo adapter board (Dylan, 2026-10-13)

- Board: 42 × 32 × 13 mm (sold as 42 × 33 mm, the Waveshare Bus Servo Adapter (A)). It stands on a short edge in a 13 mm thick pocket, its long edges facing -X and +X (the band holds 17 mm).
- Servo connector (U): top-left corner of Dylan's top view, its long axis along the top long edge, so the servo plug (about 8 × 6 mm, 15 mm long, plus a cable bend) enters through that edge. It faces -X here.
- Barrel power jack (U): near the left end of the opposite long edge, so the 5.5 × 2.1 mm plug (about 10 mm across and 40 mm long with strain relief) enters from +X, the port side.
- USB data port (U): unknown, most likely a short end. The end that points up has 20 mm of plug room. Turn the board end for end if the port is on the other end; the jack and servo plugs then sit near the plate, and their rooms cover the full board height.
- Dylan has angled USB cables for the internal connections.

## Speaker

- Housing: 100 × 45 × 21 mm (length × height × depth). This matches the Waveshare reference.

## STS3215 horn and case (online sources, U until checked on the part)

- Horn: four holes of 2.5 mm, on a square at ±4.95 mm from the shaft (14 mm circle), and an M3 × 6 center screw. Sellers list M3 horn screws. Source: [mimic-arm STS3215 fit block](https://github.com/Barbodmz/mimic-arm/pull/7), measured from the SO-ARM100 STEP model.
- Case: 45.4 × 24.8 × 28.8 mm without the output, per the same model. The servo sits in a pocket; it needs no screws.

## Taken from references

USB audio case 53 × 23.5 × 14.6 mm, the power plug and USB plug sizes in `hardware/DESIGN_REQUIREMENTS.md`, and standard M2 and M3 nuts. The first test piece print checks the nut pockets and the horn holes.
