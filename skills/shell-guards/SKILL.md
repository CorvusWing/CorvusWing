---
name: shell-guards
description: Two small Claude Code hooks that refuse shell commands which fail without saying so -- a heredoc whose body holds a backslash (or a Python started with nothing to read), and a logged exit code that belongs to the wrong command ($? read after $(date)). Use when setting up a project's safety fences, when a scripted edit wrote a file different from the one intended, when a log says "exit 0" for a run that failed, when an agent's shell hangs on a Python prompt, or when someone asks how to make a rule an agent cannot forget. Ships two scripts with self-tests and a settings example to paste.
metadata:
  author: Ron Brazil
---

# Shell guards: two mistakes a hook can refuse

Most of this kit is instructions: an agent reads them, and an agent can forget them. These two are
**locks**. Claude Code runs each one before every shell command the agent sends, and a command that
breaks the rule never runs. The agent gets the reason in words and tries again the right way.

Both mistakes have the same shape: the command runs, nothing errors, and the result is quietly wrong.

## Mistake 1: a backslash pasted through a heredoc

A heredoc is the `<<'EOF' ... EOF` block an agent uses to paste a script into a command. When that
script holds a backslash (`\n` in a string, `\s` in a pattern, a Windows path), the backslash goes
through two or three layers of escaping: the shell, the language reading the script, and the string it
builds. Any layer can eat it or double it, so the file that lands is not the file the agent wrote. A
string grows a real line break, a pattern stops matching, and nothing says which layer did it.

**The guard refuses** any heredoc whose body holds a backslash. **Instead:** write the script to a
file with the file-writing tool and run the file, or make the change with the editing tool.

The same guard refuses a Python started with **nothing to read**: `python -` or a bare `python` with
no script, no `-c`, and nothing fed to it by a heredoc, a pipe or `<`. An agent's shell has no keyboard,
so Python's prompt waits forever or, on some Windows shells, fails and retries in a loop that can fill a
disk. A command that only *mentions* `python -` inside quotes is never mistaken for one.

## Mistake 2: a logged exit code that is the wrong command's

    ./run_tests.sh; echo "$(date) finished, exit $?" >> log.txt

`$?` holds the exit code of the last command that finished, and `$(date)` is a command that finishes.
By the time `$?` is read it is `date`'s code, 0, so the log says "exit 0" for a run that failed. Try it
in bash: `false; echo "$(date) exit $?"` prints exit 0, though `false` exits 1.

**The guard refuses** a command that reads `$?` (or `${?}`) after a command substitution in the same
command. **Instead:** capture it first, `rc=$?` straight after the command, then log `$rc`. Reading `$?`
before the substitution, inside it, inside arithmetic, in single quotes or in a later command all pass,
and so does a quoted heredoc's body, which the shell never runs. Scripts on disk never pass through a
hook, so `exit_status_guard.py --scan FILE...` checks them the same way.

## Switch them on

The guards need Python 3.8 or newer and no packages. On Windows, Claude Code runs hooks with Git Bash
when it is installed; the example says `"shell": "bash"` so `$HOME` means the same thing everywhere.

1. Install this folder like the others, so the scripts sit at
   `~/.claude/skills/shell-guards/scripts/`.
2. Open your settings file: `~/.claude/settings.json` for every project, or `.claude/settings.json`
   inside one project.
3. Copy the `"hooks"` part of `hooks.example.json` into it (on Windows, `hooks.example.windows.json`,
   which says `python` where the other says `python3`). If the file already has a `"hooks"` section,
   add the two entries to its `"PreToolUse"` list rather than replacing it. If you installed the kit
   for one project only, change `$HOME/.claude` to `$CLAUDE_PROJECT_DIR/.claude` in both commands.
4. Start a new session, then ask the agent to run `false; echo "$(date) exit $?"`. It should be refused.

To check the scripts themselves:

    python3 ~/.claude/skills/shell-guards/scripts/heredoc_guard.py --self-test
    python3 ~/.claude/skills/shell-guards/scripts/exit_status_guard.py --self-test

Each prints one row per rule and GREEN. `--break NAME` switches one rule off, and then only that rule's
row may turn RED: that is how you know the test can fail.

## What the scripts do

- `scripts/heredoc_guard.py` reads the hook's JSON on standard input. Exit 2, with the reason on
  standard error, blocks the command and shows the reason to the agent; exit 0 lets it run.
- `scripts/exit_status_guard.py` does the same for the exit-code rule, on Bash and Monitor commands,
  and adds `--scan` for files. It reads what a heredoc is from the guard beside it, so the two never
  disagree.

## Limits, said plainly

- **A guard that cannot read its input lets the command through.** A broken guard must never stop
  work, so a missing Python or unreadable input fails open, not shut. The self-test is how you know it
  is really reading.
- **They read the command as text**, the way a shell would split it, not by running it. A command
  built at run time (a variable that holds the heredoc, a script that writes another script) can slip
  past. The rules catch the common shapes, which is where the mistakes happen.
- **They guard the agent's shell tool only.** Your own terminal and your scripts on disk are not
  checked unless you run `--scan`.
- **A refusal costs one retry.** The agent rewrites the command the safe way; nothing is lost.

---

Part of CorvusWing, created by Ron Brazil. MIT License.
