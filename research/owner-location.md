# Owner and location of objects

Dylan's requirement (2026-10-10): each sighting carries a UI-set location, and each named object carries its owner. Not built yet; it needs its own design gate. The earlier parser plan and session drafts are in [archive/answer-evidence.md](archive/answer-evidence.md).

| Payload | Stored value | Capture rule |
| --- | --- | --- |
| `location` | A nullable place label, such as "demo table" | Copy the UI's active robot location into each sighting at capture time |
| `owner` | A nullable named-person key, such as "Ana" | Bind a verified object introduction to the named speaker in that session |

- **Owner.** A name given in the current conversation, or a verified enrolled face, establishes the speaker. Unknown or conflicting identity leaves the owner empty. The field adds no consent shortcut.
- **Location.** It names where the robot saw the object, never where the object is now. A later location change affects only new sightings.
- **References.** "My phone" means the current speaker's object; "Ana's phone" means Ana's. The answer says "your phone" to the owner and "Ana's phone" to anyone else. When neither identity nor session evidence resolves the reference, the robot asks whose phone is meant.
- **Storage.** Owner and label together select an object, so Ana's and Dylan's phones stay apart. The object store keys records by name alone today, so this needs a reviewed storage change. Existing records stay unowned.
- **Deletion.** "Forget me" removes the person's owner links and linked evidence; "forget my phone" affects only that owner's object. D148 (same-name objects) stays open.
