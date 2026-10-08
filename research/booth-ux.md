# Booth UX: focus, labels, memory hygiene, turn-taking

As of 2026-10-08. A Fable design pass on Dylan's request, with the repo and both reference robots as context. Adopted with Dylan's changes (D63, end of file). Labels: J measured on an Orin Nano, E measured elsewhere, U unverified.

## Summary

- One focus object at a time on screen: salience = sqrt(area) x (1 minus distance from center) x 1.5 when the box overlaps the largest person box (held up). The focus changes only when it is gone for 1 s, or after 5 s if a challenger scores 1.6 x the incumbent. It freezes from the speech start of a naming turn until the bind.
- Screen: known objects get a solid label ("Dylan's phone"); the focus gets a thick orange box with "Smartphone?" (majority label score at least 0.4) or "???", and a hint "Say: this is my ..."; other unknowns get a thin grey box; people get a box and no name (D59). A status strip shows Listening, Hearing you, Thinking, Speaking, and memory events for 6 s.
- Zero unprompted speech in v1.
- Grounding (J): 15 fps detector, CONFIRM 3 frames, MAX_MISSED 1 s; DINOv2 MaxSim threshold 0.822 at zero false matches, 15 ms per crop, back-to-back crops halve decode (D57); first audio 1.61 s p50 (D58); VAD hangover 0.35 s; one worker thread, one llama slot. Reference robot ideas reused: salience, a stability gate, requery every 2 s, focus margin 1.6, a guess band.

## 1. Focus object

- Candidates: confirmed non-person tracks, not ignored, not recognized, box short side at least 48 px, center moved under 10% of frame width in the last 1 s.
- States: NONE, FOCUS(track, since), FROZEN (from naming-turn speech start until the bind; replaces SETTLE_S polling with a snapshot).
- Teaching: "This is my phone" binds to the focus. If the spoken kind matches a different confirmed track and not the focus, bind to that track. If two tracks match the spoken kind, ask once: "Which one? Hold it up alone."
- No spoken confirmation for a single candidate: a confirmation turn costs about 4 s per teach. The robot says "Got it, your phone", the label appears at once, and "that's not it" undoes it within 20 s.
- Owner is the speaker: the largest person track at speech start, named when a face matches or a name was told this conversation (D60), else "visitor" ("visitor's phone").

## 2. Recognition and labels

- Requery each confirmed track every 2 s, at most three crops per second, never while a turn decodes.
- Bands on the MaxSim score: at least 0.822 known; 0.772 to 0.822 guess, shown as "Dylan's phone?" in orange; below that, unknown.
- Hysteresis: a label is set after two consecutive agreeing queries and cleared after three consecutive queries under 0.772. One box per known name: the highest score; others thin grey.

## 3. Growing the multivector and cleaning it

- Views: the naming turn's three crops (taught, never auto-dropped) and auto views.
- Add an auto view when a track scores at least 0.85 on two consecutive queries, its best similarity to existing views is under 0.95 (new angle or light), and its short side is at least 64 px. At most eight views per object; when full, replace the auto view most similar to the rest.
- Cleanup in code: leave-one-out after each add (an auto view whose best match among the others is under 0.72 is dropped); "that's not my phone" drops auto views matching the current crop at 0.822 or more, stores a negative point (`not: phone`), and unlabels the track; a track matching a negative point above 0.822 never gets that name; a sighting whose track is later unlabeled loses its tag. No view decay in v1; sightings expire with retention (D51).

## 4. Unprompted speech and silent signals

- Zero unprompted utterances in v1. A later rate limit: one per 60 s, 3 s after the visitor's last turn, never over VAD activity.
- The screen carries state (strip above). No LED in v1.

## 5. Turn-taking in noise

- No wake word in v1. Three gates on each VAD line, logged: (1) near field: line RMS at least 10 dB over a rolling 30 s noise floor (calibrated with recorded babble); (2) someone faces the robot: a person box at least 40% of frame height at speech start; (3) at least two transcribed words. Failing lines are logged as background, not answered.
- Half-duplex: the microphone is ignored from the first played sample to 150 ms after the last (no echo canceller; the camera microphone sits by the speaker). Barge-in only if visitors try to interrupt on the test day.
- Push-to-talk fallback: "Hold to talk" on the view page skips gates 1 and 2 (booth staff in loud halls).

## 6. Conversation feel

- Proposed: one to three sentences, 60 tokens by default, 200 when the visitor asks for more ("tell me more"). No spoken filler (TTS shares the GPU path); a 0.3 s cached chime when first audio is predicted over 1.2 s.
- Names only after a face match or a told name this conversation (D60). Things only when asked or when the question concerns something in view. Privacy cues on screen: "Remembering Lena's face (consent 14:02)"; the deletion count after "forget me".

## 7. Failure modes and recovery (rules in code)

- Misheard name: the parsed name shows at once; "rename it to phone" renames (views kept, name and text vector changed).
- Wrong object bound: "that's not it" within 20 s deletes the last naming.
- Wrong person: "I'm not Lena" makes the speaker a stranger for this conversation; Lena is not deleted.
- "Forget that": undo the last memory write within 60 s, count spoken.
- Lost focus while teaching: "Sorry, I lost it. Hold it up and say it again."

## 8. What to measure

| Metric | Target |
| --- | --- |
| Focus switches per minute | under 4 (hard floor 12) |
| Focus dwell p50 | at least 8 s |
| False labels per minute (scored clip) | 0 |
| Label flicker events per minute | under 1 |
| Teach success, "this is my X" to label on screen | 90%, under 2 s |
| Wrong bindings with two objects in view | 0 of 20 |
| Auto views added and dropped per object per hour | logged; drops under 20% of adds |
| Unprompted utterances per minute | 0 |
| Background lines accepted, 10 min of booth babble | under 2 |
| False stops during playback | 0 |
| First audio p50 | 1.2 s, unchanged by focus work |

Live test day (two people): 10 teaches each, five with two objects in view, five with the other person talking 1 m away, one stranger asking "Do you remember me?", one "that's not my phone", one rename, one "forget that"; each recorded as a fixture.

## Ranked v1 build list

1. Focus state machine and view labels, status strip.
2. Requery cadence and label hysteresis with the guess band.
3. Bind naming to the focus, owner from the speaker, immediate label, "that's not it", rename.
4. Speech gates and half-duplex; record booth babble first.
5. Auto views with the diversity rule, leave-one-out drop, negative points.
6. Default answer length, chime on a predicted slow turn, memory events on screen.
7. Hold-to-talk on the view page.
8. Metrics logging for the table.

## Do not build in v1

Wake word, LED, echo cancellation and barge-in, a Kalman tracker, the brain deciding focus or binding, view decay, a memory editor page, patch-level multivectors, greetings on sight, spoken confirmation for a single candidate.

## Foreground, not background (Dylan, 2026-10-08)

- Scenery: a track still for about 60 s (furniture, shelf items, the rack) is marked scenery; it never takes the focus, is never offered for teaching, and is not re-stored as new sightings; it becomes a candidate again when it moves or disappears and returns.
- Focus salience adds interaction cues: appeared or moved in the last few seconds, overlaps a person or a "hand" box (YOLOE vocabulary), large, central.
- A teaching zone: only objects in the central near-field part of the frame take the focus (a mat or table area in front of the robot at a booth).
- Option after the live test, if needed: a USB depth camera (for example OAK-D Lite or Orbbec, about $100 to $200; new spending, Dylan's call) for a "closer than 1 m" gate.
- Measure on the live clip: background objects taking the focus (target 0 per minute), time for a held-up item to take it.

## Dylan's changes (D63, 2026-10-08)

- The focus box is for teaching: only unrecognized objects take the focus; a guess ("Dylan's phone?") never holds it; a visitor can always teach the object they hold even when it is labeled or guessed ("no, this is my wallet" creates a new object and a negative point for the old guess).
- One unprompted line: a greeting when a new person faces the robot, once per visitor, never over speech; by name only after an enrolled face match.
- A wake word: the robot answers only after its name, then keeps a conversation window (about 20 s, renewed by each turn) for follow-ups; lines outside the window are ignored. Method chosen by measurement (a small keyword model such as openWakeWord vs spotting the name in the transcript), design gate first. This replaces the "no wake word" item and the facing gate as the main turn gate.
- Answer length: 64 tokens for v1; revisit after the live test (the robot will not only be at booths and should sound smart).
- No spoken confirmation for a single candidate; "that's not it" undoes (agreed).
