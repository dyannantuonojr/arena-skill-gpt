# Validation record: required outputs (v3)

Validated on 2026-10-24 before publication.

- Full standard-library suite:71 tests run successfully on the Windows host;
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

Windows CI exposed 8.3 short directory names being mistaken for redirects. Path
validation now checks actual links/reparse points and canonical containment. A real
Windows short-name regression passes locally; symlink rejection remains covered.


Tree workspace and user rubrics (v3.1): 79 local tests pass (two symlink tests
skipped on this Windows host). Browser checks clicked an original native tree leaf
(a015), a finalist (a004) and its implementation guide, and the final match with
both answer links. The native passport is suppressed in this embedded workspace
so it cannot obscure the canvas; the source Archify HTML is unchanged. Rubric
input rejected blanks and downloaded a UTF-8 next-run rubric. Five engine tests
cover exact criteria propagation, frozen source/effective rubrics, rejection before
writes, and historical compatibility. Independent focused review found no blocker.


All-in-one bundle (v3.2): a fresh copied installation of skills/arena ran its own
bundled Archify CLI and passed validate, deliver, strict check, and real-browser
check on a native tree. No external Archify checkout, node_modules, or renderer
installation was used. The unmodified upstream subtree has 203 files and
17,826,551 bytes, verified against pinned Git-blob hashes and retained licenses.
The complete local suite ran 89 tests successfully (two filesystem-link skips);
a subsequent seven-test required-output suite covers explicit bundled paths in
fresh artifact-worker briefs. CI adds installed-copy browser smoke tests on both
Windows and Linux. The setup checker explicitly leaves native model-host worker
capability unverified until the coordinator checks actual tools.
The Task & rubric editor displays the original task before grading criteria;
its combined start request preserves exact task/criteria text and newlines.
Account sign-in and plan access remain user/host responsibilities, with linked
OpenAI instructions. No model API key or credentials are added by this bundle.
