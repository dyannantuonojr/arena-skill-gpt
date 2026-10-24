# Grudge Match

Grudge Match runs alongside Arena in the same repository and personal MCP plugin.
Open Arena and choose the **Grudge Match** toggle above the question field. You
can also say **Open Grudge Match** directly. Switching modes does not start a run.
The question field is visible above **Grading guidance
(optional)**. Leave guidance blank for the standard rubric; click **Start Grudge
Match** to run. Opening or reading does not start a job.

The five sequential worker jobs are original answer, independent peer review,
synthesis, independent judge, and winner-only Archify authoring. Separate Codex
invocations isolate conversational context. The original gets a normal direct
answer prompt, not an Arena strategy card. Synthesis must evaluate the review's
claims and retain correct original material. It can lose to the original.

The judge gets random x/y copies of the two answers and the same frozen task and
rubric, without the peer review or author labels in its brief. This reduces
position and revision bias; it does not prove objective correctness. The existing
rubric arithmetic validates numeric scores and fatal flags and selects the winner.
Exact ties follow the existing rubric: unresolved issues, correctness, then judge
pick. The UI exposes criterion scores and weighted totals. Scores are not measured
accuracy percentages. Only the winner receives a guide and native Archify diagram,
with the existing validate, deliver, check and browser-check gates. Failed gates
leave the match incomplete. Retries add usage beyond the five jobs.

All four outputs are readable by clicking the workflow nodes or using Find answer.
The winning answer's Implementation and Archify tabs unlock after package
acceptance. Frozen inputs and accepted outputs are hash-checked on progression and
read. Stop cancels only the named workflow. Interrupted runs are readable but do
not automatically resume. Duplicate requests reuse their saved run ID.

Tools: `open_grudge_match`, `start_grudge_match`, `get_grudge_status`,
`get_grudge_answer`, `get_grudge_winner_package`, `stop_grudge_match`.
Output IDs: `a001` (original), `review`, `a002` (synthesis), `judgment`.
Pass the winner ID from the opened view to retrieve its package. A loser package
request is rejected. Saved matches live under the configured plugin data root's
`grudge-match` subdirectory; Arena retains its existing root. Both workflows use
the same signed-in Codex account; plugin tools allow only one active workflow.
No additional model API key is needed.
