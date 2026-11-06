#!/usr/bin/env python3
r"""exit_status_guard.py -- a Claude Code hook that refuses a shell command whose logged exit code belongs to the wrong
command: one that reads `$?` AFTER a command substitution in the same command, as in

    ./run_tests.sh; echo "$(date) finished, exit $?" >> log.txt

WHY. `$?` holds the exit code of the last command that finished, and a command substitution, `$(...)` or backticks,
is a command that finishes. By the time `$?` is read, it holds `date`'s exit code, which is 0, never the test run's.
The log says "exit 0" for a run that failed, and nothing about the line looks wrong. Try it in bash:

    false; echo "$(date) exit $?"        prints "... exit 0", though `false` exits 1

The same happens with `${?}`, and with `msg="$(date) $?"`.

What passes: `$?` read BEFORE the substitution (`echo "exit $? at $(date)"`), captured first (`rc=$?; echo "$(date)
exit $rc"`), inside the substitution (`"$(false; echo $?)"`), inside arithmetic (`$(( $? + 1 ))`), inside single
quotes, after an escaped `\$(`, or in a later command (`x=$(cmd) && echo $?`). A heredoc with a quoted delimiter
(`<<'EOF'`) is plain text that the shell never expands, so its body is skipped; an unquoted one is expanded, so it is
checked.

What to do instead (printed on refusal): capture the code first, `rc=$?` straight after the command, then log `$rc`.

CONTRACT. Claude Code runs this before each Bash command and hands it the call as JSON on standard input. Exit 2, with
the reason on standard error, blocks the command and shows the reason to the agent. Anything this script cannot read
lets the command through with exit 0: a guard must never block work because of its own failure. Scripts on disk never
pass through a hook, so `--scan FILE...` runs the same test over them.

USAGE
    python3 exit_status_guard.py                         the hook: JSON on standard input
    python3 exit_status_guard.py --scan FILE...          exit 0 clean, 1 a trap found, 78 a file cannot be read
    python3 exit_status_guard.py --self-test [--break NAME]
        one row per rule; each break switches one rule off, and only its own row may turn RED
"""
import argparse
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from heredoc_guard import HEREDOC  # noqa: E402 -- what a heredoc is has ONE definition, in the guard beside this one

STATUS = ("$?", "${?}")
REFUSED_CODE = 78  # --scan could not look: a file cannot be read
BREAKS = ("no-substitution-check", "no-separator-reset", "no-quoted-heredoc-skip")
BREAK = None


def _skip_single(s, i):
    """Index just past a single-quoted string that opens at s[i]."""
    j = s.find("'", i + 1)
    return len(s) if j < 0 else j + 1


def _close(s, i, opener, closer):
    """Index of the bracket closing the one opened just before s[i], quotes respected."""
    depth, n = 1, len(s)
    while i < n:
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "'":
            i = _skip_single(s, i)
            continue
        if c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return n


def traps(s):
    """Each place in the command text where `$?` is read after a command substitution in the same command, as character
    offsets (empty: no trap). What starts a new command: ; & | newline ( ) { } -- but not the & of a redirection (2>&1,
    &>). A substitution's own inside is a command list of its own and is checked the same way."""
    found, i, n = [], 0, len(s)
    seen_sub, in_double = False, False
    quoted_bodies = []  # delimiters of quoted heredocs opened on this line; their bodies start at the next newline
    while i < n:
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "\n" and not in_double and quoted_bodies:
            for delim in quoted_bodies:
                end = re.compile(r"^\s*" + re.escape(delim) + r"\s*$", re.M).search(s, i + 1)
                i = n if not end else end.end()
            quoted_bodies = []
            seen_sub = False
            continue
        if s.startswith("<<", i) and not in_double and not s.startswith("<<<", i):
            m = HEREDOC.match(s, i)
            if m and m.group(1) and BREAK != "no-quoted-heredoc-skip":
                quoted_bodies.append(m.group(2))
                i = m.end()
                continue
        if c == "'" and not in_double:
            i = _skip_single(s, i)
            continue
        if c == '"':
            in_double = not in_double
            i += 1
            continue
        if c == "#" and not in_double and (i == 0 or s[i - 1] in " \t\n;&|("):
            j = s.find("\n", i)
            i = n if j < 0 else j
            continue
        if s.startswith("$((", i):
            i += 3  # arithmetic: no command runs, so its inside belongs to this command
            continue
        if s.startswith("$(", i):
            end = _close(s, i + 2, "(", ")")
            found += [i + 2 + k for k in traps(s[i + 2:end])]
            seen_sub = BREAK != "no-substitution-check"
            i = end + 1
            continue
        if c == "`":
            j = s.find("`", i + 1)
            end = n if j < 0 else j
            found += [i + 1 + k for k in traps(s[i + 1:end])]
            seen_sub = BREAK != "no-substitution-check"
            i = end + 1
            continue
        if any(s.startswith(t, i) for t in STATUS):
            if seen_sub:
                found.append(i)
            i += 2
            continue
        if not in_double and BREAK != "no-separator-reset":
            redirect_amp = c == "&" and ((i > 0 and s[i - 1] in "<>") or s.startswith("&>", i))
            if (c in ";|\n(){}" or c == "&") and not redirect_amp:
                seen_sub = False
        i += 1
    return found


REFUSE = [
    'false; echo "$(date) exit $?"',
    'cmd; echo "$(date +%T) rc=$?" >> log',
    'echo "`date` exit $?"',
    "printf '%s %s\\n' \"$(date)\" \"$?\"",
    'node x.mjs > log 2>&1; echo "done $(date -Is) exit $?" >> log',
    'false; echo "$(date) ${?}"',
    'false; msg="$(date +%S) $?"; echo "$msg"',
    'cmd; echo "$(date)" 2>&1 "$?"',
    'echo "$(echo "$(date) $?")"',
    'false\ncat <<EOF\nan unquoted body is expanded: $(date +%S) exit $?\nEOF',
    "cat <<'EOF' > notes.md\nprose: echo \"$(date) exit $?\" is the trap\nEOF\nfalse; echo \"$(date) $?\"",
]
PASS = [
    'false; echo "exit $? at $(date)"',
    'cmd; rc=$?; echo "$(date) exit $rc"',
    'echo "$(false; echo $?)"',
    'false; echo $(( $? + 1 ))',
    "echo '$(date) $?'",
    'x=$(cmd) && echo $?',
    'cmd 2>&1; echo $?',
    '# a note: $(date) then $?\necho ok',
    'echo "\\$(date) $?"',
    'for f in $(ls); do\n  check "$f"\n  echo $?\ndone',
    'if [ "$(cat f)" = x ]; then echo $?; fi',
    'cat <<< "$(date) $HOME"; echo $?',
]
QUOTED_HEREDOC = [
    "cat >> notes.md <<'EOF'\nthe trap: `echo \"$(date) ... exit $?\"` logs the date's exit code\nEOF",
    'R=x; cat >> log.md <<"EOF"\n- in $(date) the $? reads date\nEOF\necho done',
]
ROWS = [  # (row name, commands, refused?)
    ("$? read after a substitution in the same command is refused", REFUSE, True),
    ("$? read before, captured first, or in a later command passes", PASS, False),
    ("a quoted heredoc's body is text, never a command, and passes", QUOTED_HEREDOC, False),
]


def self_test():
    bad = 0
    for name, cases, want in ROWS:
        wrong = [c for c in cases if bool(traps(c)) != want]
        bad += bool(wrong)
        print("  %s  %s -- %s" % ("RED" if wrong else "ok ", name, "%d of %d as named%s" % (
            len(cases) - len(wrong), len(cases), "; wrong: %r" % wrong[0] if wrong else "")))
    print("exit-status-guard self-test %s -- %d case(s), %d not as expected%s" % (
        "RED" if bad else "GREEN", len(ROWS), bad, " (break %s)" % BREAK if BREAK else ""))
    return 1 if bad else 0


def scan(paths):
    hits = 0
    for p in paths:
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError as e:
            print("exit-status-guard could not look: %s cannot be read (%s)" % (p, e))
            return REFUSED_CODE
        for off in traps(text):
            print("  %s:%d: $? read after a command substitution in the same command" % (p, text.count("\n", 0, off) + 1))
            hits += 1
    print("exit-status-guard scan %s -- %d trap(s) in %d file(s)" % ("RED" if hits else "GREEN", hits, len(paths)))
    return 1 if hits else 0


def read_command(stream):
    """The shell command in the hook's JSON, read as UTF-8 whatever the console's own encoding; None for other tools."""
    data = json.load(io.TextIOWrapper(stream, encoding="utf-8", errors="replace"))
    if data.get("tool_name") not in ("Bash", "Monitor"):
        return None
    return (data.get("tool_input") or {}).get("command") or ""


def main(argv=None):
    global BREAK
    ap = argparse.ArgumentParser(description="refuses a logged $? that belongs to a command substitution")
    ap.add_argument("--scan", nargs="+", metavar="FILE", help="check shell scripts on disk")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--break", dest="brk", choices=BREAKS, help="with --self-test only: switch one rule off")
    a = ap.parse_args(argv)
    if a.brk and not a.self_test:
        print("exit-status-guard: --break goes with --self-test only; the hook never runs with a rule switched off")
        return 2
    if a.self_test:
        BREAK = a.brk
        return self_test()
    if a.scan:
        return scan(a.scan)
    try:
        cmd = read_command(sys.stdin.buffer)
        found = traps(cmd) if cmd else []
    except Exception:
        return 0
    if found:
        sys.stderr.write(
            "Refused by the exit-status guard: this command reads $? after a command substitution in the same command "
            "(as in echo \"$(date) ... exit $?\"). The substitution sets $? when it runs, so the log would show the "
            "substitution's exit code, 0, never the real command's. Capture it first: rc=$? straight after the command, "
            "then log $rc.\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
