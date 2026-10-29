---
name: test-freeze
description: Refuses a commit that changes an existing test in the same commit as code, unless the commit message says why on a line of its own. Use when an agent is about to change a failing test to make it pass, when a commit removes lines from a test file, when a check that used to fail has gone quiet, or when someone asks "did this weaken the tests". Ships one script, scripts/test_freeze.py, that reads a range of commits and proves its own refusals with a self-test.
---

# Test freeze: a changed test must say why

**The problem.** The cheapest way to make a failing test pass is to change the test. Sometimes that is
the right move: the test was wrong, or the requirement moved. Often it is not, and nothing in git tells
the two apart. A suite can get weaker one quiet edit at a time, and nobody sees it in review, because
the diff looks like a small tidy-up.

**The rule.** A commit that removes lines from an existing test file *and* changes code must say why.
It needs one line in its message, starting with `TEST-CHANGE:` and followed by a real reason:

    TEST-CHANGE: the old expected value encoded the rounding bug this commit fixes

Three cases are not judged, on purpose: a commit that only adds tests (nothing was weakened), a commit that
only changes tests (a test edit with no code change is a review question, not a rule), and a commit that
only changes code.

## What the script does

`scripts/test_freeze.py` reads the commits between two points (default `main..HEAD`) and prints one row for
each commit that is judged:

- **REFUSED**: it removes lines from a test and changes code, and the message has no `TEST-CHANGE:` line
  with a reason after it. The exit code is 1.
- **EXPLAINED**: the same kind of change, with a reason. The reason is printed, so a reviewer can read it.

It also runs its own self-test first. The self-test builds a scratch git repository with one commit per
case and checks each verdict by name. If the checker stops seeing a test, the run says so in words and
stops, rather than printing a clean result it cannot back up.

It needs Python 3.8 or newer and git. It uses no packages.

## How to run it

From the project's folder:

```bash
python3 skills/test-freeze/scripts/test_freeze.py check --range main..HEAD
python3 skills/test-freeze/scripts/test_freeze.py --self-test
```

On Windows, use `python` in place of `python3`. If the project keeps its skills somewhere else, use that path.
The script is copied with the skill, so it works from `~/.claude/skills/test-freeze/scripts/` too.

Exit codes: 0 when every judged commit is explained, 1 when one is refused, 78 when the range cannot be read
(a missing branch, or the folder is not a git repository).

## What to do when a commit is refused

1. Read the commit's test diff first. Ask: is the old expectation wrong, or did the code stop meeting a real
   requirement? Either can be a true reason. "The test was failing" alone is not one.
2. If the change is right, amend the message (or add a new commit that explains it) with a `TEST-CHANGE:`
   line that says what the old test got wrong.
3. If the change is wrong, put the test back and fix the code. A test that fails is information.
4. Never make the reason a single word or a placeholder such as `TEST-CHANGE: n/a`. The script accepts any
   text after the colon, so the only guard against an empty reason is the person who reads it.

## Make it part of the suite

This skill proves its own refusals. To make it block work, add the check to the project's suite, the same
way the `gates` skill adds other checks: one command, a line in the ledger, and a note in the notes file that
says what the check reads and where its breaks are. Run it on the range a landing will bring in, not on the
whole history, because older commits were written before the rule existed.

## Limits, said plainly

- A test written inside a source file (Rust's `#[cfg(test)]` module, for example) is not recognized as a test.
  Move such tests into a test file, or extend the path list at the top of the script.
- A renamed test file reads as a removed file and an added file, so a rename that also touches code needs a
  `TEST-CHANGE:` line.
- The script reads the message. It cannot tell whether the reason written there is true. A person reviewing
  the commit still has to read it.
- The lists of test paths and code extensions are short on purpose. Edit them to fit the project; the script
  does not guess.
