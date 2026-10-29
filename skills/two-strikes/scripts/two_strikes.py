#!/usr/bin/env python3
"""two_strikes.py -- a step that fails twice stops and reports, instead of trying a third time.

WHY. An agent that hits the same failure will often try again, and again, each try a small variation on
the last. That loop spends time and money, and it rarely gets anywhere the second try could not have
reached alone. This script keeps a ledger of failures. The second failure of the same check prints a STOP
line, and exits 1, so the run that called it can stop and hand the failure to a person.

The ledger is a plain JSON file (strikes.json in the project's folder, or the path given with --ledger).
It is only ever appended to. A reset, written by a person once the cause is fixed, starts the count again.

USAGE
    python3 two_strikes.py strike "<check name>" [--note TEXT] [--ledger PATH]
                                 prints the count; exit 0 for a first failure, 1 at the second (STOP)
    python3 two_strikes.py reset "<check name>" [--ledger PATH]
                                 starts the count again for that check, after its cause is fixed
    python3 two_strikes.py ledger [--ledger PATH]
                                 every check and its count since its last reset; exit 1 if any is stopped
    python3 two_strikes.py --self-test [--break NAME]
                                 a scratch ledger with one row per case; each break switches one rule off,
                                 and only its own row may turn RED

Exit codes: 0 fine, 1 stopped (or a refused strike), 78 the ledger file cannot be read.
"""
import argparse
import datetime
import json
import shutil
import sys
import tempfile
from pathlib import Path

REFUSED_CODE = 78  # the ledger file exists but cannot be read as a ledger
STOP_AT = 2
BREAKS = ("no-stop", "no-reset", "no-count-by-check")
BREAK = None


class CannotLook(Exception):
    """The ledger cannot be read; its words go out with exit 78."""


def load(path):
    path = Path(path)
    if not path.is_file():
        return []
    try:
        entries = json.loads(path.read_text(encoding="utf-8")).get("entries")
    except (ValueError, AttributeError) as e:
        raise CannotLook("%s is not a ledger (%s)" % (path, e))
    if not isinstance(entries, list):
        raise CannotLook("%s has no list of entries" % path)
    return entries


def append(path, entry):
    entries = load(path)
    entries.append(entry)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"entries": entries}, indent=2) + "\n", encoding="utf-8")


def count(entries, check):
    """Failures of this check since its last reset."""
    n = 0
    for e in entries:
        if BREAK != "no-count-by-check" and e.get("check") != check:
            continue
        if e.get("kind") == "reset" and BREAK != "no-reset":
            n = 0
        elif e.get("kind") == "strike":
            n += 1
    return n


def strike(path, check, note=""):
    """(exit code, lines) for one recorded failure."""
    if not check or not str(check).strip():
        return 1, ["two-strikes: REFUSED -- a strike must name the check that failed; an unnamed strike counts nothing"]
    entries = load(path)
    n = count(entries, check) + 1
    append(path, {"kind": "strike", "check": check, "note": note or "", "at": now()})
    if n >= STOP_AT and BREAK != "no-stop":
        return 1, ["two-strikes: STOP AND REPORT -- %r has failed %d times in a row. Do not try again. Write down what was "
                   "tried, the failing output, and the likely cause, then hand it to a person." % (check, n)]
    return 0, ["two-strikes: %r -- strike %d of %d recorded. One more failure of the same check stops the step."
               % (check, n, STOP_AT)]


def reset(path, check):
    if not check or not str(check).strip():
        return 1, ["two-strikes: REFUSED -- a reset must name the check whose count starts again"]
    append(path, {"kind": "reset", "check": check, "note": "", "at": now()})
    return 0, ["two-strikes: %r -- count reset; the next failure is strike 1 of %d" % (check, STOP_AT)]


def ledger(path):
    """(exit code, lines): every check's count since its last reset."""
    entries = load(path)
    names = []
    for e in entries:
        if e.get("check") not in names:
            names.append(e.get("check"))
    lines = ["two-strikes ledger: %d entr(ies), %d check(s)" % (len(entries), len(names))]
    stopped = False
    for name in sorted(names, key=str):
        n = count(entries, name)
        if n >= STOP_AT:
            stopped = True
            status = "STOP -- report it, do not try again"
        else:
            status = "one more failure stops it" if n == STOP_AT - 1 else "no failures since its last reset"
        lines.append("  %-40s %d failure(s)  %s" % (name, n, status))
    return (1 if stopped else 0), lines


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


# -- the self-test: one ledger in a scratch folder, each case checked in the order it happens -----------------------------------------

def self_test(quiet=False):
    tmp = Path(tempfile.mkdtemp(prefix="two_strikes_"))
    say = (lambda *a: None) if quiet else print
    bad = 0
    try:
        path = tmp / "strikes.json"
        cases = []

        code, lines = strike(path, "build the parser")
        cases.append(("a first failure is counted, not stopped", code == 0 and "1 of 2" in lines[0]
                      and "STOP" not in lines[0]))
        code, lines = strike(path, "build the parser")
        cases.append(("a second failure of the same check stops and reports", code == 1 and "STOP AND REPORT" in lines[0]))
        code, lines = ledger(path)
        cases.append(("the ledger shows the stopped check", code == 1 and any(
            "build the parser" in line and "STOP" in line for line in lines[1:])))
        code, lines = strike(path, "run the import")
        cases.append(("a failure of another check starts its own count", code == 0 and "1 of 2" in lines[0]))
        code, lines = reset(path, "build the parser")
        strike_code, strike_lines = strike(path, "build the parser")
        cases.append(("a reset starts the count again", code == 0 and strike_code == 0 and "1 of 2" in strike_lines[0]))
        code, lines = strike(path, "")
        cases.append(("a strike with no check name is refused in words", code == 1 and "REFUSED" in lines[0]))

        for name, ok in cases:
            bad += not ok
            say("  %s %s" % ("ok " if ok else "RED", name))
        return len(cases), bad
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    global BREAK
    ap = argparse.ArgumentParser(description="a step that fails twice stops and reports")
    ap.add_argument("mode", nargs="?", choices=["strike", "reset", "ledger"])
    ap.add_argument("check_name", nargs="?", help="the check that failed, for strike and reset")
    ap.add_argument("--note", default="", help="what failed, in words")
    ap.add_argument("--ledger", default=None, help="the ledger file (default: strikes.json in the current folder)")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--break", dest="brk", choices=BREAKS)
    a = ap.parse_args(argv)
    BREAK = a.brk
    if a.self_test:
        n, bad = self_test()
        print("two-strikes self-test %s -- %d case(s), %d not as expected%s"
              % ("RED" if bad else "GREEN", n, bad, " (break %s)" % BREAK if BREAK else ""))
        return 1 if bad else 0
    if a.mode is None:
        ap.print_help()
        return 2
    _, bad = self_test(quiet=True)
    if bad:
        print("two-strikes RED -- its own self-test has %d case(s) not as expected, so it cannot be trusted to stop a loop"
              % bad)
        return 1
    path = Path(a.ledger) if a.ledger else Path.cwd() / "strikes.json"
    try:
        if a.mode == "strike":
            code, lines = strike(path, a.check_name, a.note)
        elif a.mode == "reset":
            code, lines = reset(path, a.check_name)
        else:
            code, lines = ledger(path)
    except CannotLook as e:
        print("two-strikes could not look: %s" % e)
        return REFUSED_CODE
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
