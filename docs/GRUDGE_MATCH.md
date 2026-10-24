# Grudge Match

Grudge Match runs alongside Arena in the same repository and personal MCP plugin.
Open Arena and choose the **Grudge Match** toggle above the question field. You
can also say **Open Grudge Match** directly. Switching modes does not start a run.
The question field is visible above **Grading guidance
(optional)**. Leave guidance blank for the standard rubric; click **Start Grudge
Match** to run. Opening or reading does not start a job.

The six sequential worker jobs are original answer, independent peer review,
synthesis, evidence checking of all three outputs, independent judge, and
winner-only Archify authoring. Separate Codex
invocations isolate conversational context. The original gets a normal direct
answer prompt, not an Arena strategy card. Synthesis must evaluate the review's
claims and retain correct original material. It can lose to the original.

The judge gets random x/y copies of the two answers and the same frozen task and
rubric, plus an anonymized answer-claim/source index. The raw evidence report and peer
review are not in its brief. This reduces
position and revision bias; it does not prove objective correctness. The existing
rubric arithmetic validates numeric scores and fatal flags and selects the winner.
Exact ties follow the existing rubric: unresolved issues, correctness, then judge
pick. The UI exposes criterion scores and weighted totals. Scores are not measured
accuracy percentages. Only the winner receives a guide and native Archify diagram,
with the existing validate, deliver, check and browser-check gates. Failed gates
leave the match incomplete. Retries add usage beyond the six jobs.

All five pre-Archify outputs are readable by clicking the workflow nodes or using Find answer.
The winning answer's Implementation and Archify tabs unlock after package
acceptance. Frozen inputs and accepted outputs are hash-checked on progression and
read. Stop cancels only the named workflow. Interrupted runs are readable but do
not automatically resume. Duplicate requests reuse their saved run ID.

Tools: `open_grudge_match`, `start_grudge_match`, `get_grudge_status`,
`get_grudge_answer`, `get_grudge_winner_package`, `stop_grudge_match`.
Output IDs: `a001` (original), `review`, `a002` (synthesis), `evidence`, `judgment`.
Pass the winner ID from the opened view to retrieve its package. A loser package
request is rejected. Saved matches live under the configured plugin data root's
`grudge-match` subdirectory; Arena retains its existing root. Both workflows use
the same signed-in Codex account; plugin tools allow only one active workflow.
No additional model API key is needed.


## Evidence and answer citations

Original, peer-review and synthesis workers are instructed to cite material
factual claims with real Markdown links to primary sources where possible.
Grudge workers explicitly enable native Codex live web search, retaining the
workspace-write sandbox. The evidence checker runs after synthesis and audits
all three outputs: original facts, reviewer criticisms/corrections, and repeated
or newly introduced synthesis claims. It must inspect actual source content,
not treat a search snippet or a plausible URL as verification.

Each original, review and synthesis panel gains a **Claim checks and sources**
section once the checker finishes, without changing its original text or hash.
The accepted report has its own hash. An already-open panel refreshes when the
report is accepted. Click **Evidence check** to read assessments grouped by output: supported,
contradicted, unverified, or not_applicable. Each sourced finding includes a title,
URL, section/locator, check date and brief paraphrase. Inaccessible or insufficient
sources remain unverified. Creative preferences or self-contained reasoning need
no fabricated citation. Citation clicks ask the host to open the source, keeping
the Arena viewer in place; the host may require confirmation or decline.

The checker report is model-authored. The coordinator validates its schema,
coverage of all three outputs and safe citation URLs, then hashes the accepted
report; this does not independently prove that sources were accessed or that an
assessment is true. A real run's Codex worker logs retain tool activity for
operator inspection. The judge evaluates source support under the existing rubric,
not citation count, and can recheck disputed claims using live search. It receives
only the original/synthesis claim records mapped to x/y, not review-origin claims,
summary or explanation fields that could identify which answer came first.

Accepted answers remain frozen. The checker does not silently rewrite them or
launch another revision. Older five-job matches retain their historical counts
and four-node viewer; new matches require the evidence stage and total six jobs
before retries. Arena's 33-job workflow is unchanged.
