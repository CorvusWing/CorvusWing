#!/usr/bin/env python3
"""test_freeze.py -- refuses a commit that changes an existing test beside code, unless its message says why.

WHY. The cheapest way to make a failing test pass is to change the test. Sometimes that is right: the test
was wrong, or the requirement moved. But a test changed without a stated reason is how a suite gets weaker
without anyone noticing. This check reads a range of commits and finds each commit that BOTH removes lines
from an existing test file AND changes code. Such a commit must say why, on a line of its own in its message:

    TEST-CHANGE: the old expected value encoded the bug this commit fixes

Commits that only add tests, only change tests, or only change code are not judged.

USAGE
    python3 test_freeze.py check [--range BASE..HEAD]   exit 0 when every judged commit is explained,
                                                        1 when one is refused, 78 when git cannot read the range
    python3 test_freeze.py --self-test [--break NAME]   a scratch repository with one row per case; each break
                                                        switches one refusal off, and only its own row may turn RED

WHAT COUNTS AS A TEST: a path under tests/, test/ or fixtures/; a file named test_*.py; a file named
*_test.<ext> or *.test.<ext>. WHAT COUNTS AS CODE: a file with one of the extensions in CODE_EXTENSIONS.
Edit those two definitions to fit your project; nothing else needs to change.

LIMITS, stated plainly. A test written inside a source file (Rust's #[cfg(test)], for example) is not seen
as a test. A renamed test file reads as removed and added. The check reads the message; it cannot tell
whether the reason written there is true. That part stays with the person who reviews the commit.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REFUSED_CODE = 78  # the checker could not look: the range is unreadable, or git is missing
NOWIN = 0x08000000 if os.name == "nt" else 0  # no console window opens for git on Windows
TEST_PATH = re.compile(r"(^|/)(tests?|fixtures)/|(^|/)test_[^/]*$|_test\.[A-Za-z0-9]+$|\.test\.[A-Za-z0-9]+$")
CODE_EXTENSIONS = (".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".rs", ".go", ".java", ".rb", ".c", ".h",
                   ".cpp", ".cs", ".sh", ".ps1", ".html", ".css")
REASON = re.compile(r"^TEST-CHANGE:[ \t]*(\S.*)$", re.M)
HAS_LINE = re.compile(r"^TEST-CHANGE:", re.M)
BREAKS = ("no-refusal", "no-empty-reason", "no-code-check")
BREAK = None


class CannotLook(Exception):
    """The checker could not read the range; its words go out with exit 78."""


def git(root, *args):
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", creationflags=NOWIN)
    if r.returncode != 0:
        raise CannotLook("git %s: %s" % (" ".join(args[:2]), (r.stderr or r.stdout).strip()[:200]))
    return r.stdout


def is_test(path):
    return bool(TEST_PATH.search(path))


def is_code(path):
    return path.endswith(CODE_EXTENSIONS)


def read_commit(root, commit):
    """(lines of existing tests removed, whether code changed) for one commit against its first parent."""
    removed, code = 0, False
    for line in git(root, "show", "--numstat", "--no-renames", "--format=", commit).splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added, deleted, path = parts
        if is_test(path):
            if deleted != "-":  # "-" means a binary file: no line count to read
                removed += int(deleted)
        elif is_code(path):
            code = True
    if BREAK == "no-code-check":  # the break: a test-only edit is counted as if code had changed too
        code = True
    return removed, code


def reason_of(root, commit):
    """(has a TEST-CHANGE line at all, the reason written after it or None)."""
    body = git(root, "show", "-s", "--format=%B", commit)
    m = REASON.search(body)
    if m:
        return True, m.group(1).strip()
    if BREAK == "no-empty-reason" and HAS_LINE.search(body):
        return True, "(empty)"
    return bool(HAS_LINE.search(body)), None


def analyze(root, rng):
    """(commits read, rows) -- one row for each commit that changed an existing test beside code."""
    if ".." not in rng:
        raise CannotLook("the range %r is not BASE..HEAD" % rng)
    commits = git(root, "rev-list", "--no-merges", "--reverse", rng).split()
    rows = []
    for c in commits:
        removed, code = read_commit(root, c)
        if not removed or not code:
            continue
        has_line, reason = reason_of(root, c)
        if reason:
            verdict, why = "EXPLAINED", reason
        elif BREAK == "no-refusal" and not has_line:
            verdict, why = "EXPLAINED", "(no reason given)"
        else:
            verdict, why = "REFUSED", "removes %d line(s) from an existing test beside a code change, with no TEST-CHANGE: line" % removed
        subject = git(root, "show", "-s", "--format=%s", c).strip()
        rows.append({"commit": c[:9], "subject": subject, "verdict": verdict, "why": why})
    return len(commits), rows


def print_rows(n, rows, rng):
    print("test-freeze: %s, %d commit(s) read (merges left out)" % (rng, n))
    for r in rows:
        print("  %-9s %s %s" % (r["verdict"], r["commit"], r["subject"][:80]))
        print("            %s" % r["why"][:160])


# -- the self-test: a scratch repository, each case's verdict expected by its subject line ----------------------------------------

EXPECTED = {"c3 refused": "REFUSED", "c4 explained": "EXPLAINED", "c6 empty reason": "REFUSED"}
NOT_JUDGED = ("c1 tests only", "c2 code only", "c5 test only")


def self_test(quiet=False):
    tmp = Path(tempfile.mkdtemp(prefix="test_freeze_"))
    say = (lambda *a: None) if quiet else print
    bad = 0
    try:
        def write(rel, text):
            p = tmp / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8", newline="\n")

        def commit(message):
            for args in (["add", "-A"], ["-c", "gc.auto=0", "-c", "user.name=test", "-c", "user.email=test@example.com",
                                         "-c", "commit.gpgsign=false", "commit", "-q", "--no-verify", "-m", message]):
                r = subprocess.run(["git", "-C", str(tmp), *args], capture_output=True, text=True, creationflags=NOWIN)
                if r.returncode:
                    raise CannotLook("the scratch repository would not commit %r: %s" % (message, r.stderr.strip()[:200]))

        r = subprocess.run(["git", "init", "-q", str(tmp)], capture_output=True, creationflags=NOWIN)
        if r.returncode:
            raise CannotLook("git init failed in the scratch folder")
        write("lib.py", "def f():\n    return 1\n")
        write("tests/test_lib.py", "assert f() == 1\nassert f() != 2\n")
        commit("base")
        base = git(tmp, "rev-parse", "HEAD").strip()
        write("tests/test_more.py", "assert True\n")
        commit("c1 tests only")
        write("lib.py", "def f():\n    return 1  # same\n")
        commit("c2 code only")
        write("tests/test_lib.py", "assert f() == 1\n")
        commit("c5 test only")
        write("lib.py", "def f():\n    return 3\n")
        write("tests/test_lib.py", "assert f() == 3\n")
        commit("c3 refused")
        write("lib.py", "def f():\n    return 4\n")
        write("tests/test_lib.py", "assert f() == 4\n")
        commit("c4 explained\n\nTEST-CHANGE: the old expectation encoded the bug this commit fixes")
        write("lib.py", "def f():\n    return 5\n")
        write("tests/test_lib.py", "assert f() == 5\n")
        commit("c6 empty reason\n\nTEST-CHANGE:")
        n, rows = analyze(tmp, base + "..HEAD")
        got = {r["subject"]: r["verdict"] for r in rows}
        for subject, want in EXPECTED.items():
            have = got.get(subject, "(no row)")
            ok = have == want
            bad += not ok
            say("  %s %-22s expected %-9s got %s" % ("ok " if ok else "RED", subject, want, have))
        for subject in NOT_JUDGED:
            have = got.get(subject, "(no row)")
            ok = have == "(no row)"
            bad += not ok
            say("  %s %-22s expected no row  got %s" % ("ok " if ok else "RED", subject, have))
        try:
            analyze(tmp, "not-a-range")
            bad += 1
            say("  RED  a range without '..' was not refused")
        except CannotLook:
            say("  ok   a range without '..' is refused in words")
        return len(EXPECTED) + len(NOT_JUDGED) + 1, bad
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    global BREAK
    ap = argparse.ArgumentParser(description="a commit that changes an existing test beside code must say why")
    ap.add_argument("mode", nargs="?", choices=["check"])
    ap.add_argument("--range", default="main..HEAD", help="the commits to read, BASE..HEAD (default main..HEAD)")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--break", dest="brk", choices=BREAKS)
    a = ap.parse_args(argv)
    BREAK = a.brk
    if a.self_test:
        n, bad = self_test()
        print("test-freeze self-test %s -- %d case(s), %d not as expected%s"
              % ("RED" if bad else "GREEN", n, bad, " (break %s)" % BREAK if BREAK else ""))
        return 1 if bad else 0
    if a.mode != "check":
        ap.print_help()
        return 2
    _, bad = self_test(quiet=True)
    if bad:
        print("test-freeze RED -- its own self-test has %d case(s) not as expected, so it cannot be trusted to see a test"
              % bad)
        return 1
    try:
        n, rows = analyze(Path.cwd(), a.range)
    except CannotLook as e:
        print("test-freeze could not look: %s" % e)
        return REFUSED_CODE
    print_rows(n, rows, a.range)
    refused = [r for r in rows if r["verdict"] == "REFUSED"]
    print("test-freeze %s -- %d commit(s) read, %d changed an existing test beside code: %d refused, %d explained"
          % ("RED" if refused else "GREEN", n, len(rows), len(refused), len(rows) - len(refused)))
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
