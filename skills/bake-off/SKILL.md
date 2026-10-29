---
name: bake-off
description: Builds a piece whose answer does not exist yet (a parser, a scoring rule, a cache policy, a new file format) in a fixed order that stops the tests from being bent to fit. Use when the goal is clear but the mechanism is not, when an agent is told to "make the tests pass" for something nobody has designed, when several candidate approaches must be compared fairly, or when a change would otherwise rewrite the tests along with the code. Ships one script, scripts/bake_off.py, that checks a bake-off record and prints a scoreboard.
---

# Bake-off: build what nobody has invented yet, in a fixed order

**The problem.** A test can only check what has been decided. When the answer to "what should this piece do"
does not exist yet, "make the tests pass" is the wrong loop. The cheapest way to pass a test is to change it,
and an agent working alone will do that quietly, one edit at a time, until the tests say what the code does.

**The fix.** Write the order down, and check it. The bake-off has six parts, and each is committed before the
next one begins:

1. **Socket.** What the piece takes in, what it hands out, and the rules any correct version must obey. Written
   down and committed. Nothing downstream may change it.
2. **Rules as tests.** Those rules, as tests, in a commit of their own. After this commit, every candidate
   treats them as read-only. A candidate that needs a rule changed starts a new bake-off, not an edit.
3. **Control.** A deliberately dumb version (returns its input, picks at random, takes the first item) run through
   the same tests. If the control passes a test, the test is too weak. Mark it **TOO WEAK** in the record, and
   make it stronger. Never tune the control to fail a test.
4. **Candidates.** Each candidate on its own branch, each with a **kill line** written before its first run:
   the result that would make that candidate dead. A candidate that hits its kill line is dead. Its tests are not.
5. **Scoreboard.** Every candidate and the control on every rule, in one table. Changes that other parts of the
   system made are listed with their before and after. They are never counted as failures.
6. **Pick.** Made by a person (or the planner), with a reason written in the record. The candidate that builds a
   piece does not pick it.

## What the script does

`scripts/bake_off.py` reads one record, `bake-off/<name>.json`, which names each part and its commit. It refuses,
in words, when:

- a part is missing, or a candidate has no kill line, no first-run time, or no result for a rule test;
- a part is not committed before the next (rules committed after a candidate, for example);
- the control has no rows, or does not run every rule test;
- the control passes a test that is not marked TOO WEAK;
- a kill line is not older than its candidate's first run;
- the pick has no reason, or names no candidate;
- a commit the record names does not exist in the repository.

`scoreboard` prints the table only for a record that checks. A record that does not check prints the refusal
alone: a comparison that did not happen must never read as a result.

The script runs its own self-test first, with a scratch repository and one row per refusal. It needs Python 3.8
or newer, and git. It uses no packages.

## The record

```json
{
  "name": "sort-list",
  "socket": {"commit": "<ref>", "takes": "a list", "hands_out": "a sorted list"},
  "rules": {"commit": "<ref>", "tests": ["takes_empty", "keeps_order"]},
  "control": {"commit": "<ref>", "name": "returns its input",
              "results": {"takes_empty": "pass", "keeps_order": "fail"}, "too_weak": ["takes_empty"]},
  "candidates": [
    {"name": "a", "branch": "try-a", "commit": "<ref>", "kill_line": {"written_at": "<ISO time with zone>"},
     "first_run_at": "<ISO time with zone>", "results": {"takes_empty": "pass", "keeps_order": "pass"}}
  ],
  "scoreboard": {"commit": "<ref>", "other_changes": [
    {"part": "output format", "case": "empty input", "before": "nothing", "after": "an empty list"}]},
  "pick": {"candidate": "a", "reason": "keeps the order on every rule the control fails", "commit": "<ref>"}
}
```

A `<ref>` is any git reference the repository can resolve: a hash, a branch name, a tag.

## How to run it

From the project's folder:

```bash
python3 skills/bake-off/scripts/bake_off.py check sort-list
python3 skills/bake-off/scripts/bake_off.py scoreboard sort-list
python3 skills/bake-off/scripts/bake_off.py --self-test
```

On Windows, use `python` in place of `python3`. Exit codes: 0 in order, 1 refused, 78 when the record or the
repository cannot be read.

## Rules for the people and agents using it

- Write the socket and the rules before any candidate exists. If you cannot write them, the question is not ready
  for a bake-off. Use `decide-first` first.
- Write the control before the candidates. A control written after the candidates tends to be a control the
  candidates already beat.
- Write each kill line before running the candidate, and say what result would kill it. Then run it.
- If a rule turns out to be unfair, change it on purpose: write a new rule, run the old and new scores side by
  side (the old first), and record the change in the record. Never change a rule silently to make a candidate pass.
- A piece with no candidate that passes the rules is not a failure of the method. Write that down as the result.

## Limits, said plainly

- The script checks the order and the wording of the record. It cannot tell whether a test is a good test, or whether
  a result is true. The control's TOO WEAK marks are a person's judgment.
- The script runs no tests. Whoever runs the candidates writes the results into the record, and a wrong result
  there is not caught by this script.
- The scoreboard prints what the record says. For a piece whose output is a file, the file's own comparison tool
  (for example, a byte-for-byte check) is the thing to put in the `other_changes` list.
- Commit order is checked from git history. A rebase or a squash after the record is written can reorder the commits,
  so write the record after the history is final.
