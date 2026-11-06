"""shell-guards: each guard's self-test is green, each break turns only its expected row red, and the whole path works:
the settings example's own command, run by bash as Claude Code runs it, blocks a bad command with exit 2 and lets a
good one through."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import support

FOLDER = support.ROOT / "skills" / "shell-guards"
HEREDOC = support.script("shell-guards", "heredoc_guard.py")
STATUS = support.script("shell-guards", "exit_status_guard.py")
EXPECTED_RED = {
    HEREDOC: {
        "no-backslash-check": "a backslash in a heredoc body is refused; one outside a heredoc is not",
        "no-bare-python-check": "a Python with no script and no input is refused",
        "no-feed-check": "a Python fed by a heredoc, a pipe or a file passes",
        "no-body-cut": "a command that only mentions python - passes",
    },
    STATUS: {
        "no-substitution-check": "$? read after a substitution in the same command is refused",
        "no-separator-reset": "$? read before, captured first, or in a later command passes",
        "no-quoted-heredoc-skip": "a quoted heredoc's body is text, never a command, and passes",
    },
}
BAD = {HEREDOC: "cat > fix.py <<'EOF'\nprint('a\\nb')\nEOF", STATUS: 'false; echo "$(date) exit $?"'}
GOOD = {HEREDOC: "python3 fix.py", STATUS: 'false; rc=$?; echo "$(date) exit $rc"'}


def hook_input(command, tool="Bash"):
    return json.dumps({"tool_name": tool, "tool_input": {"command": command}, "hook_event_name": "PreToolUse"})


def find_bash():
    """bash, as Claude Code finds it: on PATH, or Git for Windows' own copy; None when there is none."""
    found = shutil.which("bash")
    if os.name == "nt":
        git = shutil.which("git")
        candidates = [Path(git).resolve().parent.parent / "bin" / "bash.exe"] if git else []
        candidates.append(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe")
        found = next((str(c) for c in candidates if c.exists()), None)  # not WSL's bash, which PATH may hold first
    return found


class TestShellGuards(unittest.TestCase):
    def test_every_break_has_an_expected_row(self):
        for path, expected in EXPECTED_RED.items():
            with self.subTest(script=path.name):
                self.assertEqual(set(expected), set(support.load(path, "cw_" + path.stem).BREAKS))

    def test_self_tests_are_green(self):
        for path in EXPECTED_RED:
            with self.subTest(script=path.name):
                r = support.run(path, "--self-test")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("self-test GREEN", r.stdout)
                self.assertEqual(support.red_rows(r.stdout), [])

    def test_each_break_turns_only_its_expected_row_red(self):
        for path, expected in EXPECTED_RED.items():
            for name, r in support.run_breaks(path, sorted(expected)).items():
                with self.subTest(script=path.name, break_name=name):
                    self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                    self.assertEqual(support.red_rows(r.stdout), [expected[name]], r.stdout)

    def test_a_break_outside_the_self_test_is_refused(self):
        for path, expected in EXPECTED_RED.items():
            with self.subTest(script=path.name):
                r = support.run(path, "--break", sorted(expected)[0], stdin=hook_input("ls"))
                self.assertEqual(r.returncode, 2, r.stdout)

    def test_the_hook_blocks_the_bad_command_and_passes_the_rest(self):
        for path in EXPECTED_RED:
            with self.subTest(script=path.name):
                r = support.run(path, stdin=hook_input(BAD[path]))
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("Refused by the", r.stderr)
                for why, text in (("a good command", hook_input(GOOD[path])),
                                  ("another tool", hook_input(BAD[path], tool="Write")),
                                  ("input it cannot read", "this is not JSON"),
                                  ("no input at all", ""),
                                  ("a command with non-ASCII text", hook_input("echo 'caf\u00e9 \u2713'"))):
                    r = support.run(path, stdin=text)
                    self.assertEqual(r.returncode, 0, "%s: %s" % (why, r.stdout + r.stderr))

    def test_scan_reads_scripts_on_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            support.write(tmp, "bad.sh", '#!/bin/sh\n./build.sh\necho "$(date) exit $?" >> log\n')
            support.write(tmp, "good.sh", '#!/bin/sh\n./build.sh\nrc=$?\necho "$(date) exit $rc" >> log\n')
            r = support.run(STATUS, "--scan", str(Path(tmp) / "bad.sh"))
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("bad.sh:3:", r.stdout)
            self.assertEqual(support.run(STATUS, "--scan", str(Path(tmp) / "good.sh")).returncode, 0)
            r = support.run(STATUS, "--scan", str(Path(tmp) / "missing.sh"))
            self.assertEqual(r.returncode, 78, r.stdout)
            self.assertIn("could not look", r.stdout)


@unittest.skipUnless(find_bash(), "bash is not installed here, so the whole path cannot run")
class TestWholePath(unittest.TestCase):
    """The settings example's command, unchanged, run by bash with HOME pointing at a scratch install."""

    def run_hook(self, command, home, payload):
        env = dict(os.environ, HOME=str(home))
        return subprocess.run([find_bash(), "-c", command], input=payload, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=env, creationflags=support.NOWIN)

    def test_the_trap_is_real_in_this_bash(self):
        r = subprocess.run([find_bash(), "-c", 'false; echo "$(echo now) exit $?"'], capture_output=True, text=True,
                           creationflags=support.NOWIN)
        self.assertEqual(r.stdout.strip(), "now exit 0", "the exit-status guard's premise does not hold here")

    def test_the_example_settings_block_and_pass(self):
        example = "hooks.example.windows.json" if os.name == "nt" else "hooks.example.json"
        groups = json.loads((FOLDER / example).read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
        with tempfile.TemporaryDirectory() as home:
            shutil.copytree(str(FOLDER), str(Path(home) / ".claude" / "skills" / "shell-guards"))
            seen = set()
            for group in groups:
                hook = group["hooks"][0]
                self.assertEqual(hook["shell"], "bash")
                path = HEREDOC if "heredoc_guard" in hook["command"] else STATUS
                seen.add(path)
                with self.subTest(command=hook["command"]):
                    r = self.run_hook(hook["command"], home, hook_input(BAD[path]))
                    self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                    self.assertIn("Refused by the", r.stderr)
                    r = self.run_hook(hook["command"], home, hook_input(GOOD[path]))
                    self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(seen, {HEREDOC, STATUS}, "the example must switch on both guards")


if __name__ == "__main__":
    unittest.main()
