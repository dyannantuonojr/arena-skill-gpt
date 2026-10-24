# Fixed-answer Arena default

User chose 16 immutable answers with independent pairwise judgment. Make selection
mode the published default: 16 drafts plus 15 judges = 31 jobs, four rounds.
Winners advance unchanged through fixed branches; there are no critique or revision
jobs in this mode. Preserve legacy evolving mode only as explicit --mode evolve
(91 jobs). Optional blind baseline adds one job in either mode.

Reuse the existing Python-standard-library engine, strict verdict validation, native
workers, 1-16 CLI bounds, and existing MIT attribution. Freeze and verify answer
hashes once judging begins; never point selection winners to revised files.
Existing saved states without a mode remain evolving runs for compatibility.

Test real CLI all-phase selection and existing evolving behavior, branch progression,
immutable solutions, altered-answer rejection, accurate plans and clean resumes.
Update skill prompts, metadata, README, tests and Archify documentation. Publish
only after independent review and passing Windows/Linux CI.
