"""Portable prerequisites and immutable Archify bundle checks (stdlib only)."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("arena_setup", REPO / "skills/arena/arena_setup.py")
SETUP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SETUP)


class SetupTests(unittest.TestCase):
    def test_shipped_bundle_matches_upstream_inventory(self):
        check = SETUP.check_bundle()
        self.assertEqual(check["status"], "pass", check)
        self.assertEqual(check["files"], 203)
        self.assertEqual(check["source_bytes"], 17826551)
        self.assertEqual(check["tree_sha256"], SETUP.PINNED_TREE_SHA256)

    def test_missing_or_modified_source_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "archify"
            shutil.copytree(SETUP.BUNDLE_ROOT, root)
            (root / "LICENSE").unlink()
            (root / "bin/archify.mjs").write_bytes(b"modified")
            check = SETUP.check_bundle(root)
            self.assertEqual(check["status"], "fail")
            self.assertEqual(check["problems"], [
                {"file": "LICENSE", "reason": "missing-or-unreadable"},
                {"file": "bin/archify.mjs", "reason": "content-mismatch"}])

    def test_rewritten_inventory_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = json.loads((SETUP.BUNDLE_ROOT / "SOURCE_MANIFEST.json").read_text())
            del manifest["files"]["LICENSE"]
            manifest["source_files"] -= 1
            (root / "SOURCE_MANIFEST.json").write_text(json.dumps(manifest))
            self.assertEqual(SETUP.check_bundle(root)["status"], "fail")

    @mock.patch.object(SETUP.shutil, "which", return_value=None)
    def test_missing_node_has_clear_failure(self, unused):
        self.assertIn("missing from PATH", SETUP.check_node()["error"])

    @mock.patch.object(SETUP.shutil, "which", return_value="node")
    def test_node_minimum_and_bad_versions(self, unused):
        for version, expected in (("v18.0.0", "pass"), ("v24.1.2", "pass"),
                                  ("v16.20.0", "fail"), ("not-node", "fail")):
            with self.subTest(version=version):
                result = subprocess.CompletedProcess([], 0, version + "\n", "")
                with mock.patch.object(SETUP.subprocess, "run", return_value=result):
                    self.assertEqual(SETUP.check_node()["status"], expected)

    @mock.patch.object(SETUP.shutil, "which", return_value="node")
    def test_node_launch_failure_is_reported(self, unused):
        with mock.patch.object(SETUP.subprocess, "run", side_effect=OSError("cannot execute")):
            self.assertEqual(SETUP.check_node()["status"], "fail")

    def test_no_browser_or_host_claim_without_probe(self):
        with mock.patch.object(SETUP, "check_node", return_value={"status": "pass"}), \
                mock.patch.object(SETUP, "check_bundle", return_value={"status": "pass"}), \
                mock.patch.object(SETUP, "probe_browser") as probe:
            report = SETUP.collect_checks()
        probe.assert_not_called()
        self.assertEqual(report["local_runtime_checks"], "pass")
        self.assertEqual(report["browser"]["status"], "not-checked")
        self.assertEqual(report["native_agent_host"]["status"], "check-required")

    def test_browser_missing_blocks_requested_probe(self):
        result = subprocess.CompletedProcess([], 0, '{"executable":null}', "")
        with mock.patch.object(SETUP.subprocess, "run", return_value=result):
            report = SETUP.probe_browser("node")
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["browser_gate"], "not-run")

    def test_discovered_browser_is_not_browser_gate_pass(self):
        result = subprocess.CompletedProcess([], 0, '{"executable":"/usr/bin/chromium"}', "")
        with mock.patch.object(SETUP.subprocess, "run", return_value=result):
            report = SETUP.probe_browser("node")
        self.assertEqual(report["status"], "executable-found")
        self.assertEqual(report["browser_gate"], "not-run")

    def test_upstream_browser_override_does_not_fall_back(self):
        node = SETUP.check_node()
        if node["status"] != "pass":
            self.skipTest("Node 18+ is needed for upstream resolver integration")
        with tempfile.TemporaryDirectory() as directory:
            missing = str(Path(directory) / "no-browser-here")
            with mock.patch.dict(os.environ, {"ARCHIFY_CHROME": missing}):
                report = SETUP.probe_browser(node["executable"])
        self.assertEqual(report["status"], "fail", report)
        self.assertIsNone(report["executable"])
        self.assertEqual(report["browser_gate"], "not-run")


if __name__ == "__main__":
    unittest.main()
