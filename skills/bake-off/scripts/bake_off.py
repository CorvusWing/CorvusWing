#!/usr/bin/env python3
"""bake_off.py -- builds a piece nobody has invented yet, in an order that stops the tests from being bent.

WHY. A test can only check what has been decided. When the answer to "what should this piece do" does not
exist yet, the usual loop ("make the tests pass") is the wrong loop: the cheapest way to pass a test is to
change it. A bake-off fixes the order instead, and writes the order down in one record, bake-off/<name>.json:

    1. socket      what the piece takes in, what it hands out, and the rules any correct version must obey;
                   its files are frozen from here on
    2. rules       those rules as tests, committed on their own; their files are frozen from here on
    3. control     a deliberately dumb version run through the same tests; a test the control passes is
                   marked TOO WEAK, never tuned around
    4. candidates  each on its own branch from the control, each with a kill line written down and committed
                   BEFORE the candidate, and its first run after the kill line's time
    5. scoreboard  every candidate and the control on every rule; every change another part made is LISTED
                   with its before and after, never failed
    6. pick        by a person, with a reason; never a candidate whose kill line was hit

The script checks that record against git: every part names a commit; socket, rules, control, scoreboard and
pick come in that order; each candidate descends from the rules and the control, no candidate descends from
another, and a candidate's branch (when named) holds its commit; no candidate, nor the control, nor the
scoreboard, changed the socket's or the rules' files; each kill line's words are in a commit before its
candidate's; every result is "pass" or "fail". It refuses in words, and it prints a scoreboard only for a
record that checks.

USAGE (run from the project's folder; the records are in bake-off/)
    python3 bake_off.py check <name>        exit 0 when in order, 1 when refused, 78 when it cannot look
    python3 bake_off.py scoreboard <name>   the table, and the listed changes; refused alone when it does not check
    python3 bake_off.py --self-test [--break NAME]
                                            a scratch repository with one row per case; each break switches one
                                            rule off, and only its own row may turn RED

LIMITS, stated plainly. The script reads what the record says and what git holds. It cannot tell whether a
result is true, and it runs no test. A person reads the scoreboard and makes the pick.
"""
import argparse
import copy
import datetime
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

REFUSED_CODE = 78  # the checker could not look: the record is missing, or git cannot read the commits
NOWIN = 0x08000000 if os.name == "nt" else 0
NAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
PARTS = ("socket", "rules", "control", "candidates", "scoreboard", "pick")
RESULTS = ("pass", "fail")
PLACEHOLDERS = {"n/a", "na", "none", "nothing", "tbd", "todo", "wip", "best", "fastest", "it passes", "passes", "ok",
                "same", "see above", "x", ""}
MIN_WORDS = 3  # a reason says what the pick does better; under three words it cannot
BREAKS = ("no-parts", "no-commit-check", "no-order", "no-candidate-order", "no-sibling-check", "no-branch-check",
          "no-frozen-rules", "no-files-exist", "no-control", "no-too-weak", "no-result-words", "no-rule-count",
          "no-kill-text", "no-hit-flag", "no-kill-anchor", "no-kill-in-commit", "no-kill-line-age", "no-hit-check",
          "no-reason", "no-placeholder-check", "no-control-column", "no-listing", "no-refusal")
BREAK = None
_SEEN = {}  # git's answers to read-only questions, by repository and question: one check asks many twice


class CannotLook(Exception):
    """The record or the repository cannot be read; its words go out with exit 78."""


def run_git(root, *args, stdin=None):
    """(exit code, output) of one git command; git that cannot start is refused in words."""
    try:
        r = subprocess.run(["git", "-C", str(root), "-c", "core.quotePath=false", *args], input=stdin,
                           capture_output=True, creationflags=NOWIN)
    except OSError as e:
        raise CannotLook("git could not be started (%s); is git installed and on the PATH?" % e)
    return r.returncode, r.stdout.decode("utf-8", "replace")


def git(root, *args):
    """run_git for a question that only reads, asked once per run."""
    key = (str(root),) + args
    if key not in _SEEN:
        _SEEN[key] = run_git(root, *args)
    return _SEEN[key]


def resolve(root, ref):
    """The full id of a commit reference, or None when this repository does not have that commit."""
    if not isinstance(ref, str) or not ref:
        return None
    rc, out = git(root, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
    if rc == 128:
        raise CannotLook("%s is not a git repository" % root)
    return out.strip() or None


def before(root, a, b):
    """True when commit a is an ancestor of commit b, and not the same commit."""
    return a != b and git(root, "merge-base", "--is-ancestor", a, b)[0] == 0


def has_path(root, commit, path):
    return git(root, "cat-file", "-e", "%s:%s" % (commit, path))[0] == 0


def changed_files(root, a, b, files):
    """The listed files (or folders) that differ between two commits."""
    rc, out = git(root, "--literal-pathspecs", "diff", "--name-only", "--no-renames", "--no-ext-diff", "-z", a, b, "--",
                  *files)
    if rc not in (0, 1):
        raise CannotLook("git diff %s %s could not compare the frozen files" % (a[:9], b[:9]))
    return [p for p in out.split("\0") if p]


def has_words(root, commit, text):
    """True when a file in the commit holds the text (as written, or as JSON writes it inside a string)."""
    needle = str(text).strip().splitlines()[0].strip()
    escaped = json.dumps(needle, ensure_ascii=False)[1:-1]
    rc, _ = git(root, "grep", "-q", "-F", "-I", "-e", needle, "-e", escaped, commit)
    return rc == 0


def when(text):
    """A stored time; a trailing Z is read as UTC on every Python version."""
    text = str(text)
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    t = datetime.datetime.fromisoformat(text)
    if t.tzinfo is None:
        raise ValueError("%r has no time zone" % text)
    return t


def words(text):
    return " ".join(str(text or "").split())


def reason_problem(text):
    """None for a reason a person can act on; otherwise what is wrong with it, in words."""
    t = words(text)
    if not t:
        return "is empty"
    if BREAK == "no-placeholder-check":
        return None
    if t.strip(" .!?:;,-").lower() in PLACEHOLDERS:
        return "says %r, a placeholder, not a reason" % t
    if len(t.split()) < MIN_WORDS:
        return "says %r, under %d words" % (t, MIN_WORDS)
    return None


def record_path(root, name):
    return Path(root) / "bake-off" / ("%s.json" % name)


def load_record(root, name):
    path = record_path(root, name)
    if not path.is_file():
        raise CannotLook("no record at %s" % path)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        raise CannotLook("%s cannot be read as JSON (%s)" % (path, e))
    if not isinstance(data, dict):
        raise CannotLook("%s is not an object of parts" % path)
    return data


def files_of(part):
    files = part.get("files")
    if isinstance(files, str):
        files = [files]
    if not isinstance(files, list):
        return []
    out = []
    for f in files:
        if isinstance(f, str) and f.strip():
            f = f.strip().replace("\\", "/")
            while f.startswith("./"):
                f = f[2:]
            out.append(f.rstrip("/"))
    return out


def evaluate(root, name):
    """(verdict, reasons): verdict GREEN or REFUSED. An unreadable record or repository raises CannotLook."""
    if not NAME.match(str(name or "")):
        return "REFUSED", ["%r is not a record name: use lowercase letters, digits, '.', '_' and '-'" % name]
    data = load_record(root, name)

    def part(key):
        return data.get(key) if isinstance(data.get(key), dict) else {}

    def kill(c):
        return c.get("kill_line") if isinstance(c.get("kill_line"), dict) else {}

    socket, rules, control, scoreboard, pick = (part(k) for k in ("socket", "rules", "control", "scoreboard", "pick"))
    candidates = [c for c in data.get("candidates") or [] if isinstance(c, dict)] \
        if isinstance(data.get("candidates"), list) else []
    rule_tests = [t for t in rules.get("tests") or [] if isinstance(t, str)] if isinstance(rules.get("tests"), list) else []
    results = control.get("results") if isinstance(control.get("results"), dict) else {}
    reasons = []
    say = reasons.append

    def label(c):
        return "candidate %s" % (c.get("name") or "(unnamed)")

    if BREAK != "no-parts":
        for key in PARTS:
            if not data.get(key):
                say("part missing: %s" % key)
        if rules and not files_of(rules):
            say("the rules list no files (rules.files): the rule tests' files, which nothing after them may change")
        if socket and not files_of(socket):
            say("the socket lists no files (socket.files): the socket's own files, which nothing after it may change")
        names = [c.get("name") for c in candidates]
        for c in candidates:
            for field in ("name", "first_run_at", "results"):
                if not c.get(field):
                    say("%s has no %s" % (label(c), field))
            if not kill(c):
                say("%s has no kill line" % label(c))
            for t in rule_tests:
                if t not in (c.get("results") or {}):
                    say("%s has no result for rule test %s" % (label(c), t))
        if len(set(map(str, names))) != len(names):
            say("two candidates share a name")
        if pick and pick.get("candidate") not in names:
            say("the pick names %r, which is not a candidate" % pick.get("candidate"))

    if BREAK != "no-commit-check":
        for key, p in (("socket", socket), ("rules", rules), ("control", control), ("scoreboard", scoreboard), ("pick", pick)):
            if p and not p.get("commit"):
                say("%s names no commit" % key)
        for c in candidates:
            if not c.get("commit"):
                say("%s names no commit" % label(c))
            if kill(c) and not kill(c).get("commit"):
                say("%s's kill line names no commit (the commit where it was written down)" % label(c))

    def sha(ref, what):
        if not ref:
            return None
        found = resolve(root, ref)
        if found is None:
            say("%s names commit %r, which this repository does not have" % (what, ref))
        return found

    s_sha, r_sha = sha(socket.get("commit"), "socket"), sha(rules.get("commit"), "rules")
    c_sha, sb_sha = sha(control.get("commit"), "control"), sha(scoreboard.get("commit"), "scoreboard")
    p_sha = sha(pick.get("commit"), "pick")
    cands = [(c, label(c), sha(c.get("commit"), label(c)), sha(kill(c).get("commit"), label(c) + "'s kill line"))
             for c in candidates]

    if BREAK != "no-order":
        for la, a, lb, b in (("socket", s_sha, "rules", r_sha), ("rules", r_sha, "control", c_sha),
                             ("control", c_sha, "scoreboard", sb_sha), ("scoreboard", sb_sha, "pick", p_sha)):
            if a and b and not before(root, a, b):
                say("%s is not committed before %s" % (la, lb))

    if BREAK != "no-candidate-order":
        for _, lab, cs, _ in cands:
            for la, a in (("rules", r_sha), ("control", c_sha)):
                if a and cs and not before(root, a, cs):
                    say("%s is not committed before %s" % (la, lab))

    if BREAK != "no-sibling-check":
        for i, (_, l1, s1, _) in enumerate(cands):
            for _, l2, s2, _ in cands[i + 1:]:
                if not s1 or not s2:
                    continue
                if s1 == s2:
                    say("%s and %s name the same commit; each candidate is its own line of work" % (l1, l2))
                for la, a, lb, b in ((l1, s1, l2, s2), (l2, s2, l1, s1)):
                    if before(root, a, b):
                        say("%s is an ancestor of %s; candidates are siblings, each built from the control" % (la, lb))

    if BREAK != "no-branch-check":
        for c, lab, cs, _ in cands:
            branch = c.get("branch")
            if branch is None:
                continue
            tip = resolve(root, branch) if isinstance(branch, str) and branch else None
            if tip is None:
                say("%s's branch %r does not resolve in this repository" % (lab, branch))
            elif cs and tip != cs and not before(root, cs, tip):
                say("%s's branch %r does not contain its commit" % (lab, branch))

    if BREAK != "no-files-exist":
        for key, at, files in (("rules", r_sha, files_of(rules)), ("socket", s_sha, files_of(socket))):
            for f in files:
                if at and not has_path(root, at, f):
                    say("%s.files names %r, which the %s commit does not have" % (key, f, key))

    if BREAK != "no-frozen-rules":
        later = [("the control", c_sha)] + [(lab, cs) for _, lab, cs, _ in cands] + [("the scoreboard", sb_sha)]
        for what, base, files, targets in (("the socket's files", s_sha, files_of(socket), [("the rules", r_sha)] + later),
                                           ("the rule tests", r_sha, files_of(rules), later)):
            if not base or not files:
                continue
            for lab, target in targets:
                moved = changed_files(root, base, target, files) if target else []
                if moved:
                    say("%s changed %s since they were committed: %s" % (lab, what, ", ".join(moved[:5])))

    if BREAK != "no-control":
        if not results:
            say("the control has no rows")
        for t in rule_tests:
            if results and t not in results:
                say("the control was not run on rule test %s" % t)

    if BREAK != "no-result-words":
        for lab, res in [("the control", results)] + [(label(c), c.get("results")) for c in candidates]:
            for t, v in sorted((res or {}).items() if isinstance(res, dict) else []):
                if v not in RESULTS:
                    say("%s's result for %s is %r; a result is pass or fail" % (lab, t, v))

    if BREAK != "no-too-weak":
        marked = set(control.get("too_weak") or [])
        for t, v in results.items():
            if v == "pass" and t not in marked:
                say("the control passes %s, which is not marked TOO WEAK" % t)

    if BREAK != "no-rule-count" and rules and not rule_tests:
        say("the rules name no test (rules.tests); a bake-off with nothing to pass compares nothing")

    for c, lab, cs, ks in cands:
        kl = kill(c)
        if not kl:
            continue  # reported as missing above
        text = words(kl.get("text"))
        if BREAK != "no-kill-text" and not text:
            say("%s's kill line has no words (kill_line.text)" % lab)
        if BREAK != "no-hit-flag" and not isinstance(kl.get("hit"), bool):
            say("%s's kill line does not say whether it was hit (kill_line.hit: true or false)" % lab)
        if BREAK != "no-kill-anchor" and ks and cs and not before(root, ks, cs):
            say("%s's kill line is not committed before the candidate" % lab)
        if BREAK != "no-kill-in-commit" and ks and text and not has_words(root, ks, kl.get("text")):
            say("%s's kill line words are not in its commit %s" % (lab, ks[:9]))
        if BREAK != "no-kill-line-age":
            written, first = kl.get("written_at"), c.get("first_run_at")
            if not written:
                say("%s's kill line has no time (kill_line.written_at)" % lab)
            elif first:
                try:
                    if when(written) >= when(first):
                        say("%s: its kill line (%s) is not older than its first run (%s)" % (lab, written, first))
                except (ValueError, TypeError) as e:
                    say("%s: a time does not read (%s)" % (lab, e))

    if BREAK != "no-hit-check":
        for c in candidates:
            if pick and c.get("name") == pick.get("candidate") and kill(c).get("hit") is True:
                say("the pick names %s, whose kill line was hit; a candidate past its kill line is dead" % c.get("name"))

    reason = pick.get("reason")
    if pick and (BREAK != "no-reason" or words(reason)):
        problem = reason_problem(reason)
        if problem:
            say("the pick's reason %s" % problem)

    return ("REFUSED" if reasons else "GREEN"), reasons


def scoreboard_lines(root, name):
    """(verdict, lines): the table and the listed changes, or the refusal alone."""
    verdict, reasons = evaluate(root, name)
    if verdict == "REFUSED" and BREAK != "no-refusal":
        return verdict, ["bake-off scoreboard %s: REFUSED -- %s. No table is printed: a comparison that did not happen "
                         "must never read as a result." % (name, "; ".join(reasons))]
    data = load_record(root, name)
    rules = (data.get("rules") or {}).get("tests") or []
    control = data.get("control") or {}
    candidates = data.get("candidates") or []
    cols = [] if BREAK == "no-control-column" else [("control", control.get("results") or {})]
    cols += [(str(c.get("name")), c.get("results") or {}) for c in candidates]
    test_width = max([len(t) for t in rules] + [len("rule test")]) + 2
    col_width = max([len(n) for n, _ in cols] + [len("control")]) + 2
    lines = ["bake-off scoreboard %s: %s" % (name, verdict)]
    lines.append("%-*s" % (test_width, "rule test") + "".join("%-*s" % (col_width, n) for n, _ in cols))
    for t in rules:
        lines.append("%-*s" % (test_width, t) + "".join("%-*s" % (col_width, res.get(t) or "none") for _, res in cols))
    lines.append("")
    for n, res in cols:
        lines.append("  %-*s passes %d of %d rule tests" % (col_width, n, sum(1 for t in rules if res.get(t) == "pass"),
                                                            len(rules)))
    for c in candidates:
        kl = c.get("kill_line") or {}
        lines.append("  %-*s kill line %s: %s" % (col_width, c.get("name"), "HIT" if kl.get("hit") else "not hit",
                                                 words(kl.get("text"))))
    marked = set(control.get("too_weak") or [])
    passes = [t for t in rules if (control.get("results") or {}).get(t) == "pass"]
    if passes:
        lines.append("  control passes, each marked TOO WEAK: %s"
                     % ", ".join("%s (%s)" % (t, "marked" if t in marked else "NOT marked") for t in passes))
    pick = data.get("pick") or {}
    lines.append("  pick: %s -- %s" % (pick.get("candidate"), pick.get("reason")))
    changes = [] if BREAK == "no-listing" else [
        {"part": c.get("part"), "case": c.get("case"), "before": c.get("before"), "after": c.get("after")}
        for c in (data.get("scoreboard") or {}).get("other_changes") or []]
    lines.append("")
    lines.append("changes other parts made, LISTED, never failed: %d" % len(changes))
    for c in changes:
        lines.append("  [%s] %s: before %s | after %s" % (c.get("part"), c.get("case"), c.get("before"), c.get("after")))
    return verdict, lines


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
        sys.stderr.write("bake-off: cleanup could not remove %d item(s) of the scratch folder %s; the first: %s\n"
                         % (len(failed), path, failed[0]))


def build_repo(folder, commits):
    """A bare scratch repository built in one git fast-import call, so no hook, identity or clock of the user's is
    involved. commits: [(branch, parent number or None, message, {path: text})]. Returns the commits' ids in order."""
    rc, _ = run_git(folder, "init", "-q", "--bare")
    if rc:
        raise CannotLook("git init failed in the scratch folder %s" % folder)
    stream = bytearray()
    for n, (branch, parent, message, files) in enumerate(commits, 1):
        msg = message.encode("utf-8")
        stream += b"commit refs/heads/%s\nmark :%d\ncommitter test <test@example.com> %d +0000\ndata %d\n%s\n" % (
            branch.encode("utf-8"), n, 1767225600 + 60 * n, len(msg), msg)
        if parent:
            stream += b"from :%d\n" % parent
        for path, text in files.items():
            data = text.encode("utf-8")
            stream += b"M 100644 inline %s\ndata %d\n%s\n" % (path.encode("utf-8"), len(data), data)
        stream += b"\n"
    marks = Path(folder) / "marks.txt"
    rc, _ = run_git(folder, "fast-import", "--quiet", "--export-marks=" + str(marks), stdin=bytes(stream))
    if rc:
        raise CannotLook("git fast-import could not build the scratch repository")
    ids = dict(line.split() for line in marks.read_text(encoding="ascii").splitlines() if line.strip())
    return [ids[":%d" % n] for n in range(1, len(commits) + 1)]


def proven():
    """0 when this exact script, on this Python and this git, has passed its self-test; runs it when not yet known."""
    seed = Path(__file__).read_bytes() + ("|%s|%s" % (sys.version, run_git(".", "--version")[1].strip())).encode()
    mark = Path(tempfile.gettempdir()) / ("corvuswing-bake-off-%s.green" % hashlib.sha256(seed).hexdigest()[:20])
    if mark.is_file():
        return 0
    _, bad = self_test(quiet=True)
    if not bad:
        try:
            mark.write_bytes(b"")
        except OSError:
            pass
    return bad


# -- the self-test: one complete bake-off in a scratch repository, then one changed part per row --------------------------------------

TESTS = ["takes_empty", "keeps_order"]
KILL = {"a": "candidate a is dead if keeps_order fails on any input", "b": "candidate b is dead if it is slower than the control",
        "c": "candidate c is dead if it needs a third pass over the list"}


def build_fixture(tmp):
    """A scratch repository with the six parts committed in order, each candidate on its own branch from the control,
    and a third candidate that bends a rule test. Returns (the record, {step: commit id})."""
    steps = [("socket", "main", None, {"socket.txt": "takes a list, hands out a sorted list\n"}),
             ("rules", "main", None, {"tests/rules_test.py": "def test_takes_empty():\n    assert sort([]) == []\n"
                                                             "def test_keeps_order():\n    assert sort([2, 1]) == [1, 2]\n"}),
             ("control", "main", None, {"control.py": "def sort(x):\n    return x\n"}),
             ("kill a", "try-a", 3, {"kill-lines/a.txt": KILL["a"] + "\n"}),
             ("candidate a", "try-a", None, {"candidate_a.py": "def sort(x):\n    return sorted(x)\n"}),
             ("kill b", "try-b", 3, {"kill-lines/b.txt": KILL["b"] + "\n"}),
             ("candidate b", "try-b", None, {"candidate_b.py": "def sort(x):\n    return x[::-1]\n"}),
             ("kill c", "try-c", 3, {"kill-lines/c.txt": KILL["c"] + "\n"}),
             ("candidate c", "try-c", None, {"candidate_c.py": "def sort(x):\n    return x\n",
                                             "tests/rules_test.py": "def test_takes_empty():\n    pass\n"}),
             ("scoreboard", "main", None, {"scoreboard.txt": "the scoreboard\n"}),
             ("pick", "main", None, {"pick.txt": "the pick\n"})]
    ids = build_repo(tmp, [(branch, parent, message, files) for message, branch, parent, files in steps])
    at = {message: c for (message, _, _, _), c in zip(steps, ids)}

    def candidate(name, results):
        return {"name": name, "branch": "try-" + name, "commit": at["candidate " + name],
                "kill_line": {"text": KILL[name], "hit": False, "commit": at["kill " + name],
                              "written_at": "2026-10-27T10:00:00-07:00"},
                "first_run_at": "2026-10-27T11:00:00-07:00", "results": results}

    record = {
        "name": "sort-list",
        "socket": {"commit": at["socket"], "files": ["socket.txt"], "takes": "a list", "hands_out": "a sorted list"},
        "rules": {"commit": at["rules"], "files": ["tests/rules_test.py"], "tests": list(TESTS)},
        "control": {"commit": at["control"], "name": "returns its input",
                    "results": {"takes_empty": "pass", "keeps_order": "fail"}, "too_weak": ["takes_empty"]},
        "candidates": [candidate("a", {"takes_empty": "pass", "keeps_order": "pass"}),
                       candidate("b", {"takes_empty": "pass", "keeps_order": "fail"})],
        "scoreboard": {"commit": at["scoreboard"], "other_changes": [
            {"part": "output format", "case": "empty input", "before": "nothing", "after": "an empty list"}]},
        "pick": {"candidate": "a", "reason": "keeps the order on every rule the control fails", "commit": at["pick"]},
    }
    return record, at, candidate


def self_test(quiet=False):
    tmp = Path(tempfile.mkdtemp(prefix="bake_off_"))
    say = (lambda *a: None) if quiet else print
    rows = []
    try:
        _SEEN.clear()
        try:
            base, at, candidate = build_fixture(tmp)
        except CannotLook as e:
            say("  RED  the self-test could not build its scratch repository -- %s" % e)
            return 1, 1

        def record(data):
            (tmp / "bake-off").mkdir(parents=True, exist_ok=True)
            (tmp / "bake-off" / "sort-list.json").write_text(json.dumps(data), encoding="utf-8")

        def changed(mutate):
            data = copy.deepcopy(base)
            mutate(data)
            return data

        def a(d):
            return d["candidates"][0]

        def bent(d):
            d["candidates"][1] = candidate("c", {"takes_empty": "pass", "keeps_order": "fail"})
            d["candidates"][1]["name"] = "b"

        check_rows = [
            ("a complete bake-off on sibling branches is GREEN", lambda d: None, None),
            ("a missing part is refused", lambda d: d.pop("scoreboard"), "part missing: scoreboard"),
            ("a part that names no commit is refused", lambda d: d["socket"].pop("commit"), "socket names no commit"),
            ("a scoreboard committed before the control is refused",
             lambda d: d["scoreboard"].update(commit=at["rules"]), "control is not committed before scoreboard"),
            ("rules committed after a candidate are refused", lambda d: d["rules"].update(commit=at["candidate b"]),
             "rules is not committed before candidate a"),
            ("a candidate built on another candidate is refused",
             lambda d: d["candidates"][1].update(commit=at["kill a"]), "candidate b is an ancestor of candidate a"),
            ("a branch that does not hold its candidate is refused", lambda d: a(d).update(branch="try-b"),
             "candidate a's branch 'try-b' does not contain its commit"),
            ("a candidate that changed a rule test is refused", bent, "candidate b changed the rule tests"),
            ("a rule file the rules commit does not have is refused",
             lambda d: d["rules"].update(files=["tests/no_such_test.py"]), "rules.files names 'tests/no_such_test.py'"),
            ("a control with no rows is refused", lambda d: d["control"].update(results={}), "the control has no rows"),
            ("a control passing an unmarked test is refused", lambda d: d["control"].update(too_weak=[]),
             "the control passes takes_empty, which is not marked TOO WEAK"),
            ("a result that is not pass or fail is refused", lambda d: d["control"]["results"].update(keeps_order="PASS"),
             "the control's result for keeps_order is 'PASS'"),
            ("rules with no tests are refused", lambda d: d["rules"].update(tests=[]), "the rules name no test"),
            ("a kill line with no words is refused", lambda d: a(d)["kill_line"].update(text=""),
             "candidate a's kill line has no words"),
            ("a kill line with no hit flag is refused", lambda d: a(d)["kill_line"].pop("hit"),
             "candidate a's kill line does not say whether it was hit"),
            ("a kill line committed with its candidate is refused",
             lambda d: a(d)["kill_line"].update(commit=at["candidate a"]),
             "candidate a's kill line is not committed before the candidate"),
            ("a kill line whose words are not in its commit is refused",
             lambda d: a(d)["kill_line"].update(commit=at["control"]), "candidate a's kill line words are not in its commit"),
            ("a kill line written after its first run is refused",
             lambda d: a(d)["kill_line"].update(written_at="2026-10-27T12:00:00-07:00"), "is not older than its first run"),
            ("a pick whose kill line was hit is refused", lambda d: a(d)["kill_line"].update(hit=True),
             "the pick names a, whose kill line was hit"),
            ("a pick with no reason is refused", lambda d: d["pick"].update(reason=""), "the pick's reason is empty"),
            ("a pick with a placeholder reason is refused", lambda d: d["pick"].update(reason="n/a"), "a placeholder"),
        ]
        for name, mutate, expect in check_rows:
            record(changed(mutate))
            got, why = evaluate(tmp, "sort-list")
            if expect is None:
                ok, detail = got == "GREEN", "expected GREEN, got %s%s" % (got, (": " + why[0][:70]) if why else "")
            else:
                ok = got == "REFUSED" and any(expect in r for r in why)
                detail = "expected the reason '%s', got %s" % (expect, ("; ".join(why))[:110] if why else "GREEN")
            rows.append((name, ok, detail))

        for name, data, check in [
            ("a complete bake-off prints the control and each candidate", base,
             lambda t: "control" in t[1] and "REFUSED" not in t[0]),
            ("a change another part made is listed, never failed", base,
             lambda t: any("empty input" in line for line in t)),
            ("a record that does not check prints no table", changed(lambda d: d["pick"].update(commit="0" * 40)),
             lambda t: "No table is printed" in t[0] and not any("rule test" in line for line in t)),
        ]:
            record(data)
            lines = scoreboard_lines(tmp, "sort-list")[1]
            try:
                ok = bool(check(lines))
            except (IndexError, TypeError):
                ok = False
            rows.append((name, ok, lines[0][:80]))
        try:
            evaluate(tmp, "no-such-record")
            rows.append(("a missing record is refused (could not look, exit 78)", False, "it was read"))
        except CannotLook as e:
            rows.append(("a missing record is refused (could not look, exit 78)", True, str(e)[:60]))
        for name, ok, detail in rows:
            say("  %s  %s -- %s" % ("ok " if ok else "RED", name, detail))
        return len(rows), sum(1 for _, ok, _ in rows if not ok)
    finally:
        _SEEN.clear()
        remove_tree(tmp)


def main(argv=None):
    global BREAK
    ap = argparse.ArgumentParser(description="a bake-off: a piece nobody has invented yet, built in an order that stops "
                                             "the tests bending")
    ap.add_argument("mode", nargs="?", choices=["check", "scoreboard"])
    ap.add_argument("name", nargs="?", help="the bake-off's name, as in bake-off/<name>.json")
    ap.add_argument("--root", default=None, help="the repository holding bake-off/ (default: the current folder)")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--break", dest="brk", choices=BREAKS, help="with --self-test only: switch one rule off")
    a = ap.parse_args(argv)
    if a.brk and not a.self_test:
        print("bake-off: --break goes with --self-test only; a real record is never checked with a rule switched off")
        return 2
    BREAK = a.brk
    try:
        if a.self_test:
            n, bad = self_test()
            print("bake-off self-test %s -- %d case(s), %d not as expected%s"
                  % ("RED" if bad else "GREEN", n, bad, " (break %s)" % BREAK if BREAK else ""))
            return 1 if bad else 0
        if a.mode is None or not a.name:
            ap.print_help()
            return 2
        bad = proven()
        if bad:
            print("bake-off RED -- its own self-test has %d case(s) not as expected, so it cannot be trusted to refuse; "
                  "run --self-test to read them" % bad)
            return 1
        root = Path(a.root) if a.root else Path.cwd()
        if a.mode == "check":
            verdict, reasons = evaluate(root, a.name)
            if verdict == "GREEN":
                print("bake-off check %s: GREEN -- the parts are in order, the rules and the socket stayed frozen, the "
                      "control runs every rule test, and the pick has a reason" % a.name)
                return 0
            print("bake-off check %s: REFUSED -- %d reason(s)" % (a.name, len(reasons)))
            for r in reasons:
                print("  - %s" % r)
            return 1
        verdict, lines = scoreboard_lines(root, a.name)
        print("\n".join(lines))
        return 0 if verdict == "GREEN" else 1
    except CannotLook as e:
        print("bake-off could not look: %s" % e)
        return REFUSED_CODE


if __name__ == "__main__":
    sys.exit(main())
