# Minimal personal statement recall

Dylan requested the simplest useful personal-memory improvement, with Claude Opus 5.5 checking the plan before implementation. The current robot stores a visitor ID on turn points and indexes that field. Statement search currently uses only time and similarity, then suppresses first-person statements from earlier conversations. This blocks returning-person recall while allowing other visitors' non-first-person statements to compete for results.

## Proposed change

1. Require a nonempty resolved visitor ID in the shared Memory.told query. Apply its payload filter before ranking and limiting results. Missing visitor IDs and legacy unowned points yield no personal results.
2. Pass turn.visitor from Robot._told. Retain ignored-object suppression and selection-error blocking. Replace the first-person/session heuristic with visitor isolation for every statement. Enrolled visitors already have stable IDs; guests retain the existing temporary conversation IDs. Do not identify guests from a spoken name alone.
3. Keep the existing question/action exclusions from statement vectors. Add one small deterministic exclusion for standalone acknowledgements and filler, such as "okay", "thank you", "yes", "no", "um", and "hmm". Keep meaningful short statements such as "I like tea". Do not use a word-count threshold or an LLM classifier. Preserve raw turn records, dialogue history, object links, and source IDs; only eligibility for semantic statement recall changes. Wake-only greetings already set keep=False and remain unchanged.
4. Keep the current model, at most two delivered statements, similarity threshold, ordinary 12-hour retention, knowledge retrieval, visual recall, face-consent rules, deletion, and object ownership.

This first version recalls what a person said within the current retention window. It does not promise complete conversation reconstruction or recall after the retention window. Record those limitations in the handoff.

## Binding change and review corrections

Record D206 before code changes. It supersedes D70's statement-scoping clause: all semantic statement recall belongs to the resolved visitor. General statements such as "The booth closes at five" no longer cross visitor boundaries; shared curated knowledge remains shared. An enrolled face match can now retrieve that person's earlier-conversation statements within the existing 12-hour window. This increases the consequences of a false face match; existing enrollment consent, unique-match, missing/ambiguous-face, and deletion guards remain required.

Intentionally update robot/test_things.py's old shared-general-statement assertion and robot/test_people.py's old returning-Cy exclusion. These expectations change because Dylan requested visitor-specific recall across conversations. Preserve the replacement-visitor privacy assertion in test_people.py, and add independent filter, guest/enrollment, reopen, and deletion checks.

Claude Opus 5.5 returned conditional GO after these corrections. Its review is retained in reviews/20261017-opus55-person-memory-plan.md. No production code changed before the review.

## Alternatives

The current session-only first-person guard is smaller but prevents useful recall when an enrolled visitor returns. Persisting complete exchanges and injecting retrieved dialogue can answer broader conversation questions, but its prior prototype regressed topic transfer. Reuse the existing statement path and measure isolation and return recall first.

## Acceptance

Use real Edge storage in focused tests. An enrolled visitor must retrieve their own earlier matching statement across a conversation reset and storage reopen. A guest recalls statements only within the current temporary conversation. Include a guest who states a preference before consenting to enrollment, then returns and recalls it through the reused visitor ID. Include the existing missed-face continuation path, which must retain the selected visitor ID. Another visitor's nearer or more numerous matches must not consume the result limit. Unknown visitors with separate conversation IDs, missing IDs, and unowned legacy points must remain isolated. Ambiguous visitor selection must return no personal statements. Forgetting must remove the linked personal recall after reopen. Ignored-object suppression and meaningful short statements must remain intact. Standalone filler must have no statement vector, while its raw record can remain for diagnostics. Existing wake-only behavior must remain unchanged.

Run relevant memory, visitor, and deletion regressions before task review. Run full checks before a release deployment. Inspect the active Jetson job and preserve memories and backups. Do not interrupt the live demo for experiments. Use an isolated Jetson store for the changed query path. Keep the active robot on its existing release until a safe deployment boundary.

## Deferred handoff

- Complete exchanges and explicit "what did we discuss" retrieval, with topic relevance and correction checks.
- A deliberate retention choice for returning visitors beyond 12 hours.
- Broader transcript-quality handling based on observed recognition failures.
- Recency weighting only after an evidenced stale-result problem.
- Offline summaries or consolidation only after a measured need, retaining source IDs and deletion links.
- Existing physical heating, multi-person acceptance, restart/deletion, offline startup, and long-run qualification.

## Review request

Check whether this is the smallest safe improvement, especially anonymous identity lifetime, application of the filter before top-k, removal of the old first-person guard, deletion links, and preserving useful short utterances. Read robot/main.py, robot/memory.py, robot/test_people.py, robot/test_attention.py, the relevant statements tests in robot/test_things.py, and research/conversation.md only as needed. Review the plan without editing code, running models, or accessing the live Jetson. Return GO or concrete required corrections. No implementation may start before this review completes.
