# ORDER

Purpose: one task order for an agent. One task per order; hand the agent this file instead of a vague request.

Lines that begin with "Example:" are illustrations. Replace them with the real task.

## Task

Id: Example: NEXT-01 (export timeout)

Branch: Example: `task/NEXT-01-export-timeout`. Create it from a clean, committed main before any change.

## Goal

Example: exporting 10,000 rows to CSV finishes in under 5 seconds.

## Files in scope

- Example: `src/export.py`
- Example: `tests/test_export.py` (new tests are allowed here)

Nothing else. If you need to change any other file, STOP and ask: say which file, why, and roughly how many lines. Do not change it first and explain later.

## Size budget

Example: about 60 lines changed in total. If the change is heading past twice that, STOP and report instead of finishing.

## Done when

Example: `pytest tests/test_export.py -q` passes, including a new test that times an export of 10,000 rows and fails above 5 seconds.

## The probe that could cancel this task (run it first)

Example: time the export of 10,000 rows from the command line. If it already takes under 5 seconds, the slowness is in the page, not the export. Cancel and report that instead of building.

## Stop and report if

- the probe cancels the task;
- you need a file outside scope;
- the change is heading past twice the size budget;
- the same test still fails after 3 attempts;
- a test looks wrong (say why; do not change it);
- you are unsure what the goal means.

## Rules for this task

- Do not refactor, clean up, modernize, rewrite, rename or reformat anything not named above.
- Never delete, skip or weaken a test to make it pass.
- No new dependencies without asking.
- Commit on the task branch as you go, with what changed in each message.

## When done

Fill in REPORT.md, negative results first. Then STOP and report. Do not start the next task.
