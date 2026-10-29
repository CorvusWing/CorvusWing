#!/usr/bin/env python3
"""bake_off.py -- builds a piece nobody has invented yet, in an order that stops the tests from being bent.

WHY. A test can only check what has been decided. When the answer to "what should this piece do" does not
exist yet, the usual loop ("make the tests pass") is the wrong loop: the cheapest way to pass a test is to
change it. A bake-off fixes the order instead, and writes the order down in one record, bake-off/<name>.json:

    1. socket      what the piece takes in, what it hands out, and the rules any correct version must obey
    2. rules       those rules as tests, committed on their own, read-only from then on
    3. control     a deliberately dumb version run through the same tests; a test the control passes is
                   marked TOO WEAK, never tuned around
    4. candidates  each in its own branch, each with a kill line written BEFORE its first run
    5. scoreboard  every candidate and the control on every rule; every change another part made is LISTED
                   with its before and after, never failed
    6. pick        by a person, with a reason; a candidate never picks itself

The script checks that record: the parts are present, each part's commit comes after the one before it, the
control runs every rule test, the control's passes are all marked TOO WEAK, each kill line is older than its
candidate's first run, and the pick has a reason. It refuses in words, and it prints a scoreboard only for a
record that checks.

USAGE (run from the project's folder; the records are in bake-off/)
    python3 bake_off.py check <name>        exit 0 when in order, 1 when refused, 78 when it cannot look
    python3 bake_off.py scoreboard <name>   the table, and the listed changes; refused alone when it does not check
    python3 bake_off.py --self-test [--break NAME]
                                            a scratch repository with one row per case; each break switches one
                                            rule off, and only its own row may turn RED

LIMITS, stated plainly. The script reads what the record says and the order of the commits in git. It cannot
tell whether a result is true, and it runs no test. The planner reads the scoreboard and makes the pick.
"""
import argparse
import copy
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REFUSED_CODE = 78  # the checker could not look: the record is missing, or git cannot read the commits
NOWIN = 0x08000000 if os.name == "nt" else 0
PARTS = ("socket", "rules", "control", "candidates", "scoreboard", "pick")
BREAKS = ("no-parts", "no-order", "no-control", "no-too-weak", "no-kill-line-age", "no-reason", "no-control-column",
          "no-listing", "no-refusal")
BREAK = None


class CannotLook(Exception):
    """The record or the repository cannot be read; its words go out with exit 78."""


def git(root, *args):
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", creationflags=NOWIN)
    return r.returncode, r.stdout


def resolve(root, ref):
    """The full hash of a commit reference, or None when this repository does not have that commit."""
    if not isinstance(ref, str) or not ref:
        return None
    rc, out = git(root, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
    if rc == 128:
        raise CannotLook("%s is not a git repository" % root)
    return out.strip() or None


def before(root, a, b):
    """True when commit a is an ancestor of commit b, and not the same commit."""
    if a == b:
        return False
    rc, _ = git(root, "merge-base", "--is-ancestor", a, b)
    return rc == 0


def record_path(root, name):
    return Path(root) / "bake-off" / ("%s.json" % name)


def load_record(root, name):
    path = record_path(root, name)
    if not path.is_file():
        raise CannotLook("no record at %s" % path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise CannotLook("%s is not JSON (%s)" % (path, e))
    if not isinstance(data, dict):
        raise CannotLook("%s is not an object of parts" % path)
    return data


def when(text):
    t = datetime.datetime.fromisoformat(str(text))
    if t.tzinfo is None:
        raise ValueError("%r has no time zone" % text)
    return t


def evaluate(root, name):
    """(verdict, reasons): verdict GREEN or REFUSED. An unreadable record or repository raises CannotLook."""
    data = load_record(root, name)
    socket, rules = data.get("socket") or {}, data.get("rules") or {}
    control, scoreboard, pick = data.get("control") or {}, data.get("scoreboard") or {}, data.get("pick") or {}
    candidates = data.get("candidates") or []
    rule_tests = list(rules.get("tests") or [])
    results = control.get("results") or {}
    reasons = []

    if BREAK != "no-parts":
        for part in PARTS:
            if not data.get(part):
                reasons.append("part missing: %s" % part)
        for c in candidates:
            label = c.get("name") or "(unnamed)"
            for field in ("name", "commit", "first_run_at", "results"):
                if not c.get(field):
                    reasons.append("candidate %s has no %s" % (label, field))
            if not (c.get("kill_line") or {}).get("written_at"):
                reasons.append("candidate %s has no kill line" % label)
            for t in rule_tests:
                if t not in (c.get("results") or {}):
                    reasons.append("candidate %s has no result for rule test %s" % (label, t))
        if pick and pick.get("candidate") not in [c.get("name") for c in candidates]:
            reasons.append("the pick names %r, which is not a candidate" % pick.get("candidate"))

    s_sha, r_sha = resolve(root, socket.get("commit")), resolve(root, rules.get("commit"))
    c_sha = resolve(root, control.get("commit"))
    sb_sha, p_sha = resolve(root, scoreboard.get("commit")), resolve(root, pick.get("commit"))
    cand_sha = [(c.get("name"), resolve(root, c.get("commit"))) for c in candidates]
    for label, ref, sha in [("socket", socket.get("commit"), s_sha), ("rules", rules.get("commit"), r_sha),
                            ("control", control.get("commit"), c_sha), ("scoreboard", scoreboard.get("commit"), sb_sha),
                            ("pick", pick.get("commit"), p_sha)] + [("candidate %s" % n, c.get("commit"), s)
                                                                    for (n, s), c in zip(cand_sha, candidates)]:
        if ref and sha is None:
            reasons.append("%s names commit %r, which this repository does not have" % (label, ref))

    if BREAK != "no-order":
        pairs = [("socket", s_sha, "rules", r_sha), ("rules", r_sha, "control", c_sha)]
        for n, sha in cand_sha:
            pairs += [("rules", r_sha, "candidate %s" % n, sha), ("control", c_sha, "candidate %s" % n, sha),
                      ("candidate %s" % n, sha, "scoreboard", sb_sha)]
        pairs.append(("scoreboard", sb_sha, "pick", p_sha))
        for la, a, lb, b in pairs:
            if a and b and not before(root, a, b):
                reasons.append("%s is not committed before %s" % (la, lb))

    if BREAK != "no-control":
        if not results:
            reasons.append("the control has no rows")
        for t in rule_tests:
            if results and t not in results:
                reasons.append("the control was not run on rule test %s" % t)

    if BREAK != "no-too-weak":
        marked = set(control.get("too_weak") or [])
        for t, v in results.items():
            if v == "pass" and t not in marked:
                reasons.append("the control passes %s, which is not marked TOO WEAK" % t)

    if BREAK != "no-kill-line-age":
        for c in candidates:
            kl, fr = (c.get("kill_line") or {}).get("written_at"), c.get("first_run_at")
            if not kl or not fr:
                continue  # reported as missing above
            try:
                if when(kl) >= when(fr):
                    reasons.append("candidate %s: its kill line (%s) is not older than its first run (%s)"
                                   % (c.get("name"), kl, fr))
            except (ValueError, TypeError) as e:
                reasons.append("candidate %s: a time does not read (%s)" % (c.get("name"), e))

    if BREAK != "no-reason" and not str(pick.get("reason") or "").strip():
        reasons.append("the pick gives no reason")

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
    cols = [] if BREAK == "no-control-column" else [("control", control.get("results") or {})]
    cols += [(c.get("name"), c.get("results") or {}) for c in data.get("candidates") or []]
    width = max([len(t) for t in rules] + [9])
    lines = ["bake-off scoreboard %s: %s" % (name, verdict)]
    lines.append("%-*s" % (width, "rule test") + "".join("%-14s" % cname for cname, _ in cols))
    for t in rules:
        lines.append("%-*s" % (width, t) + "".join("%-14s" % (res.get(t) or "none") for _, res in cols))
    lines.append("")
    for cname, res in cols:
        lines.append("  %-12s passes %d of %d rule tests" % (cname, sum(1 for t in rules if res.get(t) == "pass"), len(rules)))
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


# -- the self-test: one complete bake-off in a scratch repository, then one changed part per row --------------------------------------

TESTS = ["takes_empty", "keeps_order"]


def build_fixture(tmp):
    """A scratch repository with the six parts committed in order; returns (the record, the commit after the candidates)."""
    def write(rel, text):
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")

    def commit(message):
        for args in (["add", "-A"], ["-c", "gc.auto=0", "-c", "user.name=test", "-c", "user.email=test@example.com",
                                     "-c", "commit.gpgsign=false", "commit", "-q", "--no-verify", "-m", message]):
            r = subprocess.run(["git", "-C", str(tmp), *args], capture_output=True, text=True, creationflags=NOWIN)
            if r.returncode:
                raise CannotLook("the scratch repository would not commit %r: %s" % (message, (r.stderr or r.stdout).strip()[:200]))
        return git(tmp, "rev-parse", "HEAD")[1].strip()

    r = subprocess.run(["git", "init", "-q", str(tmp)], capture_output=True, creationflags=NOWIN)
    if r.returncode:
        raise CannotLook("git init failed in the scratch folder")
    write("socket.txt", "takes a list, hands out a sorted list\n")
    socket = commit("socket")
    write("tests/rules_test.py", "# rules as tests\n")
    rules = commit("rules")
    write("control.txt", "the dumb control: returns its input unchanged\n")
    control = commit("control")
    write("candidate_a.py", "# candidate a\n")
    cand_a = commit("candidate a")
    write("candidate_b.py", "# candidate b\n")
    cand_b = commit("candidate b")
    write("scoreboard.txt", "the scoreboard\n")
    scoreboard = commit("scoreboard")
    write("pick.txt", "the pick\n")
    pick = commit("pick")
    record = {
        "name": "sort-list",
        "socket": {"commit": socket, "takes": "a list", "hands_out": "a sorted list"},
        "rules": {"commit": rules, "tests": list(TESTS)},
        "control": {"commit": control, "name": "returns its input", "results": {"takes_empty": "pass", "keeps_order": "fail"},
                    "too_weak": ["takes_empty"]},
        "candidates": [
            {"name": "a", "commit": cand_a, "kill_line": {"written_at": "2026-10-27T10:00:00-07:00"},
             "first_run_at": "2026-10-27T11:00:00-07:00", "results": {"takes_empty": "pass", "keeps_order": "pass"}},
            {"name": "b", "commit": cand_b, "kill_line": {"written_at": "2026-10-27T10:00:00-07:00"},
             "first_run_at": "2026-10-27T11:00:00-07:00", "results": {"takes_empty": "pass", "keeps_order": "fail"}},
        ],
        "scoreboard": {"commit": scoreboard, "other_changes": [
            {"part": "output format", "case": "empty input", "before": "nothing", "after": "an empty list"}]},
        "pick": {"candidate": "a", "reason": "keeps the order on every rule the control fails", "commit": pick},
    }
    return record, cand_b


def self_test(quiet=False):
    tmp = Path(tempfile.mkdtemp(prefix="bake_off_"))
    say = (lambda *a: None) if quiet else print
    bad = 0
    try:
        try:
            base, cand_b = build_fixture(tmp)
        except CannotLook as e:
            say("  RED  the self-test could not build its scratch repository: %s" % e)
            return 0, 1

        def record(data):
            (tmp / "bake-off").mkdir(parents=True, exist_ok=True)
            (tmp / "bake-off" / "sort-list.json").write_text(json.dumps(data), encoding="utf-8")
            return data

        def changed(mutate):
            data = copy.deepcopy(base)
            mutate(data)
            return data

        def late(d):
            d["rules"]["commit"] = cand_b

        def missing(d):
            del d["scoreboard"]

        def no_rows(d):
            d["control"]["results"] = {}

        def unmarked(d):
            d["control"]["too_weak"] = []

        def young(d):
            d["candidates"][0]["kill_line"]["written_at"] = "2026-10-27T12:00:00-07:00"

        def no_reason(d):
            d["pick"]["reason"] = ""

        check_rows = [
            ("a complete bake-off is GREEN", changed(lambda d: None), "GREEN"),
            ("a missing part is refused", changed(missing), "REFUSED"),
            ("rules committed after a candidate are refused", changed(late), "REFUSED"),
            ("a control with no rows is refused", changed(no_rows), "REFUSED"),
            ("a control passing an unmarked test is refused", changed(unmarked), "REFUSED"),
            ("a kill line written after its first run is refused", changed(young), "REFUSED"),
            ("a pick with no reason is refused", changed(no_reason), "REFUSED"),
        ]
        for name, data, want in check_rows:
            record(data)
            got, why = evaluate(tmp, "sort-list")
            ok = got == want
            bad += not ok
            say("  %s %-54s expected %-8s got %s%s" % ("ok " if ok else "RED", name, want, got,
                                                    ("  (" + why[0] + ")") if why else ""))
        record(base)
        printed = 0
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
            bad += not ok
            say("  %s %s" % ("ok " if ok else "RED", name))
            printed += 1
        try:
            record(base)
            evaluate(tmp, "no-such-record")
            bad += 1
            say("  RED  a missing record was not refused")
        except CannotLook:
            say("  ok   a missing record is refused (could not look, exit 78)")
        return len(check_rows) + printed + 1, bad
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    global BREAK
    ap = argparse.ArgumentParser(description="a bake-off: a piece nobody has invented yet, built in an order that stops the tests bending")
    ap.add_argument("mode", nargs="?", choices=["check", "scoreboard"])
    ap.add_argument("name", nargs="?", help="the bake-off's name, as in bake-off/<name>.json")
    ap.add_argument("--root", default=None, help="the repository holding bake-off/ (default: the current folder)")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--break", dest="brk", choices=BREAKS)
    a = ap.parse_args(argv)
    BREAK = a.brk
    if a.self_test:
        n, bad = self_test()
        print("bake-off self-test %s -- %d case(s), %d not as expected%s"
              % ("RED" if bad else "GREEN", n, bad, " (break %s)" % BREAK if BREAK else ""))
        return 1 if bad else 0
    if a.mode is None or not a.name:
        ap.print_help()
        return 2
    _, bad = self_test(quiet=True)
    if bad:
        print("bake-off RED -- its own self-test has %d case(s) not as expected, so it cannot be trusted to refuse" % bad)
        return 1
    root = Path(a.root) if a.root else Path.cwd()
    try:
        if a.mode == "check":
            verdict, reasons = evaluate(root, a.name)
            if verdict == "GREEN":
                print("bake-off check %s: GREEN -- the parts are in order, the control runs every rule test, the pick has a reason"
                      % a.name)
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
