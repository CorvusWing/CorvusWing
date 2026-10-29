"""bake-off: its self-test is green, each break turns only its expected row red, and the command line checks a real
repository and prints a table whose columns fit their names."""
import json
import tempfile
import unittest
from pathlib import Path

import support

SCRIPT = support.script("bake-off", "bake_off.py")
EXPECTED_RED = {
    "no-parts": "a missing part is refused",
    "no-commit-check": "a part that names no commit is refused",
    "no-order": "a scoreboard committed before the control is refused",
    "no-candidate-order": "rules committed after a candidate are refused",
    "no-sibling-check": "a candidate built on another candidate is refused",
    "no-branch-check": "a branch that does not hold its candidate is refused",
    "no-frozen-rules": "a candidate that changed a rule test is refused",
    "no-files-exist": "a rule file the rules commit does not have is refused",
    "no-control": "a control with no rows is refused",
    "no-too-weak": "a control passing an unmarked test is refused",
    "no-result-words": "a result that is not pass or fail is refused",
    "no-rule-count": "rules with no tests are refused",
    "no-kill-text": "a kill line with no words is refused",
    "no-hit-flag": "a kill line with no hit flag is refused",
    "no-kill-anchor": "a kill line committed with its candidate is refused",
    "no-kill-in-commit": "a kill line whose words are not in its commit is refused",
    "no-kill-line-age": "a kill line written after its first run is refused",
    "no-hit-check": "a pick whose kill line was hit is refused",
    "no-reason": "a pick with no reason is refused",
    "no-placeholder-check": "a pick with a placeholder reason is refused",
    "no-control-column": "a complete bake-off prints the control and each candidate",
    "no-listing": "a change another part made is listed, never failed",
    "no-refusal": "a record that does not check prints no table",
}


class TestBakeOff(unittest.TestCase):
    def test_every_break_has_an_expected_row(self):
        self.assertEqual(set(EXPECTED_RED), set(support.load(SCRIPT, "cw_bake_off").BREAKS))

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
        r = support.run(SCRIPT, "check", "x", "--break", "no-order")
        self.assertEqual(r.returncode, 2, r.stdout)

    def test_command_line_round_trip(self):
        module = support.load(SCRIPT, "cw_bake_off_fixture")
        with tempfile.TemporaryDirectory() as tmp:
            record, _, _ = module.build_fixture(Path(tmp))
            record["candidates"][1]["name"] = "b-with-a-long-name"
            (Path(tmp) / "bake-off").mkdir()
            (Path(tmp) / "bake-off" / "sort-list.json").write_text(json.dumps(record), encoding="utf-8")

            r = support.run(SCRIPT, "check", "sort-list", "--root", tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("GREEN", r.stdout)

            r = support.run(SCRIPT, "scoreboard", "sort-list", "--root", tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            lines = r.stdout.splitlines()
            self.assertEqual(lines[1].split(), ["rule", "test", "control", "a", "b-with-a-long-name"])
            self.assertEqual(lines[2].split(), ["takes_empty", "pass", "pass", "pass"])
            self.assertEqual(lines[3].split(), ["keeps_order", "fail", "pass", "fail"])

            record["candidates"][0]["kill_line"]["hit"] = True
            (Path(tmp) / "bake-off" / "sort-list.json").write_text(json.dumps(record), encoding="utf-8")
            r = support.run(SCRIPT, "scoreboard", "sort-list", "--root", tmp)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("No table is printed", r.stdout)

            r = support.run(SCRIPT, "check", "no-such-record", "--root", tmp)
            self.assertEqual(r.returncode, 78, r.stdout + r.stderr)
            r = support.run(SCRIPT, "check", "../escaped", "--root", tmp)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("not a record name", r.stdout)


if __name__ == "__main__":
    unittest.main()
