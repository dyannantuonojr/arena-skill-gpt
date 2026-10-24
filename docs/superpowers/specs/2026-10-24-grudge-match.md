# Grudge Match design

User-approved flow: original answer -> independent peer review -> synthesis -> independent judge comparing original and synthesis under the same rubric -> Archify for the winner only. Five worker jobs, retries reported separately. The reviewer is a critique, not a second independently drafted answer. Either original or synthesis can win.

Same repository and personal plugin, separate workflow and saved-run directory. Existing Arena tools/defaults and original viewer remain intact. Grudge Match shares the visible question-over-optional-rubric form, readable outputs, and tree controls. Its tree shows the four stages and winner. No model runs during development or setup.

Approaches: shrinking Arena to two competitors would omit peer review/synthesis and incorrectly package both finalists. A separate repository would duplicate proven infrastructure. Chosen: a separate workflow in the existing repository, reusing worker ownership, durable reservations, scoring and trusted Archify finalization.

Exact task/rubric inputs and accepted stage outputs remain hash checked. Independent worker invocations have no conversation history. Judge receives anonymized answer copies and the same frozen rubric, not the review. Validated rubric arithmetic determines the winner; ties use the existing rubric rules. Only the winner receives a native Archify diagram plus implementation guide, and completion requires all native gates. Reads never start work.

User refinement: use an Arena / Grudge Match toggle above the question in the same UI. Switching modes changes workflow/tool routing and count without starting work. Direct open tools can remain as shortcuts into the selected mode.
