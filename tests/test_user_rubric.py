"""User criteria are shared faithfully and cannot change inside a saved run."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1] / "skills" / "arena"
sys.path.insert(0, str(SKILL))
import bracket as B


class UserRubricTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.run = self.root / "run"

    def init(self, criteria=None):
        args = ["init", "--agents", "2", "--seed", "7", "--task", "Solve the task", "--dir", str(self.run)]
        if criteria is not None:
            source = self.root / "criteria.md"
            source.write_bytes(criteria.encode("utf-8"))
            args += ["--rubric-file", str(source)]
        self.assertEqual(B.main(args), 0)
        return B.load_state(argparse.Namespace(dir=str(self.run)))

    def test_exact_input_shared_with_every_competitor_and_judge(self):
        criteria = "  Prefer auditable evidence — café.\r\nKeep {{literal}} and {braces}.\n\n"
        state = self.init(criteria)
        self.assertEqual((self.run / "user-rubric.md").read_bytes(), criteria.encode("utf-8"))
        self.assertTrue(state["has_user_rubric"])
        self.assertEqual(state["user_rubric_sha256"], hashlib.sha256(criteria.encode("utf-8")).hexdigest())
        effective = (self.run / "rubric.md").read_bytes().decode("utf-8")
        self.assertIn("## User grading criteria", effective)
        self.assertTrue(effective.endswith(criteria))
        self.assertIn(SKILL.joinpath("rubric.md").read_text(encoding="utf-8"), effective)
        # Later source-file edits must not leak into the initialized run.
        (self.root / "criteria.md").write_text("Different priorities", encoding="utf-8")
        for job in B.write_prompts(state, "spawn"):
            brief = Path(job["prompt"]).read_bytes().decode("utf-8")
            self.assertIn(criteria, brief)
            Path(job["outputs"][0]).write_text("An answer", encoding="utf-8")
        for job in B.write_prompts(state, "judge"):
            brief = Path(job["prompt"]).read_text(encoding="utf-8")
            self.assertIn(str(self.run / "rubric.md"), brief)
        self.assertEqual(B.weighted_total({key: 10 for key, _ in B.WEIGHTS}), 100)

    def test_empty_rejected_before_run_writes(self):
        source = self.root / "empty.md"
        source.write_text(" \n\t", encoding="utf-8")
        self.assertEqual(B.main(["init", "--task", "Task", "--rubric-file", str(source), "--dir", str(self.run)]), 2)
        self.assertFalse(self.run.exists())

    def test_missing_and_invalid_utf8_rejected_before_run_writes(self):
        source = self.root / "invalid.md"
        args = ["init", "--task", "Task", "--rubric-file", str(source), "--dir", str(self.run)]
        self.assertEqual(B.main(args), 2)
        self.assertFalse(self.run.exists())
        source.write_bytes(b"\xff")
        self.assertEqual(B.main(args), 2)
        self.assertFalse(self.run.exists())

    def test_criteria_and_effective_rubric_frozen_on_resume_and_direct_operations(self):
        state = self.init("Require verifiable sources.\n")
        for filename in ("user-rubric.md", "rubric.md"):
            path = self.run / filename
            original = path.read_bytes()
            path.write_bytes(original + b"changed")
            with self.assertRaisesRegex(B.ArenaError, "rubric"):
                B.load_state(argparse.Namespace(dir=str(self.run)))
            for operation in (lambda: B.write_prompts(state, "spawn"), lambda: B.collect(state)):
                with self.assertRaisesRegex(B.ArenaError, "rubric"):
                    operation()
            path.unlink()
            with self.assertRaisesRegex(B.ArenaError, "rubric"):
                B.load_state(argparse.Namespace(dir=str(self.run)))
            path.write_bytes(original)

    def test_default_and_historical_state_compatible(self):
        state = self.init()
        self.assertFalse(state["has_user_rubric"])
        self.assertIsNone(state["user_rubric_sha256"])
        self.assertFalse((self.run / "user-rubric.md").exists())
        self.assertEqual((self.run / "rubric.md").read_text(encoding="utf-8"), SKILL.joinpath("rubric.md").read_text(encoding="utf-8"))
        rubric = self.run / "rubric.md"
        original = rubric.read_bytes()
        rubric.write_bytes(original + b"changed")
        with self.assertRaisesRegex(B.ArenaError, "rubric"):
            B.load_state(argparse.Namespace(dir=str(self.run)))
        rubric.write_bytes(original)
        for key in ("has_user_rubric", "user_rubric_sha256", "rubric_sha256"):
            state.pop(key)
        (self.run / "arena.json").write_text(json.dumps(state), encoding="utf-8")
        self.assertEqual(B.load_state(argparse.Namespace(dir=str(self.run))), state)
        self.assertEqual(len(B.write_prompts(state, "spawn")), 2)


if __name__ == "__main__":
    unittest.main()
