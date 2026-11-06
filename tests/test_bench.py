"""bench: its self-test is green on the real server, each break turns only its expected row red, and --break is refused
outside the self-test."""
import os
import re
import shutil
import subprocess
import unittest
from concurrent.futures import ThreadPoolExecutor

import support

SERVE = support.ROOT / "skills" / "bench" / "serve.mjs"
NODE = shutil.which("node")
EXPECTED_RED = {
    "no-host-check": "a request naming another host is refused",
    "no-origin-check": "a message from another site's page is refused",
    "no-key-check": "a message without this launch's key is refused",
    "room-path-escape": "a name outside the room list is refused",
    "second-write": "a sent message lands in INBOX.md, the only file changed",
    "two-recommended-shown": "a question with fewer than two options, or not exactly one recommended, is refused in words",
    "answered-from-click": "an answer already in INBOX.md reads as answered",
    "answer-any-option": "an answer to an unknown question, a refused one, or an option it does not list is refused",
    "picture-path-escape": "a picture name that leaves its question's folder is refused",
    "missing-as-blank": "a question's pictures are served by name, and a missing one is shown as missing and cannot be judged",
    "verdict-dropped": "one Send names every picture, an unmarked one as 'no verdict', and a picture it does not list is refused",
    "refused-as-fail": "a REFUSED run is its own mark, never a pass or a fail",
    "refused-as-pass": "a REFUSED run is its own mark, never a pass or a fail",
    "missing-as-pass": "a check with no line at the newest commit reads 'not run', never passing",
    "pill-missing-as-pass": "the header pill counts a check with no line at the newest commit as 'not run', never passed",
    "reply-blind": "an agent's 'answered HH:MM: line' reads as its reply on the card, and 'read HH:MM' as read with no reply",
    "batch-first-only": "a batch of answers is one message, and every answer in it reads as answered",
    "batch-unchecked": "a batch with an unknown question, a question twice, or nothing in it is refused, and nothing is written",
    "approve-first-option": "Approve sends the option marked recommended, not the first one",
    "keys-off-by-one": "each key calls its own button's handler; Approve with no recommendation, or a number no option has, does nothing",
    "keys-while-typing": "a key typed in a box, or with Ctrl, Alt or Cmd held, does nothing",
    "counts-from-old-list": "each tab's count comes from the list the cards come from, after an answer too, and says N of M while searching",
    "search-id-only": "a search finds a question by its id, its title or its text, whatever the case",
}


def node(*args):
    return subprocess.run([NODE, str(SERVE), *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                          creationflags=support.NOWIN, timeout=180)


@unittest.skipIf(NODE is None, "the bench needs Node 18 or newer, and node is not on PATH")
class TestBench(unittest.TestCase):
    def test_every_break_has_an_expected_row(self):
        text = SERVE.read_text(encoding="utf-8")
        listed = re.search(r"const BREAKS = \[([^\]]*)\]", text).group(1)
        self.assertEqual(set(EXPECTED_RED), set(re.findall(r'"([^"]+)"', listed)))

    def test_self_test_is_green(self):
        r = node("--self-test")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("self-test GREEN", r.stdout)
        self.assertEqual(support.red_rows(r.stdout), [])

    def test_each_break_turns_only_its_expected_row_red(self):
        workers = max(2, min(5, os.cpu_count() or 2))
        with ThreadPoolExecutor(workers) as pool:
            runs = dict(zip(sorted(EXPECTED_RED), pool.map(lambda b: node("--self-test", "--break", b), sorted(EXPECTED_RED))))
        for name, r in runs.items():
            with self.subTest(break_name=name):
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertEqual(support.red_rows(r.stdout), [EXPECTED_RED[name]], r.stdout)

    def test_a_lasting_setup_failure_is_refused_in_words_after_three_tries(self):
        for fault, words in (("git-denied", "Permission denied"), ("git-index-held", "unable to write new index file"),
                             ("get-dropped", "ECONNRESET")):
            with self.subTest(fault=fault):
                r = node("--self-test", "--break", fault)
                self.assertEqual(r.returncode, 78, r.stdout + r.stderr)
                self.assertIn("could not look", r.stdout)
                self.assertIn("after 3 tries", r.stdout)
                self.assertIn(words, r.stdout)
                self.assertNotIn("self-test GREEN", r.stdout)
                self.assertEqual(support.red_rows(r.stdout), [])

    def test_break_is_refused_outside_the_self_test(self):
        r = node("--break", "no-key-check", "--check")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("--break goes with --self-test only", r.stderr)


if __name__ == "__main__":
    unittest.main()
