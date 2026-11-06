#!/usr/bin/env python3
r"""heredoc_guard.py -- a Claude Code hook that refuses two shell commands that go wrong quietly.

1. A HEREDOC WHOSE BODY HOLDS A BACKSLASH. A heredoc is the `<<EOF ... EOF` block that pastes text into a command.
   Code carrying a backslash (`\n`, `\s`, `\u00e9`, a Windows path) passes through two or three layers of escaping on
   the way in: the shell, then the language inside it, then the string that language builds. Each layer can eat or
   double a backslash, so the file that lands is not the file that was written: a raw newline inside a string, a regex
   that no longer matches, a unicode-escape error. Nothing in the output says which layer did it.

2. A PYTHON STARTED WITH NO SCRIPT AND NOTHING ON ITS STANDARD INPUT, as in `python -` or a bare `python`. An agent's
   shell has no keyboard, so Python's interactive prompt either waits for input that never comes or, on some Windows
   shells, fails and retries in a loop that can fill the disk with its error. A script file, `-c`, `-m`, `--version`,
   and anything fed by a heredoc, `<`, `<<<` or a pipe all pass. The command is split the way a shell splits it, so a
   quoted message that only MENTIONS `python -` is never mistaken for one.

What to do instead (printed on refusal): write the script to a file and run the file, or make the change with an
editing tool.

CONTRACT. Claude Code runs this before each Bash command and hands it the call as JSON on standard input. Exit 2, with
the reason on standard error, blocks the command and shows the reason to the agent. Anything this script cannot read
lets the command through with exit 0: a guard must never block work because of its own failure.

USAGE
    python3 heredoc_guard.py                         the hook: JSON on standard input
    python3 heredoc_guard.py --self-test [--break NAME]
        one row per rule; each break switches one rule off, and only its own row may turn RED
"""
import argparse
import io
import json
import os
import re
import shlex
import sys

HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")  # `<<EOF`, `<<-EOF`, `<<'EOF'`, `<< "EOF"`
PYTHONS = re.compile(r"^(python|pythonw|py|python3(\.\d+)?)$")
TAKES_ARG = {"-X", "-W", "--check-hash-based-pycs"}  # options whose next word is their value, not a script
EXITS = {"-V", "-VV", "--version", "-h", "-?", "--help"}  # options that print and exit before any prompt
PREFIXES = {"then", "do", "else", "elif", "time", "nohup", "exec", "command", "!", "{"}  # words before the program

BREAKS = ("no-backslash-check", "no-bare-python-check", "no-feed-check", "no-body-cut")
BREAK = None


def bodies(cmd):
    """Each heredoc's body: from the line after its `<<DELIM` to the line that is exactly DELIM."""
    out = []
    for m in HEREDOC.finditer(cmd):
        start = cmd.find("\n", m.end())
        if start < 0:
            continue
        end = re.search(r"^\s*" + re.escape(m.group(2)) + r"\s*$", cmd[start + 1:], re.M)
        out.append(cmd[start + 1:start + 1 + end.start()] if end else cmd[start + 1:])
    return out


def backslash_in_body(cmd):
    """True when any heredoc body in the command holds a backslash."""
    if BREAK == "no-backslash-check":
        return False
    return any("\\" in body for body in bodies(cmd))


def without_bodies(cmd):
    """The command with every heredoc's body and closing line cut out; the `<<DELIM` stays, as the input it is."""
    if BREAK == "no-body-cut":
        return cmd
    pos = 0
    while True:
        m = HEREDOC.search(cmd, pos)
        if not m:
            return cmd
        start = cmd.find("\n", m.end())
        if start < 0:
            return cmd
        end = re.search(r"^\s*" + re.escape(m.group(2)) + r"[ \t]*$", cmd[start + 1:], re.M)
        cmd = cmd[:start + 1] + (cmd[start + 1 + end.end():] if end else "")
        pos = m.end()


def program_name(word):
    name = os.path.basename(word.replace("\\", "/")).lower()
    return name[:-4] if name.endswith(".exe") else name


def bare_python(cmd):
    """The first Python started with no script and no standard input, as its words; None when there is none."""
    if BREAK == "no-bare-python-check":
        return None
    lex = shlex.shlex(without_bodies(cmd), posix=True, punctuation_chars="();<>|&\n")
    lex.whitespace, lex.whitespace_split, lex.commenters = " \t\r", True, ""
    segs, words, fed, skip = [], [], False, False
    for t in list(lex) + [";"]:
        if skip:
            skip = False
        elif t and set(t) <= set("();|&\n"):
            segs.append((words, fed))
            words, fed = [], ("|" in t and "||" not in t)
        elif "<" in t:
            fed = True  # <, << and <<< all give the command its standard input
            skip = not t.startswith("<<")  # `< file`: the file name is not a word of the command
        elif ">" in t:
            skip = True  # `> out` names a file and `>&` a descriptor: neither is a word of the command
        else:
            words.append(t)
    for words, fed in segs:
        while words and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]) or words[0] in PREFIXES):
            words = words[1:]
        if BREAK == "no-feed-check":
            fed = False
        if fed or not words or not PYTHONS.match(program_name(words[0])):
            continue
        needs, args = True, iter(words[1:])
        for a in args:
            if a in ("-c", "-m") or (a[:2] in ("-c", "-m") and len(a) > 2) or a in EXITS:
                needs = False
                break
            if a == "-":
                break
            if a in TAKES_ARG:
                next(args, None)
            elif a.startswith("-"):
                if not a.startswith("--") and "i" in a[1:]:
                    break  # -i: the prompt opens after the script, the same trap
            else:
                needs = False  # a script file
                break
        if needs:
            return " ".join(words)
    return None


def refusal(cmd):
    """The reason this command is refused, in words; None when it may run."""
    if backslash_in_body(cmd):
        return ("Refused by the heredoc guard: this command's heredoc holds a backslash. A backslash inside a heredoc "
                "passes through the shell AND the language inside it, and either one can change it, so the file that "
                "lands may not be the one you wrote. Write the script to a file with your file-writing tool and run "
                "the file, or make the change with your editing tool.")
    bare = bare_python(cmd)
    if bare:
        return ("Refused by the heredoc guard: `%s` starts Python with no script and nothing on its standard input, so "
                "it opens Python's interactive prompt, which an agent's shell cannot answer: it waits forever or, on "
                "some Windows shells, loops on an error. Give it a script file, `-c`, or feed it with a heredoc or a "
                "pipe." % bare)
    return None


SLASH_CASES = [  # (command, refused?)
    ("cat > fix.py <<'EOF'\nprint('a\\nb')\nEOF", True), ("python3 - <<EOF\nimport re; re.compile(r'\\s+')\nEOF", True),
    ("cat <<-EOF > notes.txt\n\tC:\\Users\\me\nEOF", True),
    ("cat > ok.py <<'EOF'\nprint('plain')\nEOF", False), ("echo 'a\\nb' > x.txt", False), ("ls C:\\\\temp", False),
]
BARE_CASES = [
    ("python -", True), ("python -X utf8 -", True), ("python", True), ("cd /tmp/x && python -u -", True),
    ("py -3 -", True), ("python -i run.py", True), ("C:/Python313/python.exe -", True), ("FOO=1 python3 -", True),
    ("ls; python -I -B -", True), ("if true; then python -; fi", True), ("nohup python -u - &", True),
]
FED_CASES = [
    ("python - <<'EOF'\nprint(1)\nEOF", False), ("python -X utf8 - << EOF\nx = 1\nEOF\necho done", False),
    ("cat a.py | python -", False), ("python - < a.py", False), ("python - <<< 'print(1)'", False),
]
SCRIPTED_CASES = [
    ("for f in a b; do python $f; done", False), ("python -c 'print(1)'", False), ("python -m py_compile a.py", False),
    ("python -X utf8 tools/x.py --flag -", False), ("python --version", False), ("pip install x", False),
    ("python -u tools/x.py 2>&1 | tail -5", False), ("python3.12 -W ignore a.py", False),
]
MENTION_CASES = [
    ("git commit -m 'guard: python - with nothing on stdin'", False), ("echo \"python -\" > note.txt", False),
    ("cat <<'EOF' > s.sh\npython -\nEOF\nbash s.sh", False),
]
ROWS = [  # (row name, cases, the test that sorts them)
    ("a backslash in a heredoc body is refused; one outside a heredoc is not", SLASH_CASES, backslash_in_body),
    ("a Python with no script and no input is refused", BARE_CASES, lambda c: bare_python(c) is not None),
    ("a Python fed by a heredoc, a pipe or a file passes", FED_CASES, lambda c: bare_python(c) is not None),
    ("a Python given a script, -c, -m or --version passes", SCRIPTED_CASES, lambda c: bare_python(c) is not None),
    ("a command that only mentions python - passes", MENTION_CASES, lambda c: bare_python(c) is not None),
]


def self_test():
    bad = 0
    for name, cases, test in ROWS:
        wrong = [c for c, want in cases if bool(test(c)) != want]
        bad += bool(wrong)
        print("  %s  %s -- %s" % ("RED" if wrong else "ok ", name, "%d of %d sorted as named%s" % (
            len(cases) - len(wrong), len(cases), "; wrong: %r" % wrong[0] if wrong else "")))
    print("heredoc-guard self-test %s -- %d case(s), %d not as expected%s" % (
        "RED" if bad else "GREEN", len(ROWS), bad, " (break %s)" % BREAK if BREAK else ""))
    return 1 if bad else 0


def read_command(stream):
    """The Bash command in the hook's JSON, read as UTF-8 whatever the console's own encoding; None for any other tool."""
    data = json.load(io.TextIOWrapper(stream, encoding="utf-8", errors="replace"))
    if data.get("tool_name") != "Bash":
        return None
    return (data.get("tool_input") or {}).get("command") or ""


def main(argv=None):
    global BREAK
    ap = argparse.ArgumentParser(description="refuses a heredoc holding a backslash, and a Python with no input")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--break", dest="brk", choices=BREAKS, help="with --self-test only: switch one rule off")
    a = ap.parse_args(argv)
    if a.brk and not a.self_test:
        print("heredoc-guard: --break goes with --self-test only; the hook never runs with a rule switched off")
        return 2
    if a.self_test:
        BREAK = a.brk
        return self_test()
    try:
        cmd = read_command(sys.stdin.buffer)
        reason = refusal(cmd) if cmd else None
    except Exception:
        return 0
    if reason:
        sys.stderr.write(reason + "\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
