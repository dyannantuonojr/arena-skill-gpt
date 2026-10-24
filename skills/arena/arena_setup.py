#!/usr/bin/env python3
"""Check an installed Arena skill without installing or downloading anything.

Requires Python 3.8+. Browser discovery is opt-in; only Archify finalize can
prove a particular generated artifact passed the real browser gates.
"""
import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys

SKILL_ROOT = pathlib.Path(__file__).resolve().parent
BUNDLE_ROOT = SKILL_ROOT / "vendor" / "archify"
PINNED_COMMIT = "25cf37080fc8b1dbe758a4efc3935b55f3327083"
PINNED_TREE_SHA256 = "ca88f10174e60bb4488aa8cfae627b493daa699397490a43851c410f90e084aa"


def check_bundle(root=BUNDLE_ROOT):
    """Verify source inventory and bytes using the pinned source manifest."""
    try:
        manifest = json.loads((root / "SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
        files = manifest["files"]
        if manifest["schema_version"] != 1 or manifest["upstream_commit"] != PINNED_COMMIT:
            raise ValueError("unsupported manifest schema or upstream commit")
        if not isinstance(files, dict) or not files or len(files) != manifest["source_files"]:
            raise ValueError("invalid source inventory")
        canonical = json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if (hashlib.sha256(canonical).hexdigest() != manifest["tree_sha256"]
                or manifest["tree_sha256"] != PINNED_TREE_SHA256):
            raise ValueError("source inventory digest mismatch")
        problems = []
        total = 0
        for name, expected in sorted(files.items()):
            relative = pathlib.PurePosixPath(name)
            if relative.is_absolute() or ".." in relative.parts or "\\" in name or ":" in name:
                raise ValueError("invalid source path")
            path = root.joinpath(*relative.parts)
            # Source files must stay inside the immutable bundle, including via links.
            try:
                path.resolve().relative_to(root.resolve())
                data = path.read_bytes()
            except (OSError, ValueError):
                problems.append({"file": name, "reason": "missing-or-unreadable"})
                continue
            total += len(data)
            if len(data) != expected["bytes"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
                problems.append({"file": name, "reason": "content-mismatch"})
        if not problems and total != manifest["source_bytes"]:
            raise ValueError("source byte count mismatch")
        return {"status": "fail" if problems else "pass", "files": len(files),
                "source_bytes": manifest["source_bytes"], "upstream_commit": PINNED_COMMIT,
                "tree_sha256": manifest["tree_sha256"], "problems": problems}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {"status": "fail", "error": "Invalid or missing Archify bundle manifest: " + str(error)}


def check_node():
    executable = shutil.which("node")
    if not executable:
        return {"status": "fail", "error": "Node.js 18+ is missing from PATH."}
    try:
        result = subprocess.run([executable, "--version"], capture_output=True,
                                text=True, timeout=15, check=False)
        version = result.stdout.strip()
        match = re.fullmatch(r"v?(\d+)\.\d+\.\d+(?:[-+][\w.-]+)?", version)
        if result.returncode != 0 or not match:
            return {"status": "fail", "executable": executable,
                    "error": "Node version command failed or returned an unrecognized version."}
        return {"status": "pass" if int(match.group(1)) >= 18 else "fail",
                "executable": executable, "version": version, "minimum_major": 18}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"status": "fail", "executable": executable, "error": str(error)}


def probe_browser(node, root=BUNDLE_ROOT):
    """Use Archify's own discovery implementation; do not launch a browser."""
    module = (root / "bin" / "visual-check.mjs").resolve().as_uri()
    script = ("const {findChrome}=await import(" + json.dumps(module) + ");"
              "console.log(JSON.stringify({executable:findChrome()}));")
    try:
        result = subprocess.run([node, "--input-type=module", "--eval", script],
                                capture_output=True, text=True, timeout=30, check=False)
        if result.returncode:
            return {"status": "fail", "error": "Archify browser discovery failed.",
                    "detail": result.stderr.strip()}
        executable = json.loads(result.stdout)["executable"]
        return {"status": "executable-found" if executable else "fail",
                "executable": executable, "browser_gate": "not-run",
                "note": "Discovery only. Run Archify finalize on the actual candidate for real browser proof."}
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        return {"status": "fail", "error": str(error)}


def browser_setup():
    """Human-run, one-time commands; this checker never executes them."""
    if sys.platform == "win32":
        return {"shell": "PowerShell", "requires": "Windows App Installer / winget",
                "install_once": ["winget install --id Google.Chrome --exact"],
                "use_existing_browser": "$env:ARCHIFY_CHROME = 'C:\\full\\path\\to\\chrome.exe'"}
    if sys.platform == "darwin":
        return {"shell": "sh", "requires": "Homebrew",
                "install_once": ["brew install --cask google-chrome"],
                "use_existing_browser": "export ARCHIFY_CHROME='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'"}
    return {"shell": "sh", "requires": "Debian/Ubuntu apt (other Linux distributions: use their package manager)",
            "install_once": ["sudo apt-get update", "sudo apt-get install chromium"],
            "use_existing_browser": "export ARCHIFY_CHROME='/usr/bin/chromium'"}


def collect_checks(probe=False, root=BUNDLE_ROOT):
    python = {"status": "pass" if sys.version_info >= (3, 8) else "fail",
              "version": ".".join(str(part) for part in sys.version_info[:3]), "minimum": "3.8"}
    node = check_node()
    bundle = check_bundle(root)
    browser = {"status": "not-checked", "browser_gate": "not-run",
               "note": "Use --probe-browser for executable discovery; finalize verifies the artifact."}
    if probe:
        browser = (probe_browser(node["executable"], root)
                   if node["status"] == "pass" and bundle["status"] == "pass"
                   else {"status": "blocked", "browser_gate": "not-run",
                         "note": "Fix Node and bundle checks before browser discovery."})
    local_pass = all(item["status"] == "pass" for item in (python, node, bundle))
    ok = local_pass and (not probe or browser["status"] == "executable-found")
    report = {"schema_version": 1, "local_runtime_checks": "pass" if ok else "fail",
            "python": python, "node": node, "bundle": bundle, "browser": browser,
            "native_agent_host": {"status": "check-required",
                                  "note": "The model host must verify native subagent tools and enough concurrent slots. A shell cannot inspect that capability."},
            "next_steps": ["Have the model host verify native subagent support and concurrency.",
                           "Read vendor/archify/SKILL.md before authoring candidates.",
                           "Run the bundled Archify finalize command on each actual candidate; require every gate to pass."]}
    if browser["status"] == "fail":
        report["browser_setup"] = browser_setup()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check local prerequisites (the default)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--probe-browser", action="store_true", help="discover Chrome/Chromium/Edge using Archify; does not launch it")
    args = parser.parse_args(argv)
    report = collect_checks(probe=args.probe_browser)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("Arena local runtime checks: " + report["local_runtime_checks"])
        for name in ("python", "node", "bundle", "browser", "native_agent_host"):
            item = report[name]
            print("  {}: {}{}".format(name, item["status"], " - " + item["error"] if "error" in item else ""))
        print("Host native-agent support still needs a model-host check; browser discovery is not an artifact gate.")
        if report["browser"]["status"] == "fail":
            setup = report["browser_setup"]
            print("One-time browser setup ({}; requires {}):".format(setup["shell"], setup["requires"]))
            for command in setup["install_once"]:
                print("  " + command)
            print("Or select an existing executable: " + setup["use_existing_browser"])
            print("An invalid ARCHIFY_CHROME value is authoritative; fix or unset it before retrying.")
    return 0 if report["local_runtime_checks"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
