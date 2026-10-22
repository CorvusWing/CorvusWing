# REPORT

Purpose: what one task actually did, written before the merge, with the negative results first.

Lines and rows that begin with "Example:" are illustrations. Replace them with the real results.

Task: Example: NEXT-01 (export timeout)

Branch and last commit: Example: `task/NEXT-01-export-timeout` at 9d3b4e7

## What did not work, or got worse (first)

- Example: the first attempt (loading the whole table into memory) used 2 GB for 10,000 rows; reverted.
- Example: exporting 100,000 rows still takes 30 s. Out of scope; added to HANDOFF.md as NEXT-06.

## What changed

| File | Lines changed | What and why |
|---|---|---|
| Example: `src/export.py` | +24 / -9 | one query for all rows, instead of one query per row |
| Example: `tests/test_export.py` | +18 | a new timing test for 10,000 rows |

Size against budget: Example: 51 lines against a budget of 60.

Files outside scope touched: Example: none.

## The measurement

| What | Before | After | Conditions | Command |
|---|---|---|---|---|
| Example: export of 10,000 rows | 41 s | 3.1 s | local machine, test data, median of 3 runs | `python scripts/time_export.py --rows 10000` |
| Example: test suite | 84 pass, 2 fail | 86 pass, 0 fail | main against this branch | `pytest -q` |

Which checks ran: Example: the full suite; nothing skipped.

## Still open

- Example: NEXT-06 (export of 100,000 rows is still slow)

## Plain summary

- Example: the export is about 13 times faster for 10,000 rows, and the change stayed inside its budget and its files.
- Example: very large exports are still slow; that is a separate task.
