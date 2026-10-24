# Arena 16 for GPT and Codex

A GPT/Codex port of [Jake Schincariol's Arena](https://github.com/Jakeschincariol/arena-skill), with **16 fixed answers, four rounds, and 31 agent jobs by default**. This is an independent MIT-licensed fork, not an official OpenAI product.

Each competitor gets the same task and a distinct strategy card. The 16 submitted answers are frozen, then independent judges compare pairs. Winners advance unchanged through fixed branches. The Python engine validates scores and decides who advances. An optional blind comparison checks the selected answer against a previous answer.

**The count is explicit:** 16 initial answer jobs + 15 judge jobs = 31 total. It is not 16 total jobs or 16 simultaneous agents.

The original critique-and-revision process remains available with explicit `--mode evolve`: 91 jobs for 16 competitors. Existing saved runs without a mode keep their original evolving behavior.

## Requirements and compatibility

Use a ChatGPT/Codex environment with **Python 3.8+, shared writable files, and tools that create independent subagents**. No Python dependencies, API keys, or external model service are required by this skill. Normal model usage limits and subscription costs still apply.

A plain ChatGPT chat without these tools cannot run the independent-agent tournament. Uploading the prompt alone does not enable agents. The skill checks capabilities and stops honestly rather than simulating independent workers. Installing a plugin also does not grant missing runtime capabilities.

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
| no flags | 16 fixed answers, four rounds, 31 jobs |
| `--mode select` | Default: judge pairs and advance unchanged answers |
| `--mode evolve` | Original critique/revision process: 91 jobs |
| `--agents N` | 1-16 competitors; larger values are rejected |
| `--quick` | Alias for 16, retained from upstream |
| `--seed S` | Reproducible cards and pairings, not reproducible model answers |
| `--wave W` | Parallel job ceiling; default 1, limited further by actual runtime capacity |

Sixteen competitors are not sixteen simultaneous workers. The coordinator reserves its own slot, waits for workers, and releases them when required by the host. Every job receives a fresh context. It never substitutes itself for an independent judge.

## Cost and records

A default run is **16 initial drafts + 15 judgments = 31 jobs**, or **32** with a baseline. Four fixed answers take seven jobs; eight take 15. Explicit evolving mode takes **91**, or **92** with a baseline. Retries and extra artifact-generation jobs add usage. Plan without invoking models:

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

Architecture visualization generated using [Archify](https://github.com/tt-a1i/archify), MIT; see [diagram attribution](docs/architecture/ATTRIBUTION.md).
