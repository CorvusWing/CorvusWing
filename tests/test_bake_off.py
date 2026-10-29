"""Runs the bake-off script: its self-test is green, and each of its nine breaks turns only its own row red."""
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "bake-off" / "scripts" / "bake_off.py"
BREAKS = ("no-parts", "no-order", "no-control", "no-too-weak", "no-kill-line-age", "no-reason", "no-control-column",
          "no-listing", "no-refusal")


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


class TestBakeOff(unittest.TestCase):
    def test_self_test_is_green(self):
        r = run("--self-test")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("GREEN", r.stdout)

    def test_each_break_turns_only_its_own_row_red(self):
        for name in BREAKS:
            with self.subTest(break_name=name):
                r = run("--self-test", "--break", name)
                reds = [line for line in r.stdout.splitlines() if line.lstrip().startswith("RED")]
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertEqual(len(reds), 1, r.stdout)


if __name__ == "__main__":
    unittest.main()
