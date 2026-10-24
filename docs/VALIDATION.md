# Validation record: fixed-answer default (v2)

Validated on 2026-10-24 before publication.

- Full standard-library suite: 43 tests passed. This includes a real-CLI synthetic
  16-answer selection tournament with exactly 31 jobs, four fixed-branch rounds,
  and unchanged original answer paths, plus the explicit legacy evolving pipeline.
- The selection tests reject changed answers during judging and at final delivery.
- Independent review reproduced the final-delivery hash gap; its regression failed
  before the fix and passed afterward. All five selection tests passed independently,
  including an additional singleton CLI smoke check.
- Legacy states without a mode remain evolving runs. The explicit evolving plan
  remains 91 jobs; the default selection plan is 31. Optional baseline adds one.
- Skill creator frontmatter validation and diff whitespace checks passed.
- Cross-platform CI runs Windows/Linux with Python 3.8/3.12.

These tests establish engine contracts and bookkeeping, not general model answer
accuracy. Native worker scheduling and retry limits remain instructions interpreted
by the host, not an autonomous Python model runner or an OS sandbox. A selected
answer may still be wrong. Archify automation verifies diagram artifact properties;
it does not prove the diagram's semantic truth. Diagram receipts accompany its HTML.
