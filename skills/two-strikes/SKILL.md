---
name: two-strikes
description: Stops a step after the same check fails twice in a row, so an agent reports the failure to a person instead of trying a third variation. Use when a test, build, command or check has failed twice, when an agent is about to "just try one more thing" on the same failure, when a run is looping, or when someone asks how to stop an agent from spinning. Ships one script, scripts/two_strikes.py, with an append-only ledger, a run wrapper and a self-test.
metadata:
  author: Ron Brazil
---

# Two strikes: a check that fails twice in a row stops and reports

**The problem.** An agent that hits the same failure tends to try again, and again. Each try is a small
variation on the last, the cost adds up, and the third or fourth try rarely reaches anything the second
could not have reached with a human reading the failure. The loop feels like progress. It is usually
spinning.

**The rule.** The second failure in a row of the same check is a stop. The agent writes down what it tried,
the failing output and its best guess at the cause, and hands that to a person. It does not try a third time.

"The same check" means the same named thing: the same test, the same command, the same gate. Names are
compared without regard to case or spaces, so `Unit tests: parser` and `unit tests:parser` are one check. A
failure of a different check starts its own count. A pass ends the run of failures, so a check that failed
in March, passed in April and failed again in May is two separate first strikes, not a stop. Without the
recorded pass in between, the May failure is the second strike.

## What the script does

`scripts/two_strikes.py` keeps a ledger, `strikes.jsonl` in the project's folder (or any path given with
`--ledger`): one JSON entry per line, only ever appended, so nothing is lost and two writers at the same
moment take turns instead of overwriting each other. Five commands:

- `run "<check>" -- <command>` runs the command and records the result itself: a pass, or a strike. It
  refuses to run a check that is already stopped. This is the easiest way to use it: put it in front of the
  command, and the count can never be forgotten.
- `strike "<check>" --note "what failed"` records one failure by hand. The first prints "strike 1 of 2
  recorded". The second in a row prints **STOP AND REPORT**.
- `pass "<check>"` records a pass by hand, which ends the check's run of failures.
- `reset "<check>" --note "what was fixed"` starts the count again. A person writes this, once the cause is
  fixed and the check has a fresh reason to pass.
- `ledger` lists every check with its failures in a row.

Exit codes: 0 fine; 1 `run`'s command failed (a first strike); 2 bad use, such as a check with no name;
3 **STOP**: a second failure in a row, a stopped check that `run` refused to run, or `ledger` showing a stopped
check; 78 the ledger cannot be read or written, or `run`'s command cannot be started (nothing is recorded then).
**If the exit code is 3, stop.**

Before its first command on a machine, the script runs its own self-test: thirteen cases, each on a scratch
ledger, each checked by name. If the counting stops working, the run says so in words and does not pretend
to count. A passed self-test leaves a small marker in the system's temp folder, named by a hash of the script
and the Python version, so later commands skip it until one of those changes.

It needs Python 3.8 or newer. It uses no packages.

## How to use it

Put `run` in front of the check:

```bash
python3 skills/two-strikes/scripts/two_strikes.py run "unit tests: parser" -- python3 -m pytest tests/test_parser.py
```

Or record a failure by hand when the check runs some other way:

```bash
python3 skills/two-strikes/scripts/two_strikes.py strike "unit tests: parser" --note "KeyError on empty input"
```

On Windows, use `python` in place of `python3`. If the kit is installed for every project, the script is at
`~/.claude/skills/two-strikes/scripts/two_strikes.py` (on Windows,
`%USERPROFILE%\.claude\skills\two-strikes\scripts\two_strikes.py`); use that path instead.

**Commit `strikes.jsonl`** with the project's other notes. It is the record of what failed and when, and a
person reviewing the work reads it.

If the exit code is 3, stop. Do not run the check again. Write the report, in this order:

1. What the check is, and the exact command that runs it.
2. The failing output, copied in full (or the part that matters, with the line numbers).
3. What was tried and what each try showed. The first failure counts as a try too.
4. The likely cause, and how sure you are. Name what would prove it.
5. What you need from a person: a decision, a missing file, or access you do not have.

Then wait for the person. Their reset, or their fix, is what starts a fresh count.

## Where it fits

- In an agent's instructions, put one line such as: "After a second failure in a row of the same check, stop
  and report (see the two-strikes skill). Do not try a third time." The skill's own name is enough for most
  tools to find it. The `scope-guard` skill's stop condition and the ORDER template say the same.
- In a project's suite, the `gates` skill can call `ledger` at the end of a run, so the stopped checks show up
  next to the pass and fail results.
- It counts failures, not reasons. Two failures in a row with different causes still stop the step, on
  purpose: a step that needs a third try is a step that needs a person to look at it.

## Limits, said plainly

- The count is only as good as the check name. Use the same name every time (copy it from the first report),
  or use `run`, which takes the name once per command line.
- A failure recorded by hand is only counted if someone records it. `run` removes that gap.
- A pass that is never recorded leaves the earlier failure standing, so the next failure stops the step. That
  errs on the side of stopping.
- The script does not stop a run by itself. It returns exit code 3, and the run that calls it has to stop when
  it sees that. `run` does refuse to run a stopped check, which is as close to a lock as a script can get.
- A reset is trust. Only a person should write one, and only after the cause is fixed.

---

Part of CorvusWing, created by Ron Brazil. MIT License.
