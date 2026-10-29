"""test-freeze: its self-test is green, each break turns only its expected row red, and the command line reads a real range."""
import tempfile
import unittest

import support

SCRIPT = support.script("test-freeze", "test_freeze.py")
EXPECTED_RED = {
    "no-refusal": "c3 a test changed beside code, no reason",
    "no-empty-reason": "c6 an empty reason",
    "no-placeholder-check": "c7 a placeholder reason",
    "code-only": "c5 a test changed alone",
    "deletions-only": "c8 a skip marker added",
    "no-deleted-files": "c9 a test file deleted",
    "quoted-paths": "c10 a test with a non-ASCII name changed",
    "narrow-patterns": "the patterns sort test, code and document paths",
    "no-range-check": "a range that is not BASE..HEAD is refused in words",
    "no-empty-range-check": "an empty range is refused in words",
    "no-net": "net: a test weakened and put back reads clean",
    "no-net-refusal": "net: a range that changes a test with no reason is refused",
}


class TestFreeze(unittest.TestCase):
    def test_every_break_has_an_expected_row(self):
        self.assertEqual(set(EXPECTED_RED), set(support.load(SCRIPT, "cw_test_freeze").BREAKS))

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
        r = support.run(SCRIPT, "check", "--break", "no-refusal")
        self.assertEqual(r.returncode, 2, r.stdout)

    def test_command_line_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            support.git(tmp, "init", "-q")
            support.write(tmp, "lib.py", "def f():\n    return 1\n")
            support.write(tmp, "tests/test_lib.py", "assert f() == 1\n")
            base = support.commit(tmp, "base")
            support.write(tmp, "lib.py", "def f():\n    return 2\n")
            support.write(tmp, "tests/test_lib.py", "assert f() == 2\n")
            bent = support.commit(tmp, "change the code and its test")
            support.write(tmp, "tests/test_lib.py", "assert f() == 2\nassert f() > 0\n")
            support.commit(tmp, "tighten the test\n\nTEST-CHANGE: the old test never checked the sign of the result")

            r = support.run(SCRIPT, "check", "--range", base + "..HEAD", cwd=tmp)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("REFUSED", r.stdout)
            self.assertIn("1 refused, 1 explained; 0 file(s) could not be sorted", r.stdout)

            r = support.run(SCRIPT, "check", "--range", bent + "..HEAD", cwd=tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("EXPLAINED", r.stdout)

            r = support.run(SCRIPT, "check", "--range", base + "..HEAD", "--net", cwd=tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("the range as a whole", r.stdout)

            r = support.run(SCRIPT, "check", "--range", "HEAD..HEAD", cwd=tmp)
            self.assertEqual(r.returncode, 78, r.stdout + r.stderr)
            self.assertIn("holds no commits", r.stdout)

            r = support.run(SCRIPT, "check", "--range", "no-such-branch..HEAD", cwd=tmp)
            self.assertEqual(r.returncode, 78, r.stdout + r.stderr)
            self.assertIn("could not look", r.stdout)


if __name__ == "__main__":
    unittest.main()
