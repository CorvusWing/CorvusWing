---
name: two-strikes
description: Stops a step after its second failure of the same check, so an agent reports the failure to a person instead of trying a third variation. Use when a test, build, command or check has failed twice, when an agent is about to "just try one more thing" on the same failure, when a run is looping, or when someone asks how to stop an agent from spinning. Ships one script, scripts/two_strikes.py, with a ledger file and a self-test.
---

# Two strikes: a step that fails twice stops and reports

**The problem.** An agent that hits the same failure tends to try again, and again. Each try is a small
variation on the last, the cost adds up, and the third or fourth try rarely reaches anything the second
could not have reached with a human reading the failure. The loop feels like progress. It is usually
spinning.

**The rule.** The second failure of the same check is a stop. The agent writes down what it tried, the
failing output and its best guess at the cause, and hands that to a person. It does not try a third time.

"The same check" means the same named thing: the same test, the same command, the same gate. A failure of
a different check starts its own count.

## What the script does

`scripts/two_strikes.py` keeps a ledger, a JSON file named `strikes.json` in the project's folder (or any
path given with `--ledger`). Three commands:

- `strike "<check name>" --note "what failed"` records one failure. The first failure prints
  "strike 1 of 2 recorded". The second prints **STOP AND REPORT** and exits 1.
- `reset "<check name>"` starts the count again for that check. A person writes this, once the cause is
  fixed and the check has a fresh reason to pass.
- `ledger` lists every check with its count since its last reset. It exits 1 if any check is stopped.

The ledger is only ever appended to. Nothing is deleted, so the record of what failed stays intact.

The script runs its own self-test first. The self-test uses a scratch ledger and checks six cases by name. If
the counting stops working, the run says so in words and does not pretend to count.

It needs Python 3.8 or newer. It uses no packages.

## How to use it

When a check fails, record it:

```bash
python3 skills/two-strikes/scripts/two_strikes.py strike "unit tests: parser" --note "KeyError on empty input"
```

If the exit code is 1, stop. Do not run the check again. Write the report, in this order:

1. What the check is, and the exact command that runs it.
2. The failing output, copied in full (or the part that matters, with the line numbers).
3. What was tried and what each try showed. The first failure counts as a try too.
4. The likely cause, and how sure you are. Name what would prove it.
5. What you need from a person: a decision, a missing file, or access you do not have.

Then wait for the person. Their reset, or their fix, is what starts a fresh count.

## Where it fits

- In an agent's instructions, put one line such as: "After a second failure of the same check, stop and report
  (see the two-strikes skill). Do not try a third time." The skill's own name is enough for most tools to find it.
- In a project's suite, the `gates` skill can call `ledger` at the end of a run, so the stopped checks show up
  next to the pass and fail results.
- It counts failures, not reasons. Two failures with different causes still stop the step, on purpose: a
  step that needs a third try is a step that needs a person to look at it.

## Limits, said plainly

- The count is only as good as the check name. Use the same name every time (copy it from the first report).
- A failure the agent never records is not counted. Record each failure at the moment it happens.
- The script does not stop a run by itself. It returns exit code 1, and the run that calls it has to stop when it sees that.
- A reset is trust. Only a person should write one, and only after the cause is fixed.
