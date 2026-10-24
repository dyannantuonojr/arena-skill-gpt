# Validation record: required outputs (v3)

Validated on 2026-10-24 before publication.

- Full standard-library suite:70 tests run successfully on the Windows host;
  two filesystem-symlink checks skipped because creation is not permitted here.
  Linux CI executes those checks. Tests cover the original selection/evolution
  engines, mandatory package acceptance/delivery gates, and safe all-answer export.
- Independent review reproduced original/state overwrite, incorrect evolving-mode
  counters, and unreadable-answer false completion. All three have regression tests
  and fixes. Sidecar writes are constrained to the report directory before writes.
- Viewer tests cover every answer, closed scope/assumption blocks, script escaping,
  safe links, UTF8/UTF16 BOM decoding, live source fingerprints, copied diagram hashes,
  input-preserving export and pending output behavior.
- The current real run has16 unchanged original answers,15 judgments and two actual
  finalist implementation packages. Both Archify native workflows passed validate,
  delivery, strict provenance and browser gates; accepted hashes match actual bytes.
- Browser interaction verified answer selection, a rendered finalist implementation
  guide, a working Archify iframe and collapsed assumptions. The live header uses
  plain text; job/rubric details are collapsed.
- Skill frontmatter validation and diff whitespace checks passed.

New-run budget:31 core jobs +2 mandatory package jobs=33 worker jobs. Rendering and
coordinator overhead are separate. Old saved-run fixtures exercise compatibility;
new runs cannot finish without accepted packages and a current complete viewer.
Unsigned receipts bind files to reported checks; they do not attest renderer identity
or semantic truth. A tournament winner is not certification of general accuracy.

The published workflow diagram is pinned to source commit b3ccf5d160d9f8bfdffbc1820f776737f4077eef; its required-output flow, all four Archify gates and exact artifact/candidate hashes were checked. Final browser interaction also verified bracket selection and both required guides/diagrams, with the user selection restored.
