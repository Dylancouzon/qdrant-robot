# Claude Code Adversarial Review

Requested model: `claude-opus-5-5`. The companion reviewed the plan before production edits. The required plan corrections were applied before implementation.

Target: working tree diff
Verdict: needs-attention

The query design is sound, but the plan silently reverses decision D70 and the tests that encode it. Fix the plan text first; no architecture change is needed.

Findings:
- [medium] Plan reverses D70 and its explicit tests without a decision record (research/person-memory-plan.md:7-10)
  DECISIONS.md:61 (D49/D60/D68/D69/D70) states: "Only first-person statements are scoped to the visitor." Two tests encode that rule. test_things.py:283-285 asserts "The booth closes at five." is recalled for a different conversation ("a general statement is shared"). test_people.py:372-374 asserts that an enrolled visitor (Cy) gets told == [] after a new conversation. Step 2 of the plan scopes every statement to the visitor ID, so both assertions must flip. Shared general statements stop working entirely, and enrolled visitors now hear their first-person statements from earlier conversations. This is the requested feature, but the plan never names it as a decision change, never lists the removed capability, and never names the tests that will invert. The repo rules require a DECISIONS.md entry for decision changes and forbid flip-the-test patches without a recorded reason. A face false match also now discloses an enrolled person's personal statements from earlier conversations, where D70 blocked that before. The plan accepts this new exposure without stating it.
  Recommendation: Add a short DECISIONS.md entry to the plan that supersedes the D70 statement-scoping clause. Name the dropped capability: general statements are no longer shared across visitors. Name the new disclosure: an enrolled face match recalls statements from earlier conversations within the 12-hour retention window. List test_things.py:281-285 and test_people.py:372-374 as intended changes with that reason. Keep the replacement-visitor assertion at test_people.py:365-369 unchanged.
- [low] Acceptance does not separate enrolled and guest identity lifetimes (research/person-memory-plan.md:21)
  The acceptance says "The current visitor must retrieve their own earlier matching statement across a conversation reset and storage reopen." Only enrolled visitors can pass this. _converse (main.py:1769) creates a new conversation_visitor on every reset, and a restart creates another one. A guest therefore loses recall at the reset by design. The plan also has no test for the path that makes returning-person recall work for new enrollees. people.enroll (people.py:62) reuses turn.visitor, so guest statements made before consent stay linked to the enrolled person. Statements stored on the D161 missed-face path keep current_visitor and should also stay linked. If a refactor breaks either path, the headline feature fails while the stated acceptance still passes.
  Recommendation: Reword the acceptance in two parts. First, an enrolled visitor recalls their own statement across a conversation reset and a storage reopen. Second, a guest recalls only within the current conversation. Add one case where a guest makes a statement, then enrolls, and later recalls that statement in a new conversation through the same visitor ID.

Next steps:
- Add the D70 supersession entry and the list of intended test changes to research/person-memory-plan.md.
- Split the acceptance into separate enrolled and guest cases, and add the enroll-after-statement case.
- After those edits, GO: a visitor filter in Memory.told, applied before ranking, uses the existing keyword index on visitor (memory.py:346), and forget_visitor already deletes by that field.
