"""Runs the test-freeze script: its self-test is green, each break turns only its own row red, and a clean range reads green."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "test-freeze" / "scripts" / "test_freeze.py"


def run(*args, cwd=None):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=cwd)


class TestFreeze(unittest.TestCase):
    def test_self_test_is_green(self):
        r = run("--self-test")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("GREEN", r.stdout)

    def test_each_break_turns_only_its_own_row_red(self):
        for name in ("no-refusal", "no-empty-reason", "no-code-check"):
            with self.subTest(break_name=name):
                r = run("--self-test", "--break", name)
                reds = [line for line in r.stdout.splitlines() if line.lstrip().startswith("RED")]
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertEqual(len(reds), 1, r.stdout)

    def test_an_empty_range_is_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "-C", tmp, "init", "-q"], check=True)
            Path(tmp, "a.txt").write_text("x\n", encoding="utf-8")
            subprocess.run(["git", "-C", tmp, "add", "-A"], check=True)
            subprocess.run(["git", "-C", tmp, "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
                            "commit", "-q", "-m", "first"], check=True)
            r = run("check", "--range", "HEAD..HEAD", cwd=tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("GREEN", r.stdout)


if __name__ == "__main__":
    unittest.main()
