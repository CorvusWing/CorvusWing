---
name: test-freeze
description: Refuses a commit that changes or deletes an existing test, unless the commit message says why on a line of its own. Use when an agent is about to change a failing test to make it pass, when a commit edits, skips or deletes a test file, when a check that used to fail has gone quiet, or when someone asks "did this weaken the tests". Ships one script, scripts/test_freeze.py, that reads a range of commits and proves its own refusals with a self-test.
metadata:
  author: Ron Brazil
---

# Test freeze: a changed test must say why

**The problem.** The cheapest way to make a failing test pass is to change the test. Sometimes that is
the right move: the test was wrong, or the requirement moved. Often it is not, and nothing in git tells
the two apart. A suite can get weaker one quiet edit at a time, and nobody sees it in review, because
the diff looks like a small tidy-up. Splitting the change in two (the test in one commit, the code in the
next) hides it even better.

**The rule.** A commit that changes or deletes a test file that already existed must say why, whether or
not it also changes code. It needs one line in its message, starting with `TEST-CHANGE:` and followed by a
real reason:

    TEST-CHANGE: the old expected value encoded the rounding bug this commit fixes

Adding a skip or expected-failure marker to an existing test changes that test, so it needs the line too.
A commit that only adds new test files is not judged: nothing that existed was weakened.

## What the script does

`scripts/test_freeze.py` reads the commits between two points (default `main..HEAD`) and prints one row for
each commit that is judged:

- **REFUSED**: it changes or deletes an existing test, and its message has no `TEST-CHANGE:` line, or the
  line is empty, a placeholder such as `n/a`, or under three words. The exit code is 1.
- **EXPLAINED**: the same kind of change, with a reason. The reason is printed, so a reviewer can read it.

Each row also says what the commit did: which test files it changed or deleted, whether it touched code,
and how many skip or expected-failure markers it added.

With `--net`, the script judges the range's combined change instead: one row for what the range as a whole
did to the tests that existed at its start, explained by a `TEST-CHANGE:` line in any of its commits. Use it
for a branch that will be merged as one piece, and to read what merge commits changed (the commit-by-commit
reading leaves merges out). A test weakened in one commit and put back in a later one reads clean in `--net`
and refused commit by commit, on purpose.

**What counts as a test**: a path in a folder such as `tests/`, `test/`, `__tests__/`, `spec/`, `fixtures/`
or `MyApp.Tests/`, or a file named like `test_x.py`, `x_test.go`, `x.test.js`, `x.spec.ts`, `x_spec.rb`,
`XTest.java` or `XTests.cs`. Case does not matter, except in the last two, which need the capital T so that
`latest.py` is not read as a test. **What counts as code**: any other file, except `.md`, `.txt` and `.rst`
documents. The summary line says how many file names could not be sorted at all; it should be 0.

Before its first check on a machine, the script runs its own self-test: a scratch git repository with one
commit per case, each verdict checked by name. If the checker stops seeing a test, the run says so in words
and stops, rather than printing a clean result it cannot back up. A passed self-test leaves a small marker
in the system's temp folder, named by a hash of the script, the Python version and git's version, so later
checks skip it until one of those changes.

It needs Python 3.8 or newer and git. It uses no packages.

## How to run it

From the project's folder:

```bash
python3 skills/test-freeze/scripts/test_freeze.py check --range main..HEAD
python3 skills/test-freeze/scripts/test_freeze.py check --range main..HEAD --net
python3 skills/test-freeze/scripts/test_freeze.py --self-test
```

On Windows, use `python` in place of `python3`. If the kit is installed for every project, the script is at
`~/.claude/skills/test-freeze/scripts/test_freeze.py` (on Windows,
`%USERPROFILE%\.claude\skills\test-freeze\scripts\test_freeze.py`); use that path instead.

Exit codes: 0 when every judged commit is explained, 1 when one is refused, 2 for a command it does not
understand, 78 when it cannot look: git is missing, the range does not read (a missing branch, or the folder
is not a git repository), or the range holds no commits. An empty range is refused rather than passed,
because it usually means BASE and HEAD were swapped.

The script writes nothing into the project, so there is nothing of its own to commit.

## What to do when a commit is refused

1. Read the commit's test diff first. Ask: is the old expectation wrong, or did the code stop meeting a real
   requirement? Either can be a true reason. "The test was failing" alone is not one.
2. If the change is right, amend the message (or, once the commit is shared, say so in the merge's message
   and check the range with `--net`) with a `TEST-CHANGE:` line that says what the old test got wrong.
3. If the change is wrong, put the test back and fix the code. A test that fails is information.
4. A reason is a sentence: at least three words, never a placeholder such as `n/a`, `fix` or `updated`. The
   script refuses those, and a person still reads the rest.

## Make it part of the suite

This skill proves its own refusals. To make it block work, add the check to the project's suite, the same
way the `gates` skill adds other checks: one command, a line in the ledger, and a note in the notes file that
says what the check reads and where its breaks are. Run it on the range a merge will bring in, not on the
whole history, because older commits were written before the rule existed.

## Limits, said plainly

- A test written inside a source file (Rust's `#[cfg(test)]` module, for example) is not recognized as a test.
  Move such tests into a test file, or extend the patterns at the top of the script.
- A renamed test file reads as a deleted file and an added file, so a rename needs a `TEST-CHANGE:` line.
- A document inside a test folder (`tests/README.md`) is read as a test, because fixtures there are often
  plain text.
- The skip-marker scan knows the common markers of pytest, unittest, Jest, Mocha, JUnit, NUnit, xUnit, Go and
  Rust. A marker it does not know is still judged, because it changes the test file; the row just does not
  name it.
- The script reads the message. It cannot tell whether the reason written there is true. A person reviewing
  the commit still has to read it.
- The patterns are short on purpose. Edit them to fit the project; the script does not guess.

---

Part of CorvusWing, created by Ron Brazil. MIT License.
