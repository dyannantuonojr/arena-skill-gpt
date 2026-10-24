# Arena 16 for GPT/Codex

Adapt Jake Schincariol's MIT Arena skill as a real GitHub fork for GPT users.
The chosen approach preserves the standard-library Python tournament engine,
strategy dealer, attack/defend/judge phases, independent judging, and saved state.
Default to 16 competitors; allow smaller experiments (1-16), four rounds and
91 nominal jobs for a full run, plus one optional blind baseline comparison.

Alternatives considered: a single-chat roleplay cannot supply independent agents;
an API service adds keys and billing outside this request. This fork targets
ChatGPT/Codex environments exposing Python, shared files, and independent workers.
Regular ChatGPT without these capabilities receives an honest capability message.

Use native worker tools instead of Claude-specific commands. Default wave size
is one for portability; the coordinator may set a larger wave only within the
runtime's available worker capacity. Fresh job contexts and releasing finished
workers are essential. Never substitute the coordinator for a failed judge.

Harden scored verdicts, numeric input validation, resumability, and isolation.
Keep the original license and credit. Publish source, tests, install instructions,
and an Archify workflow diagram. Do not run a full model tournament merely to
validate bookkeeping; distinguish simulated pipelines from live model evaluation.
