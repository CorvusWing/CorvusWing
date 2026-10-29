#!/usr/bin/env python3
"""test_freeze.py -- refuses a commit that changes or deletes an existing test, unless its message says why.

WHY. The cheapest way to make a failing test pass is to change the test. Sometimes that is right: the test
was wrong, or the requirement moved. But a test changed without a stated reason is how a suite gets weaker
without anyone noticing. This check reads a range of commits and judges every commit that changes or deletes
a test file that existed before it (git's status M or D), whether or not the commit also changes code. Such a
commit must say why, on a line of its own in its message:

    TEST-CHANGE: the old expected value encoded the bug this commit fixes

A commit that only adds new test files is not judged: nothing that existed was weakened. An added skip or
expected-failure marker changes an existing test file, so it is judged like any other change, and its row
names the marker it found.

USAGE
    python3 test_freeze.py check [--range BASE..HEAD] [--net]
        exit 0 when every judged commit is explained, 1 when one is refused, 78 when it cannot look
        (git is missing, the range does not read, or the range holds no commits)
        --net judges the range's combined change instead: one row for what the range as a whole did to the
        tests that existed at its start, explained by a TEST-CHANGE: line in any of its commits
    python3 test_freeze.py --self-test [--break NAME]
        a scratch repository with one row per case; each break switches one rule off, and only its own row
        may turn RED

WHAT COUNTS AS A TEST: a path matching one of TEST_PATTERNS (folders such as tests/, test/, __tests__/,
spec/, fixtures/ and *.Tests/; names such as test_*.py, *_test.go, *.test.js, *.spec.ts, *_spec.rb, and the
CamelCase *Test.java and *Tests.cs). Case does not matter, except in the CamelCase endings, which need the
capital T so that latest.py is not read as a test. WHAT COUNTS AS CODE: any other file, except the documents
named in DOC_EXTENSIONS. Edit those definitions to fit your project; nothing else needs to change.

LIMITS, stated plainly. A test written inside a source file (Rust's #[cfg(test)], for example) is not seen
as a test. A renamed test file reads as deleted and added, so the rename is judged. Merge commits are left
out of the per-commit reading; --net reads what they changed. The skip-marker scan knows the common markers
of pytest, unittest, Jest, Mocha, JUnit, NUnit, xUnit, Go and Rust, and no others. The check reads the
message; it cannot tell whether the reason written there is true. That part stays with the person who
reviews the commit.
"""
import argparse
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

TOOL = "test-freeze"  # the name this script signs its words with
REFUSED_CODE = 78  # the checker could not look: git is missing, or the range is unreadable or empty
NOWIN = 0x08000000 if os.name == "nt" else 0  # no console window opens for git on Windows
TEST_PATTERNS = (
    re.compile(r"(^|/)(tests?|__tests__|specs?|fixtures|testdata)/", re.I),
    re.compile(r"(^|/)[^/]+\.tests?/", re.I),
    re.compile(r"(^|/)test_[^/]*$", re.I),
    re.compile(r"[._](test|spec)\.[a-z0-9]+$", re.I),
    re.compile(r"[A-Za-z0-9_]Tests?\.[A-Za-z0-9]+$"),
)
NARROW_PATTERNS = (re.compile(r"(^|/)(tests?|fixtures)/|(^|/)test_[^/]*$|_test\.[A-Za-z0-9]+$|\.test\.[A-Za-z0-9]+$"),)
DOC_EXTENSIONS = (".md", ".txt", ".rst")
JUDGED = ("M", "T", "D")  # changed, changed type, deleted: each means a test that existed is no longer as it was
SKIP_MARKER = re.compile(
    r"@pytest\.mark\.(skip|skipif|xfail)\b|\bpytest\.(skip|xfail|importorskip)\(|@unittest\.(skip|skipIf|skipUnless|"
    r"expectedFailure)\b|\.(skip|todo|fixme)\(|\b(xit|xdescribe|xtest)\(|@(Ignore|Disabled)\b|#\[ignore\]|"
    r"\bt\.Skip(Now|f)?\(|\[(Ignore|Skip)\b|\bSkip\s*=\s*\"")
REASON_LINE = re.compile(r"^TEST-CHANGE:(.*)$", re.M)
PLACEHOLDERS = {"n/a", "na", "none", "nothing", "tbd", "todo", "wip", "fix", "fixed", "fixes", "test", "tests", "update",
                "updated", "change", "changed", "changes", "same", "see above", "see below", "as above", "ok", "x", ""}
MIN_WORDS = 3  # a reason says what was wrong and why; under three words it cannot
BREAKS = ("no-refusal", "no-empty-reason", "no-placeholder-check", "code-only", "deletions-only", "no-deleted-files",
          "quoted-paths", "narrow-patterns", "no-range-check", "no-empty-range-check", "no-net", "no-net-refusal")
BREAK = None


class CannotLook(Exception):
    """The checker could not read the range; its words go out with exit 78."""


def git(root, *args, binary=False, stdin=None):
    cmd = ["git", "-C", str(root), "-c", "core.quotePath=false", "-c", "i18n.logOutputEncoding=UTF-8", *args]
    try:
        r = subprocess.run(cmd, input=stdin, capture_output=True, creationflags=NOWIN)
    except OSError as e:
        raise CannotLook("git could not be started (%s); is git installed and on the PATH?" % e)
    if r.returncode != 0:
        words = [a for a in args if not a.startswith("-")][:2]
        raise CannotLook("git %s: %s" % (" ".join(words), r.stderr.decode("utf-8", "replace").strip()[:200]))
    return r.stdout if binary else r.stdout.decode("utf-8", "replace")


def sort_path(path):
    """'test', 'docs' or 'code' for one path; None when the path does not read as text."""
    if "�" in path:
        return None
    p = path.replace("\\", "/")
    if any(rx.search(p) for rx in (NARROW_PATTERNS if BREAK == "narrow-patterns" else TEST_PATTERNS)):
        return "test"
    return "docs" if p.lower().endswith(DOC_EXTENSIONS) else "code"


def changes(root, commits):
    """{commit: ([(status, path)], records that would not parse)}, each commit against its first parent, in one git call."""
    table = {c: ([], 0) for c in commits}
    if not commits:
        return table
    feed = ("\n".join(commits) + "\n").encode("ascii")
    if BREAK == "quoted-paths":  # the break: git's default text output, where a non-ASCII path arrives quoted
        out = git(root, "-c", "core.quotePath=true", "diff-tree", "--stdin", "-r", "--root", "--name-status",
                  "--no-renames", stdin=feed)
        current = None
        for line in out.splitlines():
            if "\t" in line and current:
                status, path = line.split("\t", 1)
                table[current][0].append((status[:1], path))
            elif line.strip():
                current = line.split()[0]
        return table
    fields = git(root, "diff-tree", "--stdin", "-r", "--root", "--name-status", "--no-renames", "-z", stdin=feed,
                 binary=True).split(b"\0")
    current, i = None, 0
    while i < len(fields):
        field = fields[i].decode("utf-8", "replace")
        if field in table:  # a commit's id opens its records
            current = field
            i += 1
        elif current and len(field) <= 3 and field[:1] in ("A", "M", "D", "T") and i + 1 < len(fields):
            table[current][0].append((field[:1], fields[i + 1].decode("utf-8", "replace")))
            i += 2
        else:
            if field and current:
                table[current] = (table[current][0], table[current][1] + 1)
            i += 1
    return table


def deleted_test_lines(root, commit):
    """Lines removed from test files by one commit (used only by the deletions-only break, the old rule)."""
    n = 0
    for rec in git(root, "show", "--numstat", "-z", "--format=", "--no-renames", commit).split("\0"):
        parts = rec.strip("\n").split("\t")
        if len(parts) == 3 and parts[1].isdigit() and sort_path(parts[2]) == "test":
            n += int(parts[1])
    return n


def read_commit(root, commit, paths):
    """(subject, message, how many added lines in these test files carry a skip or expected-failure marker)."""
    out = git(root, "--literal-pathspecs", "show", "--format=%s%x00%B%x00", "-U0", "--no-renames", "--no-color",
              "--no-ext-diff", commit, "--", *paths)
    subject, body, patch = (out.split("\0", 2) + ["", ""])[:3]
    marks = sum(1 for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++")
                and SKIP_MARKER.search(line))
    return subject.strip(), body, marks


def reason_problem(text):
    """None for a reason a person can act on; otherwise what is wrong with it, in words."""
    t = " ".join(str(text or "").split())
    if not t:
        return None if BREAK == "no-empty-reason" else "is empty"
    if BREAK == "no-placeholder-check":
        return None
    if t.strip(" .!?:;,-").lower() in PLACEHOLDERS:
        return "says %r, a placeholder, not a reason" % t
    if len(t.split()) < MIN_WORDS:
        return "says %r, under %d words; a reason says what the old test got wrong" % (t, MIN_WORDS)
    return None


def judge(messages, waive):
    """(verdict, why) for the message(s) that must explain a test change. waive is the break that lets a missing line pass."""
    problems = []
    for message in messages:
        for m in REASON_LINE.finditer(message):
            problem = reason_problem(m.group(1))
            if problem is None:
                return "EXPLAINED", "TEST-CHANGE: " + " ".join(m.group(1).split())
            problems.append(problem)
    if problems:
        return "REFUSED", "its TEST-CHANGE: line %s" % problems[0]
    if BREAK == waive:
        return "EXPLAINED", "(no reason given)"
    return "REFUSED", "no TEST-CHANGE: line says why"


def split_range(rng):
    if BREAK != "no-range-check":
        if "..." in rng:
            raise CannotLook("the range %r has three dots, which git reads as both sides' commits; use BASE..HEAD" % rng)
        if ".." not in rng:
            raise CannotLook("the range %r is not BASE..HEAD" % rng)
    base, _, head = rng.partition("..")
    return base or "HEAD", head or "HEAD"


def describe(touched, code):
    names = [("deletes " if s == "D" else "changes ") + p for s, p in touched]
    return "%s%s %s" % (", ".join(names[:3]), (" and %d more" % (len(names) - 3)) if len(names) > 3 else "",
                        ("beside %d code file(s)" % len(code)) if code else "with no code change")


def analyze(root, rng, net=False, stats=None):
    """(commits read, rows): one row per commit that changed or deleted an existing test; with net, one row at most.
    stats, when given, receives how many files could not be sorted and how many merges were left out."""
    stats = {} if stats is None else stats
    stats.update(unsorted=0, merges=0)
    base, head = split_range(rng)
    listed = [line.split() for line in git(root, "rev-list", "--reverse", "--parents", rng).splitlines() if line.strip()]
    every = [ids[0] for ids in listed]
    commits = [ids[0] for ids in listed if len(ids) <= 2]  # one parent, or none: merges are left out
    stats["merges"] = len(every) - len(commits)
    if not every and BREAK != "no-empty-range-check":
        raise CannotLook("the range %s holds no commits, so nothing was read; check that BASE comes first and is not "
                         "already the same as HEAD" % rng)
    if net:
        return len(every), net_rows(root, rng, base, head, commits, stats)
    table = changes(root, commits)
    judged_status = ("M", "T") if BREAK == "no-deleted-files" else JUDGED
    rows = []
    for c in commits:
        pairs, broken = table[c]
        kinds = [(s, p, sort_path(p)) for s, p in pairs]
        stats["unsorted"] += broken + sum(1 for _, _, k in kinds if k is None)
        touched = [(s, p) for s, p, k in kinds if k == "test" and s in judged_status]
        code = [p for _, p, k in kinds if k == "code"]
        if not touched or (BREAK == "code-only" and not code):
            continue
        if BREAK == "deletions-only" and not deleted_test_lines(root, c):
            continue
        subject, body, marks = read_commit(root, c, [p for _, p in touched])
        verdict, why = judge([body], "no-refusal")
        what = describe(touched, code)
        if marks:
            what += "; adds %d line(s) with a skip or expected-failure marker" % marks
        rows.append({"commit": c[:9], "subject": subject, "verdict": verdict, "why": why, "what": what})
    return len(commits), rows


def net_rows(root, rng, base, head, commits, stats):
    """The range's combined change to the tests that existed at its start, judged against every message in it."""
    if BREAK == "no-net":  # the break: the union of each commit's changes, so a test weakened and put back still counts
        seen = {}
        for pairs, _ in changes(root, commits).values():
            seen.update((p, s) for s, p in pairs)
        pairs = [(s, p) for p, s in seen.items()]
    else:
        start = git(root, "merge-base", base, head).strip()
        fields = git(root, "diff", "--name-status", "--no-renames", "-z", start, head, binary=True).split(b"\0")
        pairs = [(fields[i].decode("ascii", "replace")[:1], fields[i + 1].decode("utf-8", "replace"))
                 for i in range(0, len(fields) - 1, 2)]
    kinds = [(s, p, sort_path(p)) for s, p in pairs]
    stats["unsorted"] += sum(1 for _, _, k in kinds if k is None)
    touched = [(s, p) for s, p, k in kinds if k == "test" and s in JUDGED]
    if not touched:
        return []
    messages = git(root, "log", "--format=%B%x00", rng).split("\0")  # merges included: their messages count here
    verdict, why = judge(messages, "no-net-refusal")
    what = describe(touched, [p for _, p, k in kinds if k == "code"])
    return [{"commit": rng, "subject": "the range as a whole (--net)", "verdict": verdict, "why": why, "what": what}]


def print_rows(n, rows, rng, net, stats):
    print("test-freeze: %s, %d commit(s) read%s" % (rng, n, " as one combined change" if net else
          (" (%d merge(s) left out; --net reads what they changed)" % stats["merges"]) if stats.get("merges") else ""))
    for r in rows:
        print("  %-9s %s %s" % (r["verdict"], r["commit"], r["subject"][:80]))
        print("            what: %s" % r["what"][:200])
        print("            why:  %s" % r["why"][:200])


# -- cleanup, the scratch repository, and the self-test's cache ----------------------------------------------------------------

def remove_tree(path):
    """Removes a scratch folder. Git marks its object files read-only, which stops a plain delete on Windows, so a
    refused item has that flag cleared and is tried once more; anything that still will not go is said out loud."""
    failed = []

    def again(func, item, _exc):
        try:
            os.chmod(item, stat.S_IWRITE | stat.S_IREAD)
            func(item)
        except OSError as e:
            failed.append("%s (%s)" % (item, e.strerror or e))

    if not os.path.exists(str(path)):
        return
    if sys.version_info >= (3, 12):
        shutil.rmtree(str(path), onexc=again)
    else:
        shutil.rmtree(str(path), onerror=again)
    if failed:
        sys.stderr.write("%s: cleanup could not remove %d item(s) of the scratch folder %s; the first: %s\n"
                         % (TOOL, len(failed), path, failed[0]))


def build_repo(folder, commits):
    """A bare scratch repository built in one git fast-import call, so no hook, identity or clock of the user's is
    involved. commits: [(branch, parent number or None, message, {path: text, or None to delete})]. Returns the
    commits' ids in order."""
    git(folder, "init", "-q", "--bare")
    stream = bytearray()
    for n, (branch, parent, message, files) in enumerate(commits, 1):
        msg = message.encode("utf-8")
        stream += b"commit refs/heads/%s\nmark :%d\ncommitter test <test@example.com> %d +0000\ndata %d\n%s\n" % (
            branch.encode("utf-8"), n, 1767225600 + 60 * n, len(msg), msg)
        if parent:
            stream += b"from :%d\n" % parent
        for path, text in files.items():
            if text is None:
                stream += b"D %s\n" % path.encode("utf-8")
            else:
                data = text.encode("utf-8")
                stream += b"M 100644 inline %s\ndata %d\n%s\n" % (path.encode("utf-8"), len(data), data)
        stream += b"\n"
    marks = Path(folder) / "marks.txt"
    git(folder, "fast-import", "--quiet", "--export-marks=" + str(marks), stdin=bytes(stream))
    ids = dict(line.split() for line in marks.read_text(encoding="ascii").splitlines() if line.strip())
    return [ids[":%d" % n] for n in range(1, len(commits) + 1)]


def proven():
    """0 when this exact script, on this Python and this git, has passed its self-test; runs it when not yet known.
    The proof is a small marker in the system's temp folder, named by a hash of all three."""
    seed = Path(__file__).read_bytes() + ("|%s|%s" % (sys.version, git(".", "--version").strip())).encode()
    mark = Path(tempfile.gettempdir()) / ("corvuswing-test-freeze-%s.green" % hashlib.sha256(seed).hexdigest()[:20])
    if mark.is_file():
        return 0
    _, bad = self_test(quiet=True)
    if not bad:
        try:
            mark.write_bytes(b"")
        except OSError:
            pass
    return bad


# -- the self-test: a scratch repository, each case's verdict expected by its subject line ---------------------------------------

CASES = [  # (message, files): the first is the base, each later one a commit on top of the one before
    ("base", {"lib.py": "def f():\n    return 1\n", "tests/test_lib.py": "assert f() == 1\nassert f() != 2\n",
              "tests/test_skip.py": "def test_g():\n    assert g() == 1\n", "tests/test_gone.py": "assert True\n",
              "tests/café.py": "HELPER = 1\n", "docs.md": "notes\n"}),
    ("c1 a new test file alone", {"tests/test_more.py": "assert True\n"}),
    ("c2 code alone", {"lib.py": "def f():\n    return 1  # same\n"}),
    ("c3 a test changed beside code, no reason", {"lib.py": "def f():\n    return 3\n",
                                                  "tests/test_lib.py": "assert f() == 3\n"}),
    ("c4 a test changed beside code, with a reason\n\nTEST-CHANGE: the old expectation encoded the bug this commit "
     "fixes", {"lib.py": "def f():\n    return 4\n", "tests/test_lib.py": "assert f() == 4\n"}),
    ("c5 a test changed alone", {"tests/test_lib.py": "assert f() == 4  # alone\n"}),
    ("c6 an empty reason\n\nTEST-CHANGE:", {"lib.py": "def f():\n    return 5\n", "tests/test_lib.py": "assert f() == 5\n"}),
    ("c7 a placeholder reason\n\nTEST-CHANGE: n/a", {"lib.py": "def f():\n    return 6\n",
                                                     "tests/test_lib.py": "assert f() == 6\n"}),
    ("c8 a skip marker added", {"lib.py": "def f():\n    return 7\n",
                                "tests/test_skip.py": "@pytest.mark.skip\ndef test_g():\n    assert g() == 1\n"}),
    ("c9 a test file deleted", {"lib.py": "def f():\n    return 8\n", "tests/test_gone.py": None}),
    ("c10 a test with a non-ASCII name changed", {"lib.py": "def f():\n    return 9\n", "tests/café.py": "HELPER = 2\n"}),
    ("c11 documents alone", {"docs.md": "more notes\n"}),
    # the --net ranges, after the per-commit cases
    ("n1 weaken a test", {"tests/test_lib.py": "assert True\n"}),
    ("n2 put it back", {"tests/test_lib.py": "assert f() == 6\n"}),
    ("n3 a test changed\n\nTEST-CHANGE: the old value was copied from the wrong fixture",
     {"tests/test_lib.py": "assert f() == 10\n"}),
    ("n4 a test changed", {"tests/test_lib.py": "assert f() == 11\n"}),
    ("n5 code", {"lib.py": "def f():\n    return 11\n"}),
]
VERDICTS = [("c1 a new test file alone", "(no row)"), ("c2 code alone", "(no row)"),
            ("c3 a test changed beside code, no reason", "REFUSED"),
            ("c4 a test changed beside code, with a reason", "EXPLAINED"), ("c5 a test changed alone", "judged"),
            ("c6 an empty reason", "REFUSED"), ("c7 a placeholder reason", "REFUSED"),
            ("c8 a skip marker added", "names the marker"), ("c9 a test file deleted", "judged"),
            ("c10 a test with a non-ASCII name changed", "judged"), ("c11 documents alone", "(no row)")]
SAMPLES = [("src/__tests__/lib.js", "test"), ("spec/models/user_spec.rb", "test"), ("src/lib.spec.ts", "test"),
           ("src/LibTest.java", "test"), ("src/LibTests.cs", "test"), ("MyApp.Tests/Lib.cs", "test"),
           ("Tests/Helpers.py", "test"), ("pkg/lib_test.go", "test"), ("src/latest.py", "code"), ("src/Lib.kt", "code"),
           ("README.md", "docs"), ("notes/plan.rst", "docs")]


def self_test(quiet=False):
    tmp = Path(tempfile.mkdtemp(prefix="test_freeze_"))
    say = (lambda *a: None) if quiet else print
    rows = []
    try:
        ids = build_repo(tmp, [("main", None, message, files) for message, files in CASES])
        at = {message.split("\n")[0]: c for (message, _), c in zip(CASES, ids)}
        _, got_rows = analyze(tmp, at["base"] + ".." + at["c11 documents alone"])
        got = {r["subject"]: r for r in got_rows}
        for subject, want in VERDICTS:
            r = got.get(subject)
            have = r["verdict"] if r else "(no row)"
            if want == "judged":
                ok = r is not None
            elif want == "names the marker":
                ok, have = bool(r) and "skip" in r["what"], r["what"] if r else "(no row)"
            else:
                ok = have == want
            rows.append((subject, ok, "expected %s, got %s" % (want, have)))

        wrong = ["%s read as %s" % (p, sort_path(p)) for p, want in SAMPLES if sort_path(p) != want]
        rows.append(("the patterns sort test, code and document paths", not wrong,
                     "expected all %d as listed, got %s" % (len(SAMPLES), "; ".join(wrong) or "all")))

        last = at["c11 documents alone"]
        for name, rng in (("a range that is not BASE..HEAD is refused in words", last),
                          ("an empty range is refused in words", last + ".." + last)):
            try:
                analyze(tmp, rng)
                rows.append((name, False, "expected a refusal, got a reading"))
            except CannotLook as e:
                rows.append((name, True, "refused: %s" % str(e)[:60]))

        for name, rng, want in (("net: a test weakened and put back reads clean", last + ".." + at["n2 put it back"],
                                 "(no row)"),
                                ("net: a range explained by one commit's reason",
                                 at["n2 put it back"] + ".." + at["n3 a test changed"], "EXPLAINED"),
                                ("net: a range that changes a test with no reason is refused",
                                 at["n3 a test changed"] + ".." + at["n5 code"], "REFUSED")):
            net = analyze(tmp, rng, net=True)[1]
            have = net[0]["verdict"] if net else "(no row)"
            rows.append((name, have == want, "expected %s, got %s" % (want, have)))

        for name, ok, detail in rows:
            say("  %s  %s -- %s" % ("ok " if ok else "RED", name, detail))
        return len(rows), sum(1 for _, ok, _ in rows if not ok)
    finally:
        remove_tree(tmp)


def main(argv=None):
    global BREAK
    ap = argparse.ArgumentParser(description="a commit that changes or deletes an existing test must say why")
    ap.add_argument("mode", nargs="?", choices=["check"])
    ap.add_argument("--range", default="main..HEAD", help="the commits to read, BASE..HEAD (default main..HEAD)")
    ap.add_argument("--net", action="store_true", help="judge the range's combined change, one row")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--break", dest="brk", choices=BREAKS, help="with --self-test only: switch one rule off")
    a = ap.parse_args(argv)
    if a.brk and not a.self_test:
        print("test-freeze: --break goes with --self-test only; a real check never runs with a rule switched off")
        return 2
    BREAK = a.brk
    try:
        if a.self_test:
            n, bad = self_test()
            print("test-freeze self-test %s -- %d case(s), %d not as expected%s"
                  % ("RED" if bad else "GREEN", n, bad, " (break %s)" % BREAK if BREAK else ""))
            return 1 if bad else 0
        if a.mode != "check":
            ap.print_help()
            return 2
        bad = proven()
        if bad:
            print("test-freeze RED -- its own self-test has %d case(s) not as expected, so it cannot be trusted to see a "
                  "test; run --self-test to read them" % bad)
            return 1
        stats = {}
        n, rows = analyze(Path.cwd(), a.range, net=a.net, stats=stats)
    except CannotLook as e:
        print("test-freeze could not look: %s" % e)
        return REFUSED_CODE
    print_rows(n, rows, a.range, a.net, stats)
    refused = [r for r in rows if r["verdict"] == "REFUSED"]
    print("test-freeze %s -- %d commit(s) read, %d judged: %d refused, %d explained; %d file(s) could not be sorted"
          % ("RED" if refused else "GREEN", n, len(rows), len(refused), len(rows) - len(refused), stats["unsorted"]))
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
