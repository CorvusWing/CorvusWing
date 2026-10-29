#!/usr/bin/env python3
"""decide_first.py -- a design question gets a small, measured decision before any code is written.

WHY. A design question ("should the cache be per user or shared?", "is the slow part the parser or the disk?")
is easy to answer with a plausible story and expensive to answer with code. This script makes the order fixed:

    1. open     write the question, and the condition that would make the answer "no" (the cancel line),
                BEFORE anything is measured;
    2. probe    run the smallest measurement that could show the cancel line is met, and keep its output;
                a second probe is kept beside the first, never in its place, and must say why it was run;
    3. decide   read the output, say whether the cancel line was met, and make the choice with its reason.

A record that breaks that order, decides from a crashed measurement without saying why that is acceptable, or
picks anything but "stop" after the cancel line was met, is refused in words. Only then is code written, and
the record is what the code's commit message points at.

Each step stores its time and a sequence number. The order is read from the sequence numbers, so two steps
inside one tick of a coarse clock still read in order; the times must not run backwards.

USAGE (the record is decisions/<name>.json in the current folder; a name is lowercase letters, digits, '.', '_'
and '-', starting with a letter or digit)
    python3 decide_first.py open <name> --question TEXT --cancel TEXT
    python3 decide_first.py probe <name> [--rerun-because TEXT] -- <command and its arguments>
    python3 decide_first.py decide <name> --cancel-met yes|no --choice build|stop|other --because TEXT
                                          [--probe-failed-ok TEXT]
    python3 decide_first.py check <name>               exit 0 when the record is in order, 1 when refused
    python3 decide_first.py --self-test [--break NAME]  a scratch folder with one row per case; each break
                                                        switches one rule off, and only its own row may turn RED

Exit codes: 0 in order (or recorded), 1 refused, 2 bad use of the command, 78 a record cannot be read or
written, or the probe's program cannot be started.
"""
import argparse
import datetime
import hashlib
import itertools
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

TOOL = "decide-first"  # the name this script signs its words with
REFUSED_CODE = 78
OUTPUT_LIMIT = 4000  # characters of probe output kept in the record; the rest is cut and marked
CHOICES = ("build", "stop", "other")
NAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
NOWIN = 0x08000000 if os.name == "nt" else 0
PLACEHOLDERS = {"n/a", "na", "none", "nothing", "tbd", "todo", "wip", "fix", "fixed", "ok", "yes", "no", "same",
                "see above", "as above", "because", "measured", "x", ""}
MIN_WORDS = 3  # a reason says what was seen and what follows from it; under three words it cannot
BREAKS = ("no-cancel-order", "no-cancel-stop", "no-output", "no-reason", "no-placeholder-check", "no-probe-check",
          "no-decision-order", "no-exit-check", "no-rerun-check", "no-probe-after-decision", "no-decide-once",
          "no-name-check", "no-seq")
BREAK = None


class CannotLook(Exception):
    """The record cannot be read or written, or the probe cannot start; its words go out with exit 78."""


def now():
    return datetime.datetime.now().astimezone().isoformat()


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


def name_problem(name):
    if BREAK != "no-name-check" and not NAME.match(str(name or "")):
        return ("decide-first: REFUSED -- %r is not a record name: use lowercase letters, digits, '.', '_' and '-', "
                "starting with a letter or digit" % name)
    return None


def path_of(folder, name):
    return Path(folder) / "decisions" / ("%s.json" % name)


def read(folder, name):
    path = path_of(folder, name)
    if not path.is_file():
        raise CannotLook("no record %s (open it first)" % path)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        raise CannotLook("%s cannot be read as JSON (%s)" % (path, e))
    if not isinstance(data, dict):
        raise CannotLook("%s is not an object" % path)
    return data


def write(folder, name, data):
    """Writes the whole record to a temporary file first, then puts it in place, so a crash never leaves half a record."""
    path = path_of(folder, name)
    spare = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(spare), "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        os.replace(str(spare), str(path))
    except OSError as e:
        raise CannotLook("%s cannot be written (%s)" % (path, e))


def probes_of(data):
    probes = data.get("probes")
    return [p for p in probes if isinstance(p, dict)] if isinstance(probes, list) else []


def next_seq(data):
    seqs = [data.get("cancel_seq") or 0] + [p.get("seq") or 0 for p in probes_of(data)]
    if isinstance(data.get("decision"), dict):
        seqs.append(data["decision"].get("seq") or 0)
    return max(s for s in seqs if isinstance(s, int)) + 1


def after(first, second):
    """True when the second step came after the first: (sequence number, time) pairs. The sequence decides the
    order; the time only must not run backwards. A step stored without a sequence number is ordered by time."""
    (s1, t1), (s2, t2) = first, second
    if BREAK == "no-seq" or not isinstance(s1, int) or not isinstance(s2, int):
        return when(t2) > when(t1)
    return s2 > s1 and when(t2) >= when(t1)


def rerun_problem(index, reason):
    """Why the probe at this position (0 is the first) may not be kept, or None. Only a second run needs a reason."""
    if index == 0 or BREAK == "no-rerun-check":
        return None
    problem = reason_problem(reason)
    if problem:
        return ("probe %d is a second run, and its reason (--rerun-because) %s; the first run is kept, and a rerun must "
                "say what was wrong with it" % (index + 1, problem))
    return None


def reasons_for(data, complete=True):
    """Every reason the record is out of order, in words. complete=False reads a record that is not decided yet."""
    reasons = []
    if not words(data.get("question")):
        reasons.append("no question is written")
    if not words(data.get("cancel")) or "cancel_at" not in data:
        reasons.append("no cancel line is written, or it has no time")
    probes = probes_of(data)
    decision = data.get("decision") if isinstance(data.get("decision"), dict) else {}
    try:
        if not probes:
            if complete and BREAK != "no-probe-check":
                reasons.append("nothing was measured: no probe is kept")
        else:
            first, last = probes[0], probes[-1]
            if BREAK != "no-output" and not words(last.get("output")):
                reasons.append("the probe kept no output, so there is nothing to decide from")
            for i, p in enumerate(probes):
                problem = rerun_problem(i, p.get("rerun_because"))
                if problem:
                    reasons.append(problem)
            if (BREAK != "no-cancel-order" and "cancel_at" in data
                    and not after((data.get("cancel_seq"), data["cancel_at"]), (first.get("seq"), first.get("at")))):
                reasons.append("the cancel line was not written before the first probe, so it was not set before the "
                               "measuring")
            if decision:
                if BREAK != "no-decision-order" and not after((last.get("seq"), last.get("at")),
                                                              (decision.get("seq"), decision.get("at"))):
                    reasons.append("the decision is not after the measuring")
                if (BREAK != "no-exit-check" and last.get("exit_code") != 0
                        and (not words(decision.get("probe_failed_ok"))
                             or reason_problem(decision.get("probe_failed_ok")))):
                    reasons.append("the probe the decision reads exited %s; a crashed measurement is not a result, "
                                   "unless the decision says why this exit is acceptable (--probe-failed-ok)"
                                   % last.get("exit_code"))
    except (ValueError, TypeError) as e:
        reasons.append("a time does not read (%s)" % e)
    if not complete:
        return reasons
    if decision.get("choice") not in CHOICES:
        reasons.append("the decision has no choice, or one that is not %s" % " / ".join(CHOICES))
    because = decision.get("because")
    if BREAK != "no-reason" or words(because):
        problem = reason_problem(because)
        if problem:
            reasons.append("the decision's reason %s" % problem)
    if not isinstance(data.get("cancel_met"), bool):
        reasons.append("it is not written whether the cancel line was met")
    elif BREAK != "no-cancel-stop" and data["cancel_met"] and decision.get("choice") != "stop":
        reasons.append("the cancel line was met, and the choice is %r; a met cancel line means stop (a different "
                       "question is a new record, with its own cancel line)" % decision.get("choice"))
    return reasons


def open_record(folder, name, question, cancel):
    refused = name_problem(name)
    if refused:
        return 1, [refused]
    if path_of(folder, name).exists():
        return 1, ["decide-first: REFUSED -- %s already exists; a question is opened once" % path_of(folder, name)]
    if not words(question) or not words(cancel):
        return 1, ["decide-first: REFUSED -- a question needs both a question and a cancel line"]
    write(folder, name, {"question": words(question), "cancel": words(cancel), "cancel_at": now(), "cancel_seq": 1,
                         "probes": []})
    return 0, ["decide-first: %s opened. The cancel line is written; measure next." % name]


def program(command):
    """On Windows a program named without its extension (npm, pytest) is found the way the shell would find it."""
    if os.name == "nt" and command:
        found = shutil.which(command[0])
        if found:
            return [found] + list(command[1:])
    return list(command)


def probe(folder, name, command, rerun_because=""):
    refused = name_problem(name)
    if refused:
        return 1, [refused]
    data = read(folder, name)
    if "cancel_at" not in data:
        return 1, ["decide-first: REFUSED -- the cancel line is not written; open the question first"]
    if isinstance(data.get("decision"), dict) and data["decision"] and BREAK != "no-probe-after-decision":
        return 1, ["decide-first: REFUSED -- %s is already decided; a probe after the decision cannot change it. Open a "
                   "new question if there is one." % name]
    probes = probes_of(data)
    problem = rerun_problem(len(probes), rerun_because)
    if problem:
        return 1, ["decide-first: REFUSED -- %s" % problem]
    if not command:
        return 2, ["decide-first: a probe needs the command that measures, after --"]
    try:
        r = subprocess.run(program(command), capture_output=True, creationflags=NOWIN)
    except OSError as e:
        raise CannotLook("the probe's program %r could not be started (%s); nothing was recorded" % (command[0], e))
    output = r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")
    cut = len(output) > OUTPUT_LIMIT
    probes.append({"seq": next_seq(data), "at": now(), "command": list(command), "exit_code": r.returncode,
                   "output": output[:OUTPUT_LIMIT] + (" [cut]" if cut else ""), "rerun_because": words(rerun_because) or None})
    data["probes"] = probes
    write(folder, name, data)
    lines = ["decide-first: %s probed (probe %d, exit %d, %d characters kept). Read the output, then decide."
             % (name, len(probes), r.returncode, min(len(output), OUTPUT_LIMIT))]
    if r.returncode != 0:
        lines.append("decide-first: the probe exited %d. A crashed measurement is not a result: fix the probe and run it "
                     "again with --rerun-because, or, if this exit is the measurement, say why at the decision with "
                     "--probe-failed-ok." % r.returncode)
    return 0, lines


def decide(folder, name, cancel_met, choice, because, probe_failed_ok=""):
    refused = name_problem(name)
    if refused:
        return 1, [refused]
    data = read(folder, name)
    if isinstance(data.get("decision"), dict) and data["decision"] and BREAK != "no-decide-once":
        return 1, ["decide-first: REFUSED -- %s is already decided; a decision is written once. Open a new question to "
                   "decide again." % name]
    data["cancel_met"] = cancel_met
    data["decision"] = {"seq": next_seq(data), "at": now(), "choice": choice, "because": words(because),
                        "probe_failed_ok": words(probe_failed_ok) or None}
    reasons = reasons_for(data, complete=True)
    if reasons:
        return 1, ["decide-first: REFUSED -- the decision was not written; the record would be out of order:"] + \
            ["  - " + r for r in reasons]
    write(folder, name, data)
    return 0, ["decide-first: %s decided: %s (cancel line met: %s)" % (name, choice, "yes" if cancel_met else "no")]


def check(folder, name):
    """(exit code, reasons): empty reasons means the record is in order."""
    refused = name_problem(name)
    if refused:
        return 1, [refused]
    reasons = reasons_for(read(folder, name), complete=True)
    return (1 if reasons else 0), reasons


# -- cleanup and the self-test's cache -----------------------------------------------------------------------------------------

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


def proven():
    """0 when this exact script, on this Python, has passed its self-test; runs it when not yet known."""
    seed = Path(__file__).read_bytes() + ("|%s" % sys.version).encode()
    mark = Path(tempfile.gettempdir()) / ("corvuswing-decide-first-%s.green" % hashlib.sha256(seed).hexdigest()[:20])
    if mark.is_file():
        return 0
    _, bad = self_test(quiet=True)
    if not bad:
        try:
            mark.write_bytes(b"")
        except OSError:
            pass
    return bad


# -- the self-test: one record per case in a scratch folder, on a fixed clock, each verdict expected by name -----------------------

FIXED = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)


def self_test(quiet=False):
    global now
    real_now = now
    minutes = itertools.count()
    now = lambda: (FIXED + datetime.timedelta(minutes=next(minutes))).isoformat()  # noqa: E731 -- each step a minute apart
    tmp = Path(tempfile.mkdtemp(prefix="decide_first_"))
    say = (lambda *a: None) if quiet else print
    rows = []
    try:
        measure = [sys.executable, "-c", "print(40 + 2)"]
        steps = [open_record(tmp, "base", "Is the parser the slow part?", "The parser takes under 1 ms on the sample"),
                 probe(tmp, "base", measure),
                 decide(tmp, "base", False, "build", "the parser is not the slow part; the disk is")]
        if any(code for code, _ in steps):
            raise CannotLook("the self-test could not write its own base record: %s"
                             % "; ".join(line for _, lines in steps for line in lines))
        base = read(tmp, "base")

        def record(name, mutate):
            data = json.loads(json.dumps(base))
            mutate(data)
            write(tmp, name, data)
            return name

        def verdict(name, mutate, want, expect_text=""):
            code, why = check(tmp, record("case", mutate))
            ok = (code == 0) if want == "in order" else (code == 1 and any(expect_text in r for r in why))
            rows.append((name, ok, "expected %s, got %s" % (want, ("refused: " + why[0][:70]) if why else "in order")))

        def refused_step(name, code_lines, extra_ok=True):
            code, lines = code_lines
            ok = code == 1 and extra_ok
            rows.append((name, ok, "expected a refusal, got exit %d: %s" % (code, lines[0][:70])))

        probe_at = base["probes"][0]["at"]
        verdict("a complete record is in order", lambda d: None, "in order")
        verdict("a cancel line written after the probe is refused",
                lambda d: d.update(cancel_seq=99, cancel_at=(when(probe_at) + datetime.timedelta(minutes=5)).isoformat()),
                "refused", "cancel line was not written before")
        verdict("a met cancel line with a build choice is refused",
                lambda d: (d.update(cancel_met=True), d["decision"].update(choice="build")), "refused", "means stop")
        verdict("a probe with no output is refused", lambda d: d["probes"][0].update(output=""), "refused", "no output")
        verdict("a decision with no reason is refused", lambda d: d["decision"].update(because=""), "refused",
                "reason is empty")
        verdict("a placeholder reason is refused", lambda d: d["decision"].update(because="n/a"), "refused", "placeholder")
        verdict("a record with nothing measured is refused", lambda d: d.update(probes=[]), "refused", "nothing was measured")
        verdict("a decision made before the measuring is refused",
                lambda d: d["decision"].update(seq=0, at=(when(d["cancel_at"]) - datetime.timedelta(minutes=1)).isoformat()),
                "refused", "not after the measuring")
        verdict("a crashed probe with no written why is refused", lambda d: d["probes"][0].update(exit_code=1),
                "refused", "crashed measurement")
        verdict("a crashed probe with a written why is in order",
                lambda d: (d["probes"][0].update(exit_code=1),
                           d["decision"].update(probe_failed_ok="the probe exits 1 by design when the cancel line is met")),
                "in order")
        verdict("events in one clock tick read in order by their sequence",
                lambda d: (d.update(cancel_at=probe_at), d["decision"].update(at=probe_at)), "in order")

        open_record(tmp, "rerun", "Is the cache worth it?", "The hit rate is under 50% on the sample")
        probe(tmp, "rerun", [sys.executable, "-c", "print('hit rate 31%')"])
        refused_step("a second probe with no reason is refused",
                     probe(tmp, "rerun", [sys.executable, "-c", "print('hit rate 97%')"]),
                     len(probes_of(read(tmp, "rerun"))) == 1)
        record("late", lambda d: None)
        refused_step("a probe after the decision is refused",
                     probe(tmp, "late", measure, rerun_because="checking again after the library upgrade"))
        record("again", lambda d: None)
        refused_step("a second decision is refused",
                     decide(tmp, "again", False, "other", "split the question into the parser half and the disk half"))
        escaped = tmp / "escaped.json"
        refused_step("a record name that leaves decisions/ is refused",
                     open_record(tmp, "../escaped", "q", "c"), not escaped.exists())
        open_record(tmp, "noprog", "Is the parser slow?", "The parser takes under 1 ms")
        try:
            probe(tmp, "noprog", ["no-such-program-for-decide-first"])
            rows.append(("a probe whose program does not exist is refused in words", False, "it was recorded"))
        except CannotLook as e:
            rows.append(("a probe whose program does not exist is refused in words", True, "refused: %s" % str(e)[:60]))

        for name, ok, detail in rows:
            say("  %s  %s -- %s" % ("ok " if ok else "RED", name, detail))
        return len(rows), sum(1 for _, ok, _ in rows if not ok)
    finally:
        now = real_now
        remove_tree(tmp)


def main(argv=None):
    global BREAK
    argv = list(sys.argv[1:] if argv is None else argv)
    command = []
    if "--" in argv:  # everything after -- is the probe's command, never read as an option of this script
        cut = argv.index("--")
        argv, command = argv[:cut], argv[cut + 1:]
    ap = argparse.ArgumentParser(description="a design question gets a measured decision before any code")
    ap.add_argument("mode", nargs="?", choices=["open", "probe", "decide", "check"])
    ap.add_argument("name", nargs="?", help="the record's name, as in decisions/<name>.json")
    ap.add_argument("--question", default="")
    ap.add_argument("--cancel", default="", help="the result that would make the answer no")
    ap.add_argument("--cancel-met", choices=["yes", "no"])
    ap.add_argument("--choice", choices=CHOICES)
    ap.add_argument("--because", default="")
    ap.add_argument("--probe-failed-ok", default="", help="why a probe that exited non-zero is still the measurement")
    ap.add_argument("--rerun-because", default="", help="why a second probe is run; the first is kept")
    ap.add_argument("--folder", default=None, help="where decisions/ lives (default: the current folder)")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--break", dest="brk", choices=BREAKS, help="with --self-test only: switch one rule off")
    a = ap.parse_args(argv)
    if a.brk and not a.self_test:
        print("decide-first: --break goes with --self-test only; a real record is never checked with a rule switched off")
        return 2
    BREAK = a.brk
    try:
        if a.self_test:
            n, bad = self_test()
            print("decide-first self-test %s -- %d case(s), %d not as expected%s"
                  % ("RED" if bad else "GREEN", n, bad, " (break %s)" % BREAK if BREAK else ""))
            return 1 if bad else 0
        if a.mode is None or not a.name:
            ap.print_help()
            return 2
        bad = proven()
        if bad:
            print("decide-first RED -- its own self-test has %d case(s) not as expected, so it cannot be trusted to refuse; "
                  "run --self-test to read them" % bad)
            return 1
        folder = Path(a.folder) if a.folder else Path.cwd()
        if a.mode == "open":
            code, lines = open_record(folder, a.name, a.question, a.cancel)
        elif a.mode == "probe":
            code, lines = probe(folder, a.name, command, a.rerun_because)
        elif a.mode == "decide":
            if a.cancel_met is None or a.choice is None:
                print("decide-first: decide needs --cancel-met yes|no and --choice build|stop|other")
                return 2
            code, lines = decide(folder, a.name, a.cancel_met == "yes", a.choice, a.because, a.probe_failed_ok)
        else:
            code, reasons = check(folder, a.name)
            lines = (["decide-first: %s in order" % a.name] if not reasons else
                     ["decide-first: %s REFUSED -- %d reason(s)" % (a.name, len(reasons))] + ["  - " + r for r in reasons])
    except CannotLook as e:
        print("decide-first could not look: %s" % e)
        return REFUSED_CODE
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
