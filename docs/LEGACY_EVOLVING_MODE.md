# Legacy evolving mode

The original upstream critique-and-revision workflow remains in the tournament
engine for command-line users and saved-run compatibility. It is **not a mode in
the current Arena / Grudge Match UI**.

- **Arena in the UI:** 16 frozen answers, 15 pairwise judgments and 2 finalist
  packages: 33 jobs. Answers advance unchanged.
- **Grudge Match in the UI:** original, independent peer review, synthesis,
  evidence check of all three, independent judge and winner-only Archify: 6 jobs.
- **Legacy `--mode evolve`:** original answers, opponent critiques, revisions and
  judgments across the bracket: 91 core jobs plus 2 finalist packages, or 93 jobs
  with 16 competitors. An optional baseline adds one job; retries add usage.

New CLI tournaments default to `--mode select`. Evolving mode must be requested
explicitly. Historical saved tournaments without a mode retain their original
evolving behavior so that resume does not silently change their rules.

The source and synthetic tests intentionally retain this compatibility path.
Its presence does not enable revisions in a new fixed-answer Arena run.
