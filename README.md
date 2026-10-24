# Arena 16 for GPT and Codex

A GPT/Codex port of [Jake Schincariol's Arena](https://github.com/Jakeschincariol/arena-skill), with **16 fixed answers, four rounds, and required implementation outputs for both finalists**. This is an independent MIT-licensed fork, not an official OpenAI product.

Each competitor gets the same task and a distinct strategy card. The 16 submitted answers are frozen, then independent judges compare pairs. Winners advance unchanged through fixed branches. The Python engine validates scores and decides who advances. An optional blind comparison checks the selected answer against a previous answer.

**The count is explicit:** 16 initial answers + 15 judges = **31 core jobs**, then two required finalist implementation packages = **33 worker jobs total**. This does not mean 16 simultaneous agents. Retries and coordinator/tool overhead add usage.

The original critique-and-revision process remains available with explicit `--mode evolve`: 91 core jobs plus two required packages = 93 worker jobs. Existing saved runs without a mode keep their original evolving behavior.

## Requirements and compatibility

Use a ChatGPT/Codex environment with **Python 3.8+, shared writable files, independent subagent tools, Node 18+ and an installed Chrome/Chromium/Edge browser**. Python bookkeeping and the viewer use only the standard library; the credited Archify renderer is bundled inside the skill. No API keys or external model service are required by this skill. Normal model usage limits still apply.

No separate Archify clone, npm install, or Git submodule is needed. Installing
`skills/arena` includes the pinned renderer, its authoring instructions, and its
licenses. The [credited Archify fork](https://github.com/dyannantuonojr/archify)
retains [tt-a1i/archify](https://github.com/tt-a1i/archify) as its upstream.

Check the installed runtime before starting jobs:

```bash
python skills/arena/arena_setup.py --check --probe-browser --json
```

Use the path to your installed skill if it differs. This checks local runtimes and
bundle integrity; the coordinator separately checks native worker tools. A missing
browser or runtime is reported before job spending. See [bundle details and
credits](docs/ARCHIFY_BUNDLE.md).

Independent agent tools are host commands for starting fresh workers and waiting
for their results (for example `spawn_agent` and `wait_agent`). They let each answer
and judge run in a separate context; Arena itself is a coordinator, not a model
server. Separate contexts reduce shared conversation history, but do not guarantee
independent errors or greater accuracy.

A plain ChatGPT chat without these tools cannot run the independent-agent tournament. Uploading the prompt alone does not enable agents. The skill checks capabilities and stops honestly rather than simulating independent workers. Installing a plugin also does not grant missing runtime capabilities.

## Start here: account and installation

You install Arena into a compatible agent environment, not into a subscription.
Sign into Codex with your own ChatGPT account; your account's available features
and usage limits apply. See [OpenAI's sign-in and plan guide](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan).
This repository does not create accounts, buy plans, handle credentials, or enable
missing agent tools. Its instructions and setup checker guide you through the
software requirements. There is no additional Arena model API key.

1. Open a compatible Codex/ChatGPT desktop environment and sign in yourself.
2. Install the Arena skill with the instruction below. The renderer comes with it.
3. Ask the host to run Arena's setup checks and confirm native worker tools.
4. Supply your question and optional grading rubric, then ask to run Arena.

The **Task & rubric** panel prepares a copied start request. Paste that request
into the host chat to authorize a new run; this local report is not a subscription
portal or an autonomous model server.

## Install in Codex

Ask the built-in skill installer:

```text
$skill-installer Install the arena skill from https://github.com/dyannantuonojr/arena-skill-gpt/tree/main/skills/arena
```

Or clone the repository and copy `skills/arena` into your personal `.agents/skills/arena` directory. Do not overwrite an existing Arena installation without checking which version it is.

PowerShell, from the cloned repository:

```powershell
$arenaDestination = Join-Path $HOME '.agents/skills/arena'
if (Test-Path -LiteralPath $arenaDestination) { throw 'Arena already exists; choose a different destination or back it up first.' }
New-Item -ItemType Directory -Force -Path (Split-Path $arenaDestination) | Out-Null
Copy-Item -LiteralPath './skills/arena' -Destination $arenaDestination -Recurse
```

macOS/Linux, from the cloned repository:

```bash
mkdir -p ~/.agents/skills
if [ -e ~/.agents/skills/arena ]; then
  echo 'Arena already exists; choose another destination or back it up first.' >&2
else
  cp -R skills/arena ~/.agents/skills/arena
fi
```

[Official skill documentation](https://learn.chatgpt.com/docs/build-skills) describes skill discovery and invocation. Refresh or restart the host if it does not discover the new skill. This repository also includes `.codex-plugin/plugin.json` for packaging; publication in a plugin directory is a separate process and has not been performed.

## Use

```text
$arena Improve the proposed migration plan while preserving all its constraints.
$arena --agents 4 Find counterexamples to this algorithm.
$arena --seed 7 Plan my launch week; I have six hours each day.
$arena --wave 3 Compare solutions to the task above.
```

In ChatGPT hosts that expose installed skills, select Arena with `@`. In Codex use `$arena` or the skill selector. With no task supplied, Arena uses the last substantive request and previous answer as a baseline. Asking to install or explain Arena does not start a tournament.

| Option | Behavior |
| --- | --- |
| no flags | 16 fixed answers, 31 core + 2 required package jobs = 33 total |
| `--mode select` | Default: judge pairs and advance unchanged answers |
| `--mode evolve` | Original critique/revision process: 91 core + 2 packages = 93 |
| `--agents N` | 1-16 competitors; larger values are rejected |
| `--quick` | Alias for 16, retained from upstream |
| `--seed S` | Reproducible cards and pairings, not reproducible model answers |
| `--wave W` | Parallel job ceiling; default 1, limited further by actual runtime capacity |
| `--rubric-file PATH` | UTF-8 user grading priorities and acceptance criteria, frozen for the new run |

Sixteen competitors are not sixteen simultaneous workers. The coordinator reserves its own slot, waits for workers, and releases them when required by the host. Every job receives a fresh context. It never substitutes itself for an independent judge.

Before worker jobs start, Arena collects your grading priorities and acceptance criteria;
you can choose the default rubric instead. Supply your own criteria verbatim in a UTF-8
file (empty files are rejected):

```bash
python skills/arena/bracket.py init --task-file task.md --rubric-file user-rubric.md
```

The run saves the exact input as `RUN/user-rubric.md` and appends it under **User
grading criteria** in `RUN/rubric.md`. Every initial competitor gets the same criteria
and judges apply them when assigning the five fixed scores: correctness 30%,
completeness 25%, specificity 15%, robustness 20%, and clarity 10%. This preserves
score arithmetic while letting your priorities guide grading. Arena does not invent
a preferred solution on your behalf.

Both rubric files are frozen with SHA-256 digests at initialization. Changes or missing
files stop resume and judging; restore the original bytes or start a new run. Existing
historical runs without rubric digests remain compatible. Omitting `--rubric-file`
uses the default rubric.

The viewer's **Task & rubric** panel shows the original question above the rubric.
Edit the question for a new run, add optional criteria, and copy the combined start
request into the Arena chat. The rubric editor also exports `user-rubric.md` for
your **next run** via `--rubric-file PATH`.
Editing or exporting criteria in the browser does not change or regrade the saved
run, including a completed run; its scores and winners stay recorded as judged.

## Arena tree workspace

The Arena tree is the main view throughout the run. Click an answer node to read
its original text in the adjacent results panel; click a match to inspect the
judgment and open either entry. Closing results returns the full canvas. The tree
stays visible while reading, including on narrow screens. Find answer is a compact
shortcut, not the primary page. Finalists
also have **Implementation** and **Archify** tabs. Assumptions and review scope stay
inside closed details sections, preserving original answer bytes.

Both finalists require a package after judging: `implementation.md`, `candidate.json`,
`diagram.html` and the actual passing Archify summary at
`review/diagram.finalize-summary.json`. The guide gives concrete implementation steps
and acceptance checks; the diagram accompanies that plan. It does not replace the
original answer or earn judging points for appearance.

The engine validates source/package hashes and reported finalize gates, then accepts
with `accept-artifact`. Missing, failed or stale packages block completion. Receipts
bind files and reported rendering checks; they do not prove diagram meaning.

```bash
python skills/arena/bracket.py accept-artifact a004 --dir "/absolute/path/to/run"
python skills/arena/bracket.py accept-artifact a014 --dir "/absolute/path/to/run"
python skills/arena/bracket.py view --dir "/absolute/path/to/run"
```

Use the actual finalist IDs. The coordinator generates the files before accepting
them. The exporter writes `RUN/viewer/index.html` by default and protects original
answers/state from overwrite. If the coordinator has rendered a native Archify
tree at `RUN/visual/arena-tree.html` or `RUN/viewer/arena-tree.html`, it reuses that
reader with a sandboxed selection bridge, preserving the source HTML. While the
native tree is being prepared, a state-derived SVG tree keeps every answer
clickable. Refresh the native tree and export after each wave/round. It works offline; for live refresh serve the folder:

```bash
python -m http.server 8766 --bind 127.0.0.1 --directory "/absolute/path/to/run/viewer"
```

Open the loopback URL in the host's output/browser panel. Refresh exports after
rounds and package acceptance. Unreadable answers, modified artifacts or missing
copied diagrams cannot be reported as complete delivery. Older saved runs retain
their historical requirements; all new runs require these outputs.

## Cost and records

A default run is **31 core jobs + two required packages = 33 worker jobs**, or **34** with a baseline. Four fixed answers take seven core jobs plus two packages; eight take 15 plus two. Explicit evolving mode takes **93**, or **94** with a baseline. Retries add worker jobs; coordination and rendering also consume time and resources. Plan without invoking models:

```bash
python skills/arena/bracket.py plan --json
python skills/arena/bracket.py plan --agents 4 --wave 2
```

The run records the task, rubric, cards, prompts, original answers, answer hashes, and judgments under `.arena/<run>/`. Evolving runs also record attacks and defenses. Selection verifies hashes after judging begins, preserves original answer paths and pairs neighboring branch winners without reseeding. Altered or missing answers stop the run. After interruption:

```bash
python skills/arena/bracket.py status --dir "/absolute/path/to/run"
python skills/arena/bracket.py next --dir "/absolute/path/to/run"
```

Use the same run directory for every command. The coordinator is the only process that changes `arena.json`; state replacement is atomic. Workers write only the paths in their briefs. These are instruction boundaries, **not an operating-system sandbox**. The skill does not modify permissions or apply winning diffs to your project.

Malformed judges are quarantined and retried; incomplete or invalid scores never advance a competitor. Ordinary jobs get two attempts total, judges get three. After those limits, orchestration stops with an incomplete, resumable record rather than inventing outputs. Retry counts live in a coordinator-maintained ledger; the Python engine does not execute workers or enforce scheduling itself.

## Verification and architecture

Run the full standard-library suite:

```bash
python -m unittest discover -s tests -v
```

Tests exercise the real CLI, complete 16-entry selection and explicit evolving runs with synthetic outputs, frozen-answer integrity, fixed branches, deterministic strategy diversity, rejection of invalid scores and match identities, resumability, and odd-sized brackets. Synthetic pipeline tests establish bookkeeping behavior, not model answer quality or universal host compatibility. CI runs on Windows and Linux with Python 3.8 and 3.12.

[Interactive Archify workflow](docs/architecture/arena16/arena16.html) and its source candidate and automated validation receipts are in `docs/architecture/arena16/`. Download the HTML to explore it locally; GitHub's file view does not execute HTML.

The original strategy dealer remains intact. This fork defaults to fixed-answer selection, changes runtime instructions, caps CLI competitors at 16, defaults to one worker per wave, and strengthens judge validation. Read [the mode change](docs/superpowers/specs/2026-10-24-fixed-selection.md) for the exact behavior. The strongest answer in one tournament can still be wrong, and the baseline can win.

## Attribution

Original Arena skill and tournament engine: **Jake Schincariol**, [opusjake.ai](https://opusjake.ai), upstream commit `df07b8e518e10cdecd8cd7712d9958b6f396250e`. GPT/Codex adaptation: [dyannantuonojr/arena-skill-gpt](https://github.com/dyannantuonojr/arena-skill-gpt). Original [MIT license](LICENSE) preserved.

Archify renderer: **tt-a1i (Archify), copyright 2026**, and **Cocoon AI,
copyright 2025**, MIT. The unmodified bundled source is pinned to commit
`25cf37080fc8b1dbe758a4efc3935b55f3327083`; the full license and third-party notices
remain inside `skills/arena/vendor/archify`. See [bundle credits](docs/ARCHIFY_BUNDLE.md)
and [diagram attribution](docs/architecture/ATTRIBUTION.md).
