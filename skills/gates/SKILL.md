---
name: gates
description: Builds a project's check suite ("gates"): one command that runs every check, a ledger that remembers each run against the files it checked, a deliberate break per gate that proves it can fail, and a progress window that opens beside a long run and shows how far along it is and when it should finish. Interviews the developer first, one or two questions at a time. Use after start-here, when a project has no single "run every check" command, when an agent's "it works" cannot be re-checked by anyone, or when someone says "set up gates", "build a test suite", "build a progress window" or "build a run daemon". Builds one part per session.
---

# Gates

A **gate** is a check that answers one question with pass or fail, by itself: do the tests pass,
does the build finish, does the import still read all 10,000 rows, is the page still under its size
limit. The **suite** is every gate, run by one command.

Why it matters: an agent saying "it works" is a claim. A gate going green is evidence anyone can run
again tomorrow and get the same answer. Without gates, every session starts by trusting the last one.

This skill builds four parts, in order. **One part per session**, each committed on its own branch
like any other task:

1. **The runner**: one command that runs every gate and never hides a failure.
2. **The ledger**: a file that remembers every run, and which files each pass was measured on.
3. **The breaks**: one deliberate fault per gate, proving the gate can fail.
4. **The progress window**: a second window that shows how far along a long run is.

Tell the developer that at the start, in about these words:

> I'll ask a few short questions, then build the first part: one command that runs every check you
> trust. The ledger, the proof that each check can fail, and the progress window come in the next
> sessions, one at a time.

## Part 0: Look first (read only)

- Find what already checks the project: the test folder, a lint or format config, build scripts,
  CI files (`.github/workflows/`), the scripts in `package.json`, a `Makefile`.
- Run nothing yet. Write the list down: each check, its command, and whether anyone runs it today.

## Part 1: The questions

One or two at a time, the way start-here asks them. Record answers in the developer's own words.

**Round 1**

1. Which checks do you trust today, and which do you run before you call something done?
2. What broke recently without any check noticing? (That story becomes the first new gate.)

**Round 2**

3. How long can the whole suite take before you stop running it? And a quick subset, for the
   middle of a task? (Typical answers: under 10 minutes whole, under 1 minute quick.)
4. Which operating system and terminal do you use (Windows Terminal, macOS Terminal, VS Code's
   terminal, something else)? Should a progress window open by itself when a long run starts?

**Round 3**

5. Does anything run checks for you automatically (GitHub Actions or another CI service)?
6. Is there anything a check must never touch: a real database, real email, a paid API?

Read back a five-line summary and ask "Is that accurate?" before building.

## Part 2: The runner (session 1)

- **One command runs everything**: `npm run gates`, `make gates`, `python tools/gates.py`, whatever
  fits the project. **One list of gates, in one file**: each entry has a name, the command, one line
  saying what it proves, and whether it is in the quick subset.
- **Each gate is its own small program** that exits 0 on a pass and non-zero on a fail, and on a
  fail prints why, in words, naming the file or the number that was wrong.
- **A gate that cannot run is not a pass.** If its tool is missing, a port is taken, or its input
  file is absent, it prints REFUSED and the reason. A check that silently does nothing looks
  exactly like a check that passed.
- **A failure never hides the rest.** If the runner stops at the first red gate, it says every later
  gate is UNKNOWN, not passing. A `--keep-going` flag runs them all and lists every red at the end.
- **The quick subset** (`--quick`) is for the middle of a task; **the whole suite** runs before
  every merge.
- **Keep the real exit code.** Write the run's output to a log file as well as the screen. Piping
  the output through another program (`| tail`) reports that program's exit code, and a failed run
  then reads as a success.
- **Never edit a file while the suite runs.** A file that changes halfway makes every result in
  that run unreliable, not just the one that was running.

Done when: the one command runs every gate from Part 0, a planted typo in a source file turns at
least one gate red, and the runner says so in words.

## Part 3: The ledger (session 2)

- After each gate, the runner appends one line to a ledger file (for example `.gates.jsonl`, one
  JSON object per line): the gate's name, PASS / FAIL / REFUSED, its seconds, the time, the
  commit, and a **fingerprint** of the files that gate reads (a hash: a short code that changes
  whenever any of those files change).
- **Why the fingerprint**: a green line recorded against different files is not a pass. "It passed
  yesterday" means nothing if the code changed since. **Read the ledger, not the exit code.**
- `gates --status` prints each gate's last result, whether it is STALE (its files changed since
  that result), and its last time in seconds. Those times feed the progress window's estimate.
- Add `.gates.jsonl` to `.gitignore` if the developer prefers; it is a record of runs, not code.

Done when: two runs in a row show the second one's results, and editing one file makes exactly
the gates that read it show STALE.

## Part 4: The breaks: every gate proves it can fail (session 3)

- For each gate, write one **deliberate fault** it must catch: a wrong number planted in a fixture,
  a line removed, a fixed bug put back. `gates --break <gate>` applies the fault to a temporary
  copy (or behind a switch), runs the gate, and expects RED. Nothing in the real code changes.
- **A break that leaves its gate green means the gate checks nothing.** Fix the gate. Never
  loosen it to make the break pass or fail.
- **Confirm the break really broke something.** A fault that changes nothing (a value replaced with
  itself) makes a good gate look broken, and the natural next move, loosening the gate, makes it
  worse.
- **Widen a gate by naming the new case**, never by loosening its pattern.
- When a real bug slips past every gate, the fix's task adds the gate that would have caught it, and
  that gate's break is the bug itself.

Done when: `gates --break all` turns every gate red, one at a time, each with its own reason printed.

## Part 5: The progress window (session 4)

A long run with no feedback leaves the developer guessing whether it is nine minutes or ninety.
The window answers that, live, without cluttering the run's own output.

How it works:

- **The runner writes a small status file after every gate**: the run's id, the list of gates, the
  current gate, the start time, each finished gate's result and seconds, and a "done" flag. It
  writes, flushes and moves on. It never waits for anyone to read it.
- **A separate watcher program draws the window.** It reads the status file a few times a second and
  shows: a bar, "gate N of M", the current gate's name, the time so far, the red results as they
  land, and an **estimate of the finish**: the sum of the remaining gates' last times from the
  ledger. On the first run there is no history, so it says "no estimate yet" rather than guess.
- **It opens in its own window**, so the suite keeps its own output. A bar printed into the same
  stream would scroll away in a second.
- **Nothing in the suite depends on the window.** If the watcher crashes or never opens, the run
  carries on and its results are the same.
- **It closes itself** a few seconds after the run ends, so it can be read, and **gives up** after
  five minutes with no change to the status file, saying so. A window waiting forever on a run that
  died is a window somebody leaves open, and then the next run has two.
- **On by default for the whole suite**; off for a single gate and in CI. A switch that turns it off
  will be used once "to keep the output tidy", and the developer will conclude the window is
  broken. A default beats a rule somebody has to remember.
- **Opening a window** depends on the answer to question 4. Windows Terminal: `wt -w 0 new-tab`
  followed by the watcher's command. macOS: an `osascript` line that asks Terminal to run it.
  Linux: the desktop's terminal (`gnome-terminal --`, `konsole -e`). Ask before choosing; use the
  terminal the developer named.
- Write the watcher in the project's own language, small (a couple of hundred lines at most).

Done when: a whole-suite run opens the window by itself, the bar moves gate by gate, the estimate is
within a minute of the real finish on the second run, a red gate shows the moment it lands, and the
window closes on its own.

## Part 6: Wire it into the loop

- **AGENTS.md**: "Done" means the quick gates green, with their output pasted. Before any merge, the
  whole suite, with the ledger read.
- **STATE.md**: the number of gates, and the last whole run: the date, the commit, the result, the
  minutes.
- **PICKUP.md**: its notes check names one gate whose number the notes state.
- **Every task that adds a behavior adds or widens a gate** in the same branch, with its break.

## Rules for this skill

- One part per session. Ask before each git command that changes the repository.
- Never weaken, skip or delete a gate to make a run green. If a gate looks wrong, stop and say why.
- A gate never touches anything real (question 6). If it would, it is refused, in words.
- Explain every term the first time it comes up: gate, suite, ledger, fingerprint, exit code.
- End with a plain summary in bullets: what was built, the command, what is next.

---

Part of CorvusWing. Created by Ron Brazil. MIT License.
