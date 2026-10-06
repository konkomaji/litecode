"""Validate every challenge check: it must FAIL on the start files and PASS on the reference fix."""
import shutil, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from litecode import evals
from litecode.challenges import CHALLENGES, LEVELS, KINDS


def _make(files):
    root = Path(tempfile.mkdtemp(prefix="lc-ev-"))
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return root


class TestChallengeSets(unittest.TestCase):
    def test_shape(self):
        self.assertEqual(len(CHALLENGES), 30)
        self.assertEqual(len({c.name for c in CHALLENGES}), 30)
        for lv in LEVELS:
            self.assertEqual(sum(c.level == lv for c in CHALLENGES), 10, lv)
        self.assertEqual({c.kind for c in CHALLENGES}, set(KINDS))
        for c in CHALLENGES:
            self.assertTrue(c.fix or c.answer, c.name)

    def test_checks_pass_on_fix_and_fail_on_start(self):
        for c in CHALLENGES:
            with self.subTest(c.name):
                root = _make({**c.files, **c.fix})
                try:
                    ok, out = evals._run(root, c.check, c.answer)
                    self.assertTrue(ok, f"reference should pass: {out}")
                finally:
                    shutil.rmtree(root, ignore_errors=True)
                root = _make(c.files)
                try:
                    ok, _ = evals._run(root, c.check, "")
                    self.assertFalse(ok, "start state should fail")
                finally:
                    shutil.rmtree(root, ignore_errors=True)

    def test_select(self):
        self.assertEqual(len(evals.select(level="hard")), 10)
        self.assertTrue(all(c.kind == "security" for c in evals.select(kind="security")))


if __name__ == "__main__":
    unittest.main()
