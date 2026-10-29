"""decide-first: its self-test is green, each break turns only its expected row red, and the command line keeps the order."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import support

SCRIPT = support.script("decide-first", "decide_first.py")
EXPECTED_RED = {
    "no-cancel-order": "a cancel line written after the probe is refused",
    "no-cancel-stop": "a met cancel line with a build choice is refused",
    "no-output": "a probe with no output is refused",
    "no-reason": "a decision with no reason is refused",
    "no-placeholder-check": "a placeholder reason is refused",
    "no-probe-check": "a record with nothing measured is refused",
    "no-decision-order": "a decision made before the measuring is refused",
    "no-exit-check": "a crashed probe with no written why is refused",
    "no-rerun-check": "a second probe with no reason is refused",
    "no-probe-after-decision": "a probe after the decision is refused",
    "no-decide-once": "a second decision is refused",
    "no-name-check": "a record name that leaves decisions/ is refused",
    "no-seq": "events in one clock tick read in order by their sequence",
}


class TestDecideFirst(unittest.TestCase):
    def test_every_break_has_an_expected_row(self):
        self.assertEqual(set(EXPECTED_RED), set(support.load(SCRIPT, "cw_decide_first").BREAKS))

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
        r = support.run(SCRIPT, "check", "x", "--break", "no-seq")
        self.assertEqual(r.returncode, 2, r.stdout)

    def test_command_line_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            def df(*args):
                return support.run(SCRIPT, *args, cwd=tmp)

            def ok(r, code=0, text=""):
                self.assertEqual(r.returncode, code, r.stdout + r.stderr)
                self.assertIn(text, r.stdout)

            ok(df("open", "cache-scope", "--question", "Per user or shared cache?",
                  "--cancel", "A shared cache loses more than 5% hit rate"), 0, "opened")
            ok(df("probe", "cache-scope", "--", sys.executable, "-c", "print('hit rate 97%')"), 0, "probe 1")
            ok(df("probe", "cache-scope", "--", sys.executable, "-c", "print('hit rate 99%')"), 1, "second run")
            ok(df("decide", "cache-scope", "--cancel-met", "no", "--choice", "build",
                  "--because", "the shared cache keeps 97% hit rate on the sample"), 0, "decided: build")
            ok(df("check", "cache-scope"), 0, "in order")
            ok(df("probe", "cache-scope", "--rerun-because", "the library was upgraded since", "--",
                  sys.executable, "-c", "print(1)"), 1, "already decided")
            data = json.loads((Path(tmp) / "decisions" / "cache-scope.json").read_text(encoding="utf-8"))
            self.assertEqual([p["output"].strip() for p in data["probes"]], ["hit rate 97%"])

            ok(df("open", "crash", "--question", "Is the parser slow?", "--cancel", "The parser takes under 1 ms"), 0)
            ok(df("probe", "crash", "--", sys.executable, "-c", "print('parser: 0.4 ms'); raise SystemExit(3)"), 0,
               "exited 3")
            ok(df("decide", "crash", "--cancel-met", "yes", "--choice", "stop", "--because", "the parser is under 1 ms"),
               1, "crashed measurement")
            ok(df("decide", "crash", "--cancel-met", "yes", "--choice", "stop", "--because", "the parser is under 1 ms",
                  "--probe-failed-ok", "the probe exits 3 by design when the parser is under 1 ms"), 0, "decided: stop")
            ok(df("check", "crash"), 0, "in order")

            ok(df("open", "met", "--question", "q one", "--cancel", "c one"), 0)
            ok(df("probe", "met", "--", sys.executable, "-c", "print(1)"), 0)
            ok(df("decide", "met", "--cancel-met", "yes", "--choice", "other", "--because", "a different question: split it"),
               1, "means stop")

            ok(df("open", "../escaped", "--question", "q", "--cancel", "c"), 1, "not a record name")
            self.assertFalse((Path(tmp) / "escaped.json").exists())
            ok(df("open", "noprog", "--question", "q two", "--cancel", "c two"), 0)
            ok(df("probe", "noprog", "--", "no-such-program-for-decide-first"), 78, "could not be started")
            self.assertEqual(json.loads((Path(tmp) / "decisions" / "noprog.json").read_text(encoding="utf-8"))["probes"], [])

    def test_a_time_written_with_z_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "decisions"
            folder.mkdir()
            record = {"question": "Is the disk the slow part?", "cancel": "Reads take under 1 ms", "cancel_seq": 1,
                      "cancel_at": "2026-01-01T10:00:00Z",
                      "probes": [{"seq": 2, "at": "2026-01-01T10:05:00Z", "command": ["measure"], "exit_code": 0,
                                  "output": "reads take 9 ms", "rerun_because": None}],
                      "cancel_met": False,
                      "decision": {"seq": 3, "at": "2026-01-01T10:09:00Z", "choice": "build",
                                   "because": "reads take 9 ms, far over the line", "probe_failed_ok": None}}
            (folder / "disk.json").write_text(json.dumps(record), encoding="utf-8")
            r = support.run(SCRIPT, "check", "disk", cwd=tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
