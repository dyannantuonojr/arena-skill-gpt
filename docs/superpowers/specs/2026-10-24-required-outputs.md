# Required answer viewer and finalist implementation outputs

User requires access to every answer in the bracket window, mandatory Archify
implementation accompaniment for both finalists, and hidden assumptions/review scope.

Ship a standard-library static viewer exporter. Every entry is selectable from the
bracket and an answer list; show original answer, judge notes and finalized implementation
outputs. Keep assumptions/review scope in collapsed details without modifying source
answers. Render untrusted answer text safely. Preserve answer hashes.

Each new run requires one implementation package per finalist after the tournament
(and optional baseline comparison), before delivery can be complete. Each package
contains implementation.md, candidate.json, diagram.html and a real passing Archify
finalize receipt bound by hashes to the candidate/HTML and frozen finalist answer.
Missing/failed/stale packages keep delivery incomplete; do not silently skip Archify.
The coordinator accepts packages with an explicit command, then exports the viewer.

Default budget: 31 core jobs plus two required package jobs =33 worker jobs (34 with
baseline). Legacy evolve:91+2=93. One-entry runs require one package. Older saved runs
without requirement flags remain compatible; current completed run will be upgraded
explicitly for these requested outputs. Archify/Node/browser tooling are required for
complete new-run delivery, while Python bookkeeping/viewer remain standard-library.

Keep the two original finalist answers unchanged. Guides explain proposed implementation
and distinguish already implemented behavior. No automatic applying proposals. The
current result page and all-answer viewer receive both guide packages. Publish tested
changes to the existing GitHub fork, preserving original and Archify licenses.
