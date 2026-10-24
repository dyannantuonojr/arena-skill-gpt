# Bundled Archify runtime

Arena includes [Archify](https://github.com/tt-a1i/archify), created by **tt-a1i**,
with the original **Cocoon AI** copyright retained. The credited upstream project
and [Arena maintainer's GitHub fork](https://github.com/dyannantuonojr/archify)
remain separate repositories. The fork preserves GitHub's upstream relationship.

`skills/arena/vendor/archify/` contains all 203 tracked files from upstream's
`archify/` subtree at commit
`25cf37080fc8b1dbe758a4efc3935b55f3327083` (version 3.2.0), totaling 17,826,551
source bytes. These files are copied without source edits. The bundle contains
the CLI, native renderers, browser validation, generated standalone validators,
templates, examples, schemas, authoring references, generated brand marks and
their licensing metadata. The original `LICENSE`, `THIRD_PARTY_NOTICES.md`, and
embedded Pele license remain in place. Archify's MIT license does not supersede
third-party icon licenses or trademark policies; read the bundled notices before
using brand marks.

`SOURCE_MANIFEST.json` identifies both repositories, the pinned upstream commit,
and SHA-256 hashes and byte counts for every upstream source file. Its inventory
digest is `ca88f10174e60bb4488aa8cfae627b493daa699397490a43851c410f90e084aa`.
The checker pins this digest as well as the commit. The local `.gitattributes`
preserves original file bytes on Windows and Unix. Neither `.git`, `node_modules`,
caches, nor the upstream repository's development-only files are bundled.

Copying or installing the entire `skills/arena` folder carries the runtime with
it. No separate Archify skill installation or npm install is required for native
rendering or browser validation. The upstream development npm scripts may refer
to its full source repository; use the bundled CLI for installed-skill operation.

## Local setup checks

Run from the Arena repository root, replacing `python` with the Python 3 command
on your system (`python3` on many Unix systems):

```sh
python skills/arena/arena_setup.py --check --json
python skills/arena/arena_setup.py --check --json --probe-browser
node skills/arena/vendor/archify/bin/archify.mjs doctor
```

For a standalone installed skill, replace `skills/arena` with its actual path.
Python 3.8+ and Node.js 18+ on PATH are required. The checker uses only the Python
standard library and never downloads or installs anything. It returns nonzero
when a requested local check fails. `--probe-browser` imports Archify's own
`findChrome` export from `bin/visual-check.mjs`, using its platform discovery and
`ARCHIFY_CHROME` rules. A discovered executable proves discovery only. It does
not start a browser or claim artifact validation.

`native_agent_host.status` remains `check-required`: the active model host must
verify native subagent tool access and sufficient concurrent slots. Local shell
checks cannot prove those host capabilities. A passing local report does not
mean the entire tournament is ready or that a diagram passed its browser gates.

## One-time browser dependency

Archify uses a locally installed Chrome, Chromium, or Microsoft Edge over the
DevTools pipe. It has no Puppeteer or Playwright package dependency. If browser
discovery fails, install a supported browser once using your system's installer
or one of these commands, then rerun the checker. These commands are provided for
you to run; the checker does not run them.

Windows PowerShell, with Windows App Installer / winget available:

```powershell
winget install --id Google.Chrome --exact
```

macOS, with Homebrew available:

```sh
brew install --cask google-chrome
```

Debian/Ubuntu systems with the `chromium` package available:

```sh
sudo apt-get update
sudo apt-get install chromium
```

Other Linux distributions use their own browser package or an existing supported
browser. For a portable browser or a browser installed in a custom location, set
its executable explicitly. Examples (replace the path with your actual browser):

```powershell
$env:ARCHIFY_CHROME = 'C:\full\path\to\chrome.exe'
```

```sh
export ARCHIFY_CHROME='/usr/bin/chromium'
```

An existing Edge installation can be selected the same way. An invalid
`ARCHIFY_CHROME` is authoritative: Archify intentionally does not fall back to a
different browser. Fix it or unset it (`Remove-Item Env:ARCHIFY_CHROME` in
PowerShell; `unset ARCHIFY_CHROME` in sh), then retry. Browser launch can still
fail under host security restrictions; require the actual finalize receipt.

## Artifact validation

Read the bundled `SKILL.md` and its type-specific references before authoring.
These are actual supported commands in this pinned version:

```sh
node skills/arena/vendor/archify/bin/archify.mjs finalize tree candidate.json output.html --quality showcase --json
node skills/arena/vendor/archify/bin/archify.mjs browser-check output.html --json --require-provenance --out-dir review-2
```

The `finalize` command runs validation, delivery, strict provenance checking and
real-browser checks for native diagrams. Use the quality level declared in the
candidate. `browser-check` is for focused diagnosis of an already delivered
artifact. There is no separate `browser-validation` or `diagnose` CLI in this
revision. A zero exit and passing receipt for the actual output are required;
neither the setup checker nor `doctor` substitutes for that receipt. Automated
browser validation does not claim perceptual visual review.

## Updating the bundle

Choose a reviewed upstream commit in the credited fork. Copy the complete tracked
`archify/` subtree from that commit's Git blobs without editing its source or
omitting license and brand metadata. Regenerate the manifest's per-file hashes,
byte counts, canonical JSON inventory digest, and source identity; update the
checker's pinned commit and digest and the inventory test expectations together.
Run setup checks, `doctor`, tests, and a fresh-folder finalize with real browser
proof from a copy of the installed skill. Keep the preserved upstream files
separate from Arena's own code and documentation.
