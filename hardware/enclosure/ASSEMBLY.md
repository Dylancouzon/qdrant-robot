# Assembly

Assemble the robot from nine printed parts, 17 M3 screws, four M2 screws, and 13 M3 nuts. The servo kit also supplies its own horn screw. The fastener list is in [README.md](README.md). Physical fit stays U (unverified) until you print and test the test pieces.

The viewer in [output/robot-viewer.html](output/robot-viewer.html) shows each step as a 3D picture. It fits the parts in the same order as this list, draws the new parts in orange, and moves them along the direction you push them in. `preview.py` writes the two generated blocks in this file (what each part is, and the steps) from one list, so the text here and in the viewer is the same.

Tools: a 2.5 mm hex key, a 2.5 mm ball-end hex key, and a 2.5 mm short-arm L-key. You also need a driver for the M2 screws, tweezers, a soft cloth, and four blocks 60 mm tall.

## Before you start

- Print the test pieces first (`output/bambu/Test pieces/Test pieces.3mf`). Test pieces are small prints that check the fits before the large parts. They are not part of the robot.
- Slide the slot test piece over the plastic strip on the edge of the Jetson. Fit one M3 nut in each channel of the fit test plate. Each nut must snap past the 0.3 mm ridge and stay.
- Thread one M3 screw through each test hole. Thread an M2 screw into each camera post.
- Print `Black.3mf` next. Its neck hub shows whether the bearings fit, and its horn disc shows whether the servo horn fits. Test both before you print `White.3mf`.

## What each part is

<!-- parts:start -->
### Parts you supply

| Part | What it is | What it connects to |
| --- | --- | --- |
| Jetson (Jetson Orin Nano Super developer kit) | The computer. It runs the robot. | Its four USB ports take the camera, the USB sound card, and the servo adapter board (data and power). Its own power cable leaves through the port window. |
| Jetson power supply (comes with the Jetson kit) | Powers the Jetson from the wall. | Its cable plugs into the Jetson power jack and leaves through the port window. |
| USB sound card (Waveshare USB to Audio) | The small box that the speaker plugs into. It holds the microphone. | Plugs into a Jetson USB port with an angled USB cable. The speaker lead plugs into it. |
| Speaker (Waveshare 8 Ω 5 W) | Plays the robot's voice. | Its lead plugs into the USB sound card. |
| Servo (Feetech STS3215, 7.4 V) | Turns the head. The servo kit includes the horn, the arm on its output shaft, and the horn screw. | Its lead plugs into the servo adapter board. The horn screws to the horn disc. |
| Servo adapter board (bus servo adapter from the SO-ARM100 kit, 42 × 32 × 13 mm) | Lets the Jetson drive the servo. | A USB data cable goes to a Jetson USB port. A USB-A to 5.5 × 2.1 mm barrel cable from a second Jetson USB port gives it 5 V, which also powers the servo. The build has no servo regulator. The servo lead plugs into it. |
| Camera (Arducam IMX291 USB board) | The robot's eye. | Screws to the four visor posts. Its USB cable leaves the head through a hole in the rear of the head floor, crosses the neck gap, and enters the body through a hole in the roof. It plugs into a Jetson USB port. |
| Bearings (two, 15 × 24 × 5 mm) | Let the head shaft turn. | Press into the neck hub, one on each side. |
| Servo adapter board USB data cable | A USB cable that carries data between the servo adapter board and the Jetson. | Joins the data port of the servo adapter board to a Jetson USB port. |
| USB-A to 5.5 × 2.1 mm barrel cable | A cable that carries 5 V power to the servo adapter board. | The barrel plug goes into the servo adapter board. The USB-A end goes into a second Jetson USB port. |
| Angled USB cables (three) | USB cables with a right-angle plug. They fit the tight gaps inside the body. | One joins the USB sound card to the Jetson, one joins the servo adapter board data port, and the camera cable ends in the third. |

### Printed parts

| Part | Color | What it is |
| --- | --- | --- |
| Body shell (`body-shell`) | White | The white tapered shell. It holds the servo under its roof and carries the neck hub. |
| Base plate (`base-plate`) | White | The white floor. Its pockets hold the Jetson, the USB sound card, the speaker, and the servo adapter board. |
| Port panel (`port-panel`) | White | The white cover for the port window on the port side. |
| Head shell (`head-shell`) | White | The white box that forms the head. It screws to the head shaft. |
| Visor (`visor`) | Black | The black front plate of the head. It holds the camera on four posts. |
| Speaker grille (`speaker-grille`) | Black | The black plate with holes in the front window. Sound passes through its holes. |
| Neck hub (`neck-hub`) | Black | The black ring on the roof that holds the two bearings. |
| Head shaft (`head-shaft`) | Black | The black post that turns in the bearings. The head screws to its wide top, the flange. |
| Horn disc (`horn-disc`) | Black | The black disc between the servo horn and the head shaft. |
<!-- parts:end -->

## Assemble

<!-- steps:start -->
### Neck

1. **Press the two bearings into the neck hub.** Press one bearing into each side of the hub, by its outer ring. Each bearing stops on the center shoulder.
2. **Fit three nuts into the roof.** Stand the body shell roof up on four 60 mm blocks. Take 3 × M3 nut. Hold each nut in tweezers, lower it through the roof hole to just under the roof, and push it outward into its channel until it clicks. Details: Each channel has a 0.3 mm ridge. The nut must click past it and stay. A nut that is let go falls through the hole. The blocks leave room to reach under the roof.
3. **Screw the neck hub to the roof.** Set the hub, with its bearings, over the roof hole, so its three screw holes sit over the nuts. The holes lie at the port side, the rear, and the front, and the stop post stands between the rear hole and the side with no hole. Drive 3 × M3 × 16 screw down through the hub into the roof nuts. Details: The hub fits one way only. The side with no hole faces away from the port side. Use the 2.5 mm hex key from above.
4. **Fit the servo horn.** Set the servo horn on the servo output shaft so the head will point forward. Fix it with the screw from the servo kit. Calibration at first power-on sets the exact middle. Details: The servo horn has 14.4° spline steps, so the head can sit up to 7.2° off forward until calibration.
5. **Set the horn disc on the servo horn.** Press 1 × M3 nut into the pocket on the underside of the horn disc. Set the horn disc on the servo horn with the nut pocket down. Turn it until its four holes line up with the holes in the servo horn. Details: Press the nut in until it snaps past the two lips. It must stay when you turn the horn disc over.
6. **Screw the horn disc to the servo horn.** Drive 4 × M3 × 6 screw through the horn disc into the servo horn. Use the 2.5 mm hex key.
7. **Slide the servo into the shell.** Lay the shell on its rear face on the cloth. Slide the servo into its pocket through the open bottom, with the horn disc entering the roof hole. The servo rests on the long pocket wall under it. Details: The two long pocket walls stop the servo from turning. The rear face of the shell is flat, so the shell lies steady.
8. **Insert the head shaft and drive the center screw.** Turn the shaft until the two nut channels in its flange face the front. Push the shaft in through both bearings, so the hub post enters the arc slot under the flange. Drive 1 × M3 × 16 screw down the shaft bore into the nut in the horn disc. Details: Use the 2.5 mm hex key. The shaft clears the hub post only within about 60° of the front. A square boss on the horn disc fits the socket in the shaft. Do not overtighten: the shaft keeps 0.5 mm of axial play.

### Head

9. **Slide two nuts into the shaft flange.** Stand the shell upright on the four blocks, and take 2 × M3 nut. Slide each nut to the end of its channel in the flange rim, until it clicks past the ridge.
10. **Screw the head shell to the flange.** Set the head shell on the flange, with the front opening toward you and the visor off. Drive 2 × M3 × 8 screw down through the head floor into the nuts. Use the 2.5 mm ball-end key through the front opening. Details: Tilt the key about 25° so it clears the top rim of the front opening and reaches the screws.
11. **Slide two nuts into the visor tabs.** Take 2 × M3 nut. Slide one nut into each tab slot from the rear of the visor, until it clicks past the ridge.
12. **Screw the camera to the visor posts.** Set the camera board on the four posts, with the lens in the round hole. Drive 4 × M2 × 8 screw through the board into the posts. Use a driver that fits the M2 head. Details: The screws cut their own thread in the 1.7 mm pilot holes.
13. **Plug the USB cable into the camera.** Plug the camera USB cable into the connector on the back of the camera board. The free end carries an angled USB-A plug. Leave the free end loose. Details: An angled plug fits the gaps inside the body.
14. **Thread the camera cable into the body.** Pass the free end down through the hole in the rear of the head floor. Lead it across the neck gap behind the hub, and down through the roof hole into the body. Leave a slack loop inside the body. Details: Both holes pass a USB-A plug, and they line up when the head faces forward. The slack loop absorbs the ±80° head turn.
15. **Fit the visor to the head.** Press the visor into the front opening of the head. Keep the cable slack and out of the pinch points. Drive 2 × M3 × 8 screw up through the head floor lip into the tab nuts. Details: The ring on the visor locates it in the head opening. Use the 2.5 mm short-arm L-key from below.

### Body

16. **Fit the corner nuts.** Take 4 × M3 nut. Reach up into the shell opening, and slide one nut into each corner channel until it clicks. Details: Each nut rests on a 2 mm floor and clicks past its ridge. Keep the nut flats along the channel walls.
17. **Fit the speaker grille.** Reach into the shell from below. Press the grille into the front window from the inside until it snaps. Details: The flange of the grille covers the window edge from behind.
18. **Set the Jetson and the servo adapter board in the base plate.** Slide the plastic strip of the Jetson down into the slot, with the fan facing the rear vents and the ports toward the port side. Stand the servo adapter board on its short end in its pocket, with the USB port at the top. The barrel jack faces the port side, and the servo connector faces the slot side, away from the port panel. Details: The Jetson strip is 6 mm thick, and the slot is 7 mm wide and grips 6 mm of the 8 mm strip. Keep the USB port at the top and turn the board around until the barrel jack faces the port side. Each pocket leaves about 1 mm of clearance on each side.
19. **Set the USB sound card in its pocket and plug it in.** Set the USB sound card in the front pocket. Plug an angled USB cable and the speaker lead into the card. Lead the USB cable up over the pocket walls and along the open band to a Jetson USB port on the port side. Details: Do this before the speaker goes in, because the gap above the card is only 2.8 mm. Plug the Jetson end of the cable too, while the base plate is open. The cable crosses the walls about 54 mm above the bottom of the base plate.
20. **Set the speaker on its rails.** Lower the speaker onto the two rails above the card, and face it toward the front. Keep the speaker lead and the USB cable clear of the rails.
21. **Connect the servo adapter board.** Plug the USB-A to 5.5 × 2.1 mm barrel cable into the board from the port side, and its USB-A end into a Jetson USB port. Plug the board's USB data cable into the port at the top of the board, and into a second Jetson USB port. Lead both cables along the open band to the port side, over the sound card cable. Details: Hold the top edge of the board with one finger while you push each plug in. The barrel cable gives the servo 5 V. The barrel plug needs 40 mm of room on the port side, and the USB plug needs 20 mm above the board.
22. **Plug in the servo lead and the camera cable.** Lay the shell on its rear face on the cloth next to the base plate, with its open bottom toward the base plate. Hold the top edge of the board, and plug the servo lead sideways into the servo connector on the board's slot-side edge. Plug the camera USB cable into the last Jetson USB port. Details: Both cables come out of the open bottom. The camera cable drops straight down from the roof hole on the port side to the last free Jetson USB port. Keep it clear of the other cables. The picture shows the shell upright and moved aside. Leave enough slack to lift the shell over the base plate.
23. **Lower the shell onto the base plate.** Lift the shell over the base plate, and lower it straight down. Keep the servo lead and the camera cable clear of the base plate edge and the pockets.
24. **Screw the shell to the base plate.** Tip the robot onto its back on the cloth. Drive 4 × M3 × 10 screw up through the base plate into the corner nuts. Use the 2.5 mm hex key from the plate side. Details: The heads sit in counterbores, so none stands below the base plate.
25. **Connect the Jetson power cable.** Plug the cable of the Jetson power supply into the Jetson through the open port window. Route it out through the notch in the bottom edge of the window.
26. **Fit the port panel.** Drop 1 × M3 nut into the slot in the base plate ear. Set the port panel in the port window. Drive 1 × M3 × 12 screw through the panel into the nut. Details: Use the 2.5 mm hex key from outside.
27. **Check the head turn by hand.** Keep the power off. Turn the head slowly from one stop to the other. The camera cable must slide freely through both holes, and nothing may rub. Details: The unpowered servo resists a little, so turn the head gently. The stops are at ±80°.
<!-- steps:end -->

## Service

Service is the same steps in reverse. Remove the head first, then the shaft, then the shell.

- Remove the port panel screw. Pull the panel straight out from the wall.
- Unplug the camera cable at the Jetson through the port window. Pull the cable up through the roof hole as you lift the head, so nothing pulls it tight.
- Unscrew the two visor screws from below, and pull the visor.
- Remove the two head screws through the front opening. Lift the head off the flange.
- Remove the center screw. Lift the shaft out of the bearings.
- Tip the robot onto its back, and remove the four base plate screws. Lift the shell, and unplug the servo lead. Set the shell aside.
- The servo stays in its pocket above the Jetson. It cannot drop past the Jetson, but support it when you lift the shaft.

## Open items

- Camera cable length, bend radius, and strain relief stay U.
- The USB-A plug size (16 × 9 mm) at the two camera cable holes stays U until you test a real cable.
- The reach of the servo lead and the camera cable with the shell lying beside the base plate stays U. Check it on the first build.
- The fit of the servo kit's horn screw under the horn disc stays U until you test the horn disc.
- USB port current for the servo at 5 V stays U until the first powered test.
- Pending: head calibration happens at first power-on, in software that does not exist yet. With torque off, you turn the head forward by hand and save that position as the servo's middle (the LeRobot approach). It makes up for the 14.4° spline steps of the servo horn.
- Cooling, acoustics, and powered motion stay U until printed tests.
