---
name: bake-off
description: Builds a piece whose answer does not exist yet (a parser, a scoring rule, a cache policy, a new file format) in a fixed order that stops the tests from being bent to fit. Use when the goal is clear but the mechanism is not, when an agent is told to "make the tests pass" for something nobody has designed, when several candidate approaches must be compared fairly, or when a change would otherwise rewrite the tests along with the code. Ships one script, scripts/bake_off.py, that checks a bake-off record against git and prints a scoreboard.
---

# Bake-off: build what nobody has invented yet, in a fixed order

**The problem.** A test can only check what has been decided. When the answer to "what should this piece do"
does not exist yet, "make the tests pass" is the wrong loop. The cheapest way to pass a test is to change it,
and an agent working alone will do that quietly, one edit at a time, until the tests say what the code does.

**The fix.** Write the order down, and check it. The bake-off has six parts, and each is committed before the
next one begins:

1. **Socket.** What the piece takes in, what it hands out, and the rules any correct version must obey. Written
   down in its own files and committed. Nothing downstream may change those files.
2. **Rules as tests.** Those rules, as tests, in a commit of their own. After this commit, the rule tests' files
   are frozen: no candidate, nor the control, nor the scoreboard may change them. A candidate that needs a rule
   changed starts a new bake-off, not an edit.
3. **Control.** A deliberately dumb version (returns its input, picks at random, takes the first item) run through
   the same tests. If the control passes a test, the test is too weak. Mark it **TOO WEAK** in the record.
   A stronger test is a change to the rules, so it is made before any candidate exists: commit the stronger
   rules, run the control again in a commit after them, and point the record at both new commits. Once a candidate
   exists, a stronger test starts a new bake-off. Never tune the control to fail a test.
4. **Candidates.** Each candidate on its own branch, started from the control, each with a **kill line**: the
   result that would make that candidate dead, written down and committed before the candidate's code, and before
   its first run. A candidate that hits its kill line is dead. Its tests are not.
5. **Scoreboard.** Every candidate and the control on every rule, in one table. When a candidate changes what some
   other part of the system produces (an output format, a neighboring result), the change is listed with its before
   and after. It is never counted as a failure.
6. **Pick.** Made by a person, with a reason written in the record. The candidate that builds a piece does not
   pick it, and a candidate whose kill line was hit cannot be picked.

## What the script does

`scripts/bake_off.py` reads one record, `bake-off/<name>.json`, which names each part and its commit, and checks
it against git. It refuses, in words, when:

- a part is missing; a part names no commit, or a commit the repository does not have; the rules or the socket
  list no files; a candidate has no kill line, no first-run time, or no result for a rule test;
- socket, rules, control, scoreboard and pick are not committed in that order;
- a candidate does not descend from the rules and the control, or descends from another candidate (candidates
  are siblings), or names a branch that does not hold its commit;
- a file the rules or the socket list is not in their commit, or the control, a candidate or the scoreboard
  changed one of those files after it was committed;
- the control has no rows, or does not run every rule test, or passes a test that is not marked TOO WEAK;
- a result is anything but `pass` or `fail`, or the rules name no test;
- a kill line has no words, does not say whether it was hit, is not committed before its candidate, its words
  are not in that commit, or its time is not older than the candidate's first run;
- the pick names a candidate whose kill line was hit, or has no reason, or a placeholder for one.

The scoreboard does not need the candidates merged: they can stay on their own branches, and the record names
each one's branch and commit.

`scoreboard` prints the table only for a record that checks. A record that does not check prints the refusal
alone: a comparison that did not happen must never read as a result.

Before its first check on a machine, the script runs its own self-test: a scratch repository with candidates on
sibling branches and one row per refusal, each checked by its own reason. A passed self-test leaves a small marker
in the system's temp folder, named by a hash of the script, the Python version and git's version, so later checks
skip it until one of those changes. It needs Python 3.8 or newer, and git. It uses no packages.

## The record

```json
{
  "name": "sort-list",
  "socket": {"commit": "<ref>", "files": ["docs/sort-socket.md"], "takes": "a list", "hands_out": "a sorted list"},
  "rules": {"commit": "<ref>", "files": ["tests/test_sort_rules.py"], "tests": ["takes_empty", "keeps_order"]},
  "control": {"commit": "<ref>", "name": "returns its input",
              "results": {"takes_empty": "pass", "keeps_order": "fail"}, "too_weak": ["takes_empty"]},
  "candidates": [
    {"name": "a", "branch": "try-a", "commit": "<ref>",
     "kill_line": {"text": "candidate a is dead if keeps_order fails on any input", "hit": false,
                   "commit": "<ref where the kill line was committed>", "written_at": "<ISO time with zone>"},
     "first_run_at": "<ISO time with zone>", "results": {"takes_empty": "pass", "keeps_order": "pass"}}
  ],
  "scoreboard": {"commit": "<ref>", "other_changes": [
    {"part": "output format", "case": "empty input", "before": "nothing", "after": "an empty list"}]},
  "pick": {"candidate": "a", "reason": "keeps the order on every rule the control fails", "commit": "<ref>"}
}
```

A `<ref>` is any git reference the repository can resolve: a hash, a branch name, a tag. `files` may name files
or folders. A kill line's words must appear in a file of its commit (a `KILL-LINES.md` on the candidate's branch,
or this record itself), written on one line. A time with a trailing `Z` reads as UTC.

## How to run it

From the project's folder:

```bash
python3 skills/bake-off/scripts/bake_off.py check sort-list
python3 skills/bake-off/scripts/bake_off.py scoreboard sort-list
python3 skills/bake-off/scripts/bake_off.py --self-test
```

On Windows, use `python` in place of `python3`. If the kit is installed for every project, the script is at
`~/.claude/skills/bake-off/scripts/bake_off.py` (on Windows,
`%USERPROFILE%\.claude\skills\bake-off\scripts\bake_off.py`); use that path instead.

Exit codes: 0 in order, 1 refused, 2 bad use of the command, 78 when the record or the repository cannot be read.

**Commit `bake-off/`** with the pick. The record, the rules' commit and the candidates' branches together are
what a reviewer reads to see that the comparison was fair.

## Rules for the people and agents using it

- Write the socket and the rules before any candidate exists. If you cannot write them, the question is not ready
  for a bake-off. Use `decide-first` first.
- Write the control before the candidates. A control written after the candidates tends to be a control the
  candidates already beat.
- Write each kill line, commit it, then build and run the candidate. Say what result would kill it.
- If a rule turns out to be unfair, change it on purpose, in a new bake-off: its rules commit holds the fairer
  rule, every candidate and the control are scored on it again, and the pick's reason gives the old scores beside
  the new ones (the old first). The record has no field for editing a rule in place, on purpose. Never change a
  rule silently to make a candidate pass; the frozen-files check refuses that.
- A piece with no candidate that passes the rules is not a failure of the method. Write that down as the result.

## Limits, said plainly

- The script checks the order and the wording of the record, and the history git holds. It cannot tell whether a
  test is a good test, or whether a result is true. The control's TOO WEAK marks are a person's judgment.
- The script runs no tests. Whoever runs the candidates writes the results into the record, and a wrong result
  there is not caught by this script.
- The frozen-files check covers the files the record lists. A rule test kept somewhere the record does not list is
  not protected, so list every file the rules live in.
- The scoreboard prints what the record says. For a piece whose output is a file, the file's own comparison tool
  (for example, a byte-for-byte check) is the thing to put in the `other_changes` list.
- Commit order is checked from git history. A rebase or a squash after the record is written can reorder the commits,
  so write the record after the history is final.

---

Part of CorvusWing. Created by Ron Brazil. MIT License.
