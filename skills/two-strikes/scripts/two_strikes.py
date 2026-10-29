#!/usr/bin/env python3
"""two_strikes.py -- a check that fails twice in a row stops the step, which is reported instead of tried a third time.

WHY. An agent that hits the same failure will often try again, and again, each try a small variation on
the last. That loop spends time and money, and it rarely gets anywhere the second try could not have
reached alone. This script keeps a ledger of each check's failures and passes. The second failure in a row
of the same check prints STOP AND REPORT, so the run that called it can stop and hand the failure to a
person.

The ledger is a JSON-lines file (strikes.jsonl in the current folder, or the path given with --ledger): one
entry per line, only ever appended, so two writers cannot overwrite each other and nothing is lost. A pass
ends a check's run of failures; so does a reset, written by a person once the cause is fixed.

Check names are compared without regard to case or spaces, so "Unit tests: parser" and "unit tests:parser"
are one check.

USAGE
    python3 two_strikes.py strike "<check>" [--note TEXT]   one failure: exit 0 for the first, 3 at the second (STOP)
    python3 two_strikes.py pass "<check>" [--note TEXT]     the check passed: its run of failures ends
    python3 two_strikes.py run "<check>" -- <command ...>   runs the command and records pass or strike itself;
                                                            refuses to run a check that is already stopped
    python3 two_strikes.py reset "<check>" [--note TEXT]    a person's word that the cause is fixed: count from zero
    python3 two_strikes.py ledger                           every check and its failures in a row; exit 3 if one is stopped
    python3 two_strikes.py --self-test [--break NAME]       a scratch ledger with one row per case; each break
                                                            switches one rule off, and only its own row may turn RED
    Every command takes --ledger PATH.

Exit codes: 0 fine; 1 run's command failed (a first strike); 2 bad use (no check name, no command);
3 STOP (a second failure in a row, or a stopped check that run refused); 78 the ledger cannot be read or
written, or run's command cannot be started (nothing is recorded then).
"""
import argparse
import contextlib
import datetime
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REFUSED_CODE = 78  # the ledger cannot be read or written, or the command cannot be started
FAILED, BAD_USE, STOPPED = 1, 2, 3
STOP_AT = 2
KINDS = ("strike", "pass", "reset")
DEFAULT_LEDGER = "strikes.jsonl"
LOCK_WAIT, STALE_LOCK = 10.0, 30.0  # seconds: how long a writer waits for the ledger, and when a left lock is stale
NOWIN = 0x08000000 if os.name == "nt" else 0
BREAKS = ("no-stop", "no-ledger-stop", "no-count-by-check", "no-reset", "no-pass", "no-normalize", "no-name-check",
          "no-run-refusal", "no-bom")
BREAK = None


class CannotLook(Exception):
    """The ledger cannot be read or written, or a command cannot start; its words go out with exit 78."""


def display(name):
    return " ".join(str(name or "").split())


def key_of(name):
    """The one definition of 'the same check': case and spaces do not count."""
    if BREAK == "no-normalize":
        return str(name)
    return "".join(str(name or "").split()).casefold()


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def load(path):
    path = Path(path)
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8" if BREAK == "no-bom" else "utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        raise CannotLook("the ledger %s cannot be read (%s)" % (path, e))
    entries = []
    for number, line in enumerate(text.splitlines(), 1):
        if BREAK != "no-bom":
            line = line.lstrip("﻿")
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError as e:
            raise CannotLook("the ledger %s, line %d, is not an entry (%s); fix or remove that line by hand" % (path, number, e))
        if not isinstance(entry, dict) or entry.get("kind") not in KINDS:
            raise CannotLook("the ledger %s, line %d, is not a strike, pass or reset" % (path, number))
        entries.append(entry)
    return entries


@contextlib.contextmanager
def ledger_lock(path):
    """A short lock beside the ledger, so two writers at the same instant take turns (an append alone is not
    atomic across processes on Windows). A lock left by a crashed writer is cleared after STALE_LOCK seconds."""
    lock = Path(str(path) + ".lock")
    deadline = time.monotonic() + LOCK_WAIT
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except (FileExistsError, PermissionError):
            try:
                if time.time() - lock.stat().st_mtime > STALE_LOCK:
                    lock.unlink()
                    continue
            except OSError:
                pass
            if time.monotonic() > deadline:
                raise CannotLook("the ledger's lock %s has been held for %d s; if no other strike is being written, "
                                 "remove it" % (lock, LOCK_WAIT))
            time.sleep(0.02)
    try:
        yield
    finally:
        os.close(fd)
        try:
            lock.unlink()
        except OSError:
            pass


def append(path, kind, check, note):
    path = Path(path)
    line = json.dumps({"kind": kind, "check": display(check), "note": note or "", "at": now()}, ensure_ascii=False)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_lock(path):
            ends_open = False
            if path.is_file() and path.stat().st_size:
                with open(str(path), "rb") as f:
                    f.seek(-1, os.SEEK_END)
                    ends_open = f.read(1) != b"\n"
            with open(str(path), "a", encoding="utf-8", newline="\n") as f:
                f.write(("\n" if ends_open else "") + line + "\n")
    except OSError as e:
        raise CannotLook("the ledger %s cannot be written (%s)" % (path, e))


def in_a_row(entries, check):
    """Failures of this check since its last pass or reset."""
    k, n = key_of(check), 0
    for e in entries:
        if BREAK != "no-count-by-check" and key_of(e.get("check")) != k:
            continue
        kind = e.get("kind")
        if (kind == "reset" and BREAK != "no-reset") or (kind == "pass" and BREAK != "no-pass"):
            n = 0
        elif kind == "strike":
            n += 1
    return n


def unnamed(check, what):
    if BREAK != "no-name-check" and not display(check):
        return BAD_USE, ["two-strikes: REFUSED -- %s must name the check; an unnamed entry counts nothing" % what]
    return None


def strike(path, check, note=""):
    """(exit code, lines) for one recorded failure."""
    refused = unnamed(check, "a strike")
    if refused:
        return refused
    n = in_a_row(load(path), check) + 1
    append(path, "strike", check, note)
    if n >= STOP_AT and BREAK != "no-stop":
        return STOPPED, ["two-strikes: STOP AND REPORT -- %r has failed %d times in a row, with no pass or reset between. "
                         "Do not try again. Write down what was tried, the failing output and the likely cause, then "
                         "hand it to a person." % (display(check), n)]
    return 0, ["two-strikes: %r -- strike %d of %d recorded. One more failure in a row stops the step."
               % (display(check), n, STOP_AT)]


def passed(path, check, note=""):
    refused = unnamed(check, "a pass")
    if refused:
        return refused
    append(path, "pass", check, note)
    return 0, ["two-strikes: %r passed; its run of failures ends" % display(check)]


def reset(path, check, note=""):
    refused = unnamed(check, "a reset")
    if refused:
        return refused
    append(path, "reset", check, note)
    return 0, ["two-strikes: %r -- count reset by a person; the next failure is strike 1 of %d" % (display(check), STOP_AT)]


def program(command):
    """On Windows a command named without its extension (npm, pytest) is found the way the shell would find it."""
    if os.name == "nt" and command:
        found = shutil.which(command[0])
        if found:
            return [found] + list(command[1:])
    return list(command)


def run(path, check, command, note="", echo=None):
    """Runs the command; its exit code becomes a pass or a strike. A stopped check is refused and not run."""
    refused = unnamed(check, "run")
    if refused:
        return refused
    if not command:
        return BAD_USE, ["two-strikes: REFUSED -- run needs the command after --"]
    n = in_a_row(load(path), check)
    if n >= STOP_AT and BREAK != "no-run-refusal":
        return STOPPED, ["two-strikes: REFUSED -- %r is stopped (%d failures in a row), so the command was not run. "
                         "Report it to a person; their reset starts a fresh count." % (display(check), n)]
    echo = echo or (lambda chunk: (sys.stdout.buffer.write(chunk), sys.stdout.flush()))
    try:
        proc = subprocess.Popen(program(command), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=NOWIN)
    except OSError as e:
        raise CannotLook("the command %r could not be started (%s); nothing was recorded" % (command[0], e))
    for chunk in iter(lambda: proc.stdout.read1(65536), b""):
        echo(chunk)
    proc.stdout.close()
    code = proc.wait()
    if code == 0:
        return passed(path, check, note or "run: exit 0")
    rc, lines = strike(path, check, note or "run: exit %d" % code)
    return (rc if rc else FAILED), ["two-strikes: the command exited %d." % code] + lines


def ledger(path):
    """(exit code, lines): every check's failures in a row; exit 3 if any is stopped."""
    entries = load(path)
    names = {}
    for e in entries:
        names[key_of(e.get("check"))] = display(e.get("check"))
    width = max([len(v) for v in names.values()] + [10])
    lines = ["two-strikes ledger: %d entr(ies), %d check(s)" % (len(entries), len(names))]
    stopped = False
    for k in sorted(names):
        n = in_a_row(entries, names[k])
        if n >= STOP_AT and BREAK != "no-ledger-stop":
            stopped = True
            status = "STOP -- report it, do not try again"
        else:
            status = "one more failure stops it" if n >= STOP_AT - 1 else "no failures since its last pass or reset"
        lines.append("  %-*s  %d in a row  %s" % (width, names[k], n, status))
    return (STOPPED if stopped else 0), lines


# -- cleanup and the self-test's cache ---------------------------------------------------------------------------------------

def remove_tree(path):
    """Removes a scratch folder; a read-only item has that flag cleared and is tried once more, and anything that
    still will not go is said out loud."""
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
        sys.stderr.write("two-strikes: cleanup could not remove %d item(s) of the scratch folder %s; the first: %s\n"
                         % (len(failed), path, failed[0]))


def proven():
    """0 when this exact script, on this Python, has passed its self-test; runs it when not yet known."""
    seed = Path(__file__).read_bytes() + ("|%s" % sys.version).encode()
    mark = Path(tempfile.gettempdir()) / ("corvuswing-two-strikes-%s.green" % hashlib.sha256(seed).hexdigest()[:20])
    if mark.is_file():
        return 0
    _, bad = self_test(quiet=True)
    if not bad:
        try:
            mark.write_bytes(b"")
        except OSError:
            pass
    return bad


# -- the self-test: one scratch ledger per case, each checked by name ------------------------------------------------------------

def self_test(quiet=False):
    tmp = Path(tempfile.mkdtemp(prefix="two_strikes_"))
    say = (lambda *a: None) if quiet else print
    rows = []
    quiet_echo = lambda chunk: None  # noqa: E731
    py = [sys.executable, "-c"]
    try:
        def fresh(name):
            return tmp / ("%s.jsonl" % name)

        def case(name, body):
            try:
                ok, detail = body()
            except CannotLook as e:
                ok, detail = False, "could not look: %s" % e
            rows.append((name, ok, detail))

        def first():
            code, lines = strike(fresh("first"), "build the parser")
            return code == 0 and "1 of 2" in lines[0], "exit %d: %s" % (code, lines[0][:60])

        def second():
            led = fresh("second")
            strike(led, "build the parser")
            code, lines = strike(led, "build the parser")
            return code == STOPPED and "STOP AND REPORT" in lines[0], "exit %d: %s" % (code, lines[0][:60])

        def listed():
            led = fresh("listed")
            strike(led, "build the parser")
            strike(led, "build the parser")
            code, lines = ledger(led)
            return code == STOPPED and any("STOP" in line for line in lines[1:]), "exit %d" % code

        def own_count():
            led = fresh("own")
            strike(led, "build the parser")
            code, lines = strike(led, "run the import")
            return code == 0 and "1 of 2" in lines[0], "exit %d: %s" % (code, lines[0][:60])

        def after_reset():
            led = fresh("reset")
            strike(led, "build the parser")
            reset(led, "build the parser", "the missing fixture was added")
            code, lines = strike(led, "build the parser")
            return code == 0 and "1 of 2" in lines[0], "exit %d: %s" % (code, lines[0][:60])

        def after_pass():
            led = fresh("pass")
            strike(led, "build the parser")
            passed(led, "build the parser")
            code, lines = strike(led, "build the parser")
            return code == 0 and "1 of 2" in lines[0], "exit %d: %s" % (code, lines[0][:60])

        def same_name():
            led = fresh("names")
            strike(led, "Unit tests: parser")
            strike(led, "unit  tests:parser ")
            n = in_a_row(load(led), "unit tests: parser")
            return n == 2, "%d failure(s) in a row counted" % n

        def no_name():
            code, lines = strike(fresh("unnamed"), "")
            return code == BAD_USE and "REFUSED" in lines[0], "exit %d" % code

        def run_pass():
            led = fresh("run-pass")
            code, _ = run(led, "the import", py + ["raise SystemExit(0)"], echo=quiet_echo)
            kinds = [e["kind"] for e in load(led)]
            return code == 0 and kinds == ["pass"], "exit %d, entries %s" % (code, kinds)

        def run_fail():
            led = fresh("run-fail")
            code, _ = run(led, "the import", py + ["raise SystemExit(4)"], echo=quiet_echo)
            kinds = [e["kind"] for e in load(led)]
            return code == FAILED and kinds == ["strike"], "exit %d, entries %s" % (code, kinds)

        def run_refused():
            led, marker = fresh("run-stopped"), tmp / "ran.txt"
            strike(led, "the import")
            strike(led, "the import")
            code, _ = run(led, "the import", py + ["import pathlib, sys; pathlib.Path(sys.argv[1]).touch()", str(marker)],
                          echo=quiet_echo)
            return code == STOPPED and not marker.exists(), "exit %d, the command ran: %s" % (code, marker.exists())

        def bom():
            led = fresh("bom")
            led.write_bytes(b"\xef\xbb\xbf" + json.dumps({"kind": "strike", "check": "lint", "at": "x"}).encode() + b"\n")
            n = in_a_row(load(led), "lint")
            return n == 1, "%d failure(s) read" % n

        def broken():
            led = fresh("broken")
            led.write_bytes(b"not an entry\n")
            try:
                load(led)
                return False, "read without a refusal"
            except CannotLook as e:
                return True, "refused: %s" % str(e)[-50:]

        for name, body in (("a first failure is counted, not stopped", first),
                           ("a second failure in a row stops and reports", second),
                           ("the ledger shows the stopped check", listed),
                           ("a failure of another check starts its own count", own_count),
                           ("a reset starts the count again", after_reset),
                           ("a pass ends the run of failures", after_pass),
                           ("names that differ only in case and spaces are one check", same_name),
                           ("an unnamed strike is refused in words", no_name),
                           ("run records a pass for a command that exits 0", run_pass),
                           ("run records a strike for a command that fails", run_fail),
                           ("run refuses to run a stopped check", run_refused),
                           ("a ledger saved with a byte-order mark reads", bom),
                           ("a ledger line that is not an entry is refused in words", broken)):
            case(name, body)
        for name, ok, detail in rows:
            say("  %s  %s -- %s" % ("ok " if ok else "RED", name, detail))
        return len(rows), sum(1 for _, ok, _ in rows if not ok)
    finally:
        remove_tree(tmp)


def main(argv=None):
    global BREAK
    argv = list(sys.argv[1:] if argv is None else argv)
    command = []
    if "--" in argv:  # everything after -- is run's command, never read as an option of this script
        cut = argv.index("--")
        argv, command = argv[:cut], argv[cut + 1:]
    ap = argparse.ArgumentParser(description="a check that fails twice in a row stops the step")
    ap.add_argument("mode", nargs="?", choices=["strike", "pass", "run", "reset", "ledger"])
    ap.add_argument("check_name", nargs="?", help="the check, for strike, pass, run and reset")
    ap.add_argument("--note", default="", help="what happened, in words")
    ap.add_argument("--ledger", default=None, help="the ledger file (default: %s in the current folder)" % DEFAULT_LEDGER)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--break", dest="brk", choices=BREAKS, help="with --self-test only: switch one rule off")
    a = ap.parse_args(argv)
    if a.brk and not a.self_test:
        print("two-strikes: --break goes with --self-test only; a real count never runs with a rule switched off")
        return BAD_USE
    BREAK = a.brk
    try:
        if a.self_test:
            n, bad = self_test()
            print("two-strikes self-test %s -- %d case(s), %d not as expected%s"
                  % ("RED" if bad else "GREEN", n, bad, " (break %s)" % BREAK if BREAK else ""))
            return 1 if bad else 0
        if a.mode is None:
            ap.print_help()
            return BAD_USE
        bad = proven()
        if bad:
            print("two-strikes RED -- its own self-test has %d case(s) not as expected, so it cannot be trusted to stop "
                  "a loop; run --self-test to read them" % bad)
            return 1
        path = Path(a.ledger) if a.ledger else Path.cwd() / DEFAULT_LEDGER
        if a.mode == "strike":
            code, lines = strike(path, a.check_name, a.note)
        elif a.mode == "pass":
            code, lines = passed(path, a.check_name, a.note)
        elif a.mode == "run":
            code, lines = run(path, a.check_name, command, a.note)
        elif a.mode == "reset":
            code, lines = reset(path, a.check_name, a.note)
        else:
            code, lines = ledger(path)
    except CannotLook as e:
        print("two-strikes could not look: %s" % e)
        return REFUSED_CODE
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
