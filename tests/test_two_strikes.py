"""two-strikes: its self-test is green, each break turns only its expected row red, the command line counts and stops,
and sixteen writers at once lose no entry."""
import json
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import support

SCRIPT = support.script("two-strikes", "two_strikes.py")
EXPECTED_RED = {
    "no-stop": "a second failure in a row stops and reports",
    "no-ledger-stop": "the ledger shows the stopped check",
    "no-count-by-check": "a failure of another check starts its own count",
    "no-reset": "a reset starts the count again",
    "no-pass": "a pass ends the run of failures",
    "no-normalize": "names that differ only in case and spaces are one check",
    "no-name-check": "an unnamed strike is refused in words",
    "no-run-refusal": "run refuses to run a stopped check",
    "no-bom": "a ledger saved with a byte-order mark reads",
}


class TestTwoStrikes(unittest.TestCase):
    def test_every_break_has_an_expected_row(self):
        self.assertEqual(set(EXPECTED_RED), set(support.load(SCRIPT, "cw_two_strikes").BREAKS))

    def test_self_test_is_green(self):
        r = support.run(SCRIPT, "--self-test")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("self-test GREEN", r.stdout)
        self.assertEqual(support.red_rows(r.stdout), [])

    def test_each_break_turns_only_its_expected_row_red(self):
        for name, r in support.run_breaks(SCRIPT, sorted(EXPECTED_RED)).items():
            with self.subTest(break_name=name):
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertEqual(support.red_rows(r.stdout), [EXPECTED_RED[name]], r.stdout)

    def test_a_break_outside_the_self_test_is_refused(self):
        r = support.run(SCRIPT, "ledger", "--break", "no-stop")
        self.assertEqual(r.returncode, 2, r.stdout)

    def test_command_line_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            led = str(Path(tmp) / "strikes.jsonl")

            def two(*args):
                return support.run(SCRIPT, *args, "--ledger", led)

            r = two("strike", "unit tests: parser", "--note", "KeyError on empty input")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("strike 1 of 2", r.stdout)
            r = two("strike", "Unit Tests:parser")
            self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
            self.assertIn("STOP AND REPORT", r.stdout)
            r = two("ledger")
            self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
            r = support.run(SCRIPT, "run", "unit tests: parser", "--ledger", led, "--", sys.executable, "-c", "print('ran')")
            self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
            self.assertNotIn("ran\n", r.stdout)
            r = two("reset", "unit tests: parser", "--note", "the fixture was missing; added")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            r = support.run(SCRIPT, "run", "unit tests: parser", "--ledger", led, "--", sys.executable, "-c",
                            "print('the check ran')")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("the check ran", r.stdout)
            r = support.run(SCRIPT, "run", "lint", "--ledger", led, "--", sys.executable, "-c", "raise SystemExit(5)")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("exited 5", r.stdout)
            r = two("pass", "lint")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            r = two("ledger")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            r = two("strike", "")
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            r = support.run(SCRIPT, "run", "lint", "--ledger", led, "--", "no-such-program-for-two-strikes")
            self.assertEqual(r.returncode, 78, r.stdout + r.stderr)
            self.assertIn("could not be started", r.stdout)
            kinds = [json.loads(line)["kind"] for line in Path(led).read_text(encoding="utf-8").splitlines()]
            self.assertEqual(kinds, ["strike", "strike", "reset", "pass", "strike", "pass"])

    def test_sixteen_writers_at_once_lose_no_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            led = str(Path(tmp) / "strikes.jsonl")
            support.run(SCRIPT, "ledger", "--ledger", led)  # the self-test runs once here, not sixteen times below
            with ThreadPoolExecutor(16) as pool:
                runs = list(pool.map(lambda i: support.run(SCRIPT, "strike", "check %d" % i, "--ledger", led), range(16)))
            self.assertEqual([r.returncode for r in runs], [0] * 16, [r.stdout + r.stderr for r in runs if r.returncode])
            lines = Path(led).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 16)
            self.assertEqual(sorted(json.loads(line)["check"] for line in lines), sorted("check %d" % i for i in range(16)))


if __name__ == "__main__":
    unittest.main()
