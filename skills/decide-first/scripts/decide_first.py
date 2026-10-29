#!/usr/bin/env python3
"""decide_first.py -- a design question gets a small, measured decision before any code is written.

WHY. A design question ("should the cache be per user or shared?", "is the slow part the parser or the disk?")
is easy to answer with a plausible story and expensive to answer with code. This script makes the order fixed:

    1. open     write the question, and the condition that would make the answer "no" (the cancel line),
                BEFORE anything is measured;
    2. probe    run the smallest measurement that could show the cancel line is met, and keep its output;
    3. decide   read the output, say whether the cancel line was met, and make the choice with its reason.

A record that breaks that order, or that picks "build" after the cancel line was met, is refused in words.
Only then is code written, and the record is what the code's commit message points at.

USAGE (the record is decisions/<slug>.json in the current folder)
    python3 decide_first.py open <slug> --question TEXT --cancel TEXT
    python3 decide_first.py probe <slug> -- <command and its arguments>
    python3 decide_first.py decide <slug> --cancel-met yes|no --choice build|stop|other --because TEXT
    python3 decide_first.py check <slug>               exit 0 when the record is in order, 1 when refused
    python3 decide_first.py --self-test [--break NAME]  a scratch folder with one row per case; each break
                                                        switches one rule off, and only its own row may turn RED

Exit codes: 0 in order, 1 refused, 2 bad use of the command, 78 a record cannot be read.
"""
import argparse
import datetime
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REFUSED_CODE = 78
OUTPUT_LIMIT = 4000  # characters of probe output kept in the record; the rest is cut and marked
CHOICES = ("build", "stop", "other")
BREAKS = ("no-cancel-order", "no-cancel-stop", "no-output")
BREAK = None


class CannotLook(Exception):
    """The record cannot be read; its words go out with exit 78."""


def now():
    return datetime.datetime.now().astimezone().isoformat()


def when(text):
    t = datetime.datetime.fromisoformat(str(text))
    if t.tzinfo is None:
        raise ValueError("%r has no time zone" % text)
    return t


def path_of(folder, slug):
    return Path(folder) / "decisions" / ("%s.json" % slug)


def read(folder, slug):
    path = path_of(folder, slug)
    if not path.is_file():
        raise CannotLook("no record %s (open it first)" % path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise CannotLook("%s is not JSON (%s)" % (path, e))
    if not isinstance(data, dict):
        raise CannotLook("%s is not an object" % path)
    return data


def write(folder, slug, data):
    path = path_of(folder, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def open_record(folder, slug, question, cancel):
    if path_of(folder, slug).exists():
        return 1, ["decide-first: REFUSED -- %s already exists; a question is opened once" % path_of(folder, slug)]
    if not question or not cancel:
        return 1, ["decide-first: REFUSED -- a question needs both a question and a cancel line"]
    write(folder, slug, {"question": question, "cancel": cancel, "cancel_at": now()})
    return 0, ["decide-first: %s opened. The cancel line is written; measure next." % slug]


def probe(folder, slug, command):
    data = read(folder, slug)
    if "cancel_at" not in data:
        return 1, ["decide-first: REFUSED -- the cancel line is not written; open the question first"]
    if not command:
        return 1, ["decide-first: REFUSED -- a probe needs the command that measures"]
    r = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = (r.stdout + r.stderr)
    cut = len(output) > OUTPUT_LIMIT
    data["probe"] = {"command": command, "exit_code": r.returncode, "output": output[:OUTPUT_LIMIT] + (" [cut]" if cut else ""),
                     "at": now()}
    write(folder, slug, data)
    return 0, ["decide-first: %s probed (exit %d, %d characters kept). Read the output, then decide." %
               (slug, r.returncode, len(output))]


def decide(folder, slug, cancel_met, choice, because):
    data = read(folder, slug)
    if "probe" not in data:
        return 1, ["decide-first: REFUSED -- nothing was measured; probe first"]
    data["cancel_met"] = cancel_met
    data["decision"] = {"choice": choice, "because": because, "at": now()}
    write(folder, slug, data)
    return 0, ["decide-first: %s decided: %s (cancel line met: %s)" % (slug, choice, "yes" if cancel_met else "no")]


def check(folder, slug):
    """(exit code, reasons): empty reasons means the record is in order."""
    data = read(folder, slug)
    reasons = []
    if not str(data.get("question") or "").strip():
        reasons.append("no question is written")
    if not str(data.get("cancel") or "").strip() or "cancel_at" not in data:
        reasons.append("no cancel line is written, or it has no time")
    probe_data = data.get("probe") or {}
    if not probe_data.get("command"):
        reasons.append("nothing was measured: no probe command")
    if BREAK != "no-output" and not str(probe_data.get("output") or "").strip():
        reasons.append("the probe kept no output, so there is nothing to decide from")
    if BREAK != "no-cancel-order" and "cancel_at" in data and probe_data.get("at"):
        try:
            if when(data["cancel_at"]) >= when(probe_data["at"]):
                reasons.append("the cancel line was written at or after the probe, so it was not set before the measuring")
        except (ValueError, TypeError) as e:
            reasons.append("a time does not read (%s)" % e)
    decision = data.get("decision") or {}
    if decision.get("choice") not in CHOICES:
        reasons.append("the decision has no choice, or one that is not %s" % " / ".join(CHOICES))
    if not str(decision.get("because") or "").strip():
        reasons.append("the decision gives no reason")
    if not isinstance(data.get("cancel_met"), bool):
        reasons.append("it is not written whether the cancel line was met")
    elif BREAK != "no-cancel-stop" and data["cancel_met"] and decision.get("choice") != "stop":
        reasons.append("the cancel line was met, and the choice is %r; a met cancel line means stop" % decision.get("choice"))
    if probe_data.get("at") and decision.get("at"):
        try:
            if when(decision["at"]) <= when(probe_data["at"]):
                reasons.append("the decision is not after the measuring")
        except (ValueError, TypeError) as e:
            reasons.append("a time does not read (%s)" % e)
    return (1 if reasons else 0), reasons


# -- the self-test: one record per case in a scratch folder, each verdict expected by name -------------------------------------------

def self_test(quiet=False):
    tmp = Path(tempfile.mkdtemp(prefix="decide_first_"))
    say = (lambda *a: None) if quiet else print
    bad = 0
    try:
        measure = [sys.executable, "-c", "print(40 + 2)"]
        code, _ = open_record(tmp, "base", "Is the parser the slow part?", "The parser takes under 1 ms on the sample")
        code2, _ = probe(tmp, "base", measure)
        code3, _ = decide(tmp, "base", False, "build", "the parser is not the slow part; the disk is")
        base = read(tmp, "base")
        if code or code2 or code3:
            raise CannotLook("the self-test could not write its own base record")

        def case(name, mutate, want):
            data = json.loads(json.dumps(base))
            mutate(data)
            write(tmp, "case", data)
            got, why = check(tmp, "case")
            return name, (got == 0) == (want == "in order"), want, why

        rows = [
            case("a complete record is in order", lambda d: None, "in order"),
            case("a cancel line written after the probe is refused",
                 lambda d: d.update(cancel_at=(when(d["probe"]["at"]) + datetime.timedelta(minutes=5)).isoformat()),
                 "refused"),
            case("a met cancel line with a build choice is refused",
                 lambda d: (d.update(cancel_met=True), d["decision"].update(choice="build")), "refused"),
            case("a probe with no output is refused", lambda d: d["probe"].update(output=""), "refused"),
            case("a decision with no reason is refused", lambda d: d["decision"].update(because=""), "refused"),
        ]
        for name, ok, want, why in rows:
            bad += not ok
            say("  %s %-54s expected %-9s%s" % ("ok " if ok else "RED", name, want, ("  (" + why[0] + ")") if why else ""))
        return len(rows), bad
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    global BREAK
    ap = argparse.ArgumentParser(description="a design question gets a measured decision before any code")
    argv = list(sys.argv[1:] if argv is None else argv)
    command = []
    if "--" in argv:  # everything after -- is the probe's command, never read as an option of this script
        cut = argv.index("--")
        argv, command = argv[:cut], argv[cut + 1:]
    ap.add_argument("mode", nargs="?", choices=["open", "probe", "decide", "check"])
    ap.add_argument("slug", nargs="?", help="the question's short name, used as the record's file name")
    ap.add_argument("--question", default="")
    ap.add_argument("--cancel", default="", help="the result that would make the answer no")
    ap.add_argument("--cancel-met", choices=["yes", "no"])
    ap.add_argument("--choice", choices=CHOICES)
    ap.add_argument("--because", default="")
    ap.add_argument("--folder", default=None, help="where decisions/ lives (default: the current folder)")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--break", dest="brk", choices=BREAKS)
    a = ap.parse_args(argv)
    BREAK = a.brk
    if a.self_test:
        n, bad = self_test()
        print("decide-first self-test %s -- %d case(s), %d not as expected%s"
              % ("RED" if bad else "GREEN", n, bad, " (break %s)" % BREAK if BREAK else ""))
        return 1 if bad else 0
    if a.mode is None or not a.slug:
        ap.print_help()
        return 2
    _, bad = self_test(quiet=True)
    if bad:
        print("decide-first RED -- its own self-test has %d case(s) not as expected, so it cannot be trusted to refuse" % bad)
        return 1
    folder = Path(a.folder) if a.folder else Path.cwd()
    try:
        if a.mode == "open":
            code, lines = open_record(folder, a.slug, a.question, a.cancel)
        elif a.mode == "probe":
            code, lines = probe(folder, a.slug, command)
        elif a.mode == "decide":
            if a.cancel_met is None or a.choice is None:
                print("decide-first: decide needs --cancel-met yes|no and --choice build|stop|other")
                return 2
            code, lines = decide(folder, a.slug, a.cancel_met == "yes", a.choice, a.because)
        else:
            code, reasons = check(folder, a.slug)
            lines = (["decide-first: %s in order" % a.slug] if not reasons else
                     ["decide-first: %s REFUSED -- %d reason(s)" % (a.slug, len(reasons))] + ["  - " + r for r in reasons])
    except CannotLook as e:
        print("decide-first could not look: %s" % e)
        return REFUSED_CODE
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
