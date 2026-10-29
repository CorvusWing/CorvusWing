---
name: decide-first
description: Makes a design question get a small, measured decision before any code is written. Use when a choice between designs, libraries, data shapes or approaches is open, when someone asks "should we build X", "is the slow part Y", or "which is better", when a plan's premise needs its probe run, or when an agent is about to start coding a design it has not measured. Ships one script, scripts/decide_first.py, that records the question, the cancel line, the measurement and the decision in that order, and refuses a record that breaks the order.
---

# Decide first: measure the design question before the code

**The problem.** A design question ("per user or shared cache?", "is the slow part the parser or the
disk?") can be answered with a plausible story in a minute. Building the wrong answer takes days, and the
story is then hard to test, because the code now exists and everyone has a stake in it.

**The rule.** Before any code for an open design question:

1. **Open** the question, and write the **cancel line**: the result that would make the answer "no". Write it
   before measuring, so the result cannot be bent to fit the answer you wanted.
2. **Probe**: run the smallest measurement that could show the cancel line is met. Keep its output.
3. **Decide**: read the output, say whether the cancel line was met, and choose:
   - `build`: the cancel line was not met, and the design goes ahead;
   - `stop`: the design does not go ahead;
   - `other`: neither as asked, for example build a smaller version or defer it; the reason says which.

   Give the reason in a sentence.

**If the cancel line was met, the choice is `stop`.** Building anyway, or calling it `other`, is the mistake
this rule exists to catch. A different question is a new record, opened with its own cancel line.

Only after that is the code written, and the commit message points at the decision record.

This is the tool behind the premise rows of a plan (`templates/PLAN.md`): each premise's probe and cancel line
can be a decide-first record, and its name goes in the row's status column.

## What the script does

`scripts/decide_first.py` keeps one JSON record per question in `decisions/<name>.json`. A name is lowercase
letters, digits, `.`, `_` and `-`, starting with a letter or digit, so a record cannot be written outside
`decisions/`. Four commands:

- `open <name> --question "..." --cancel "..."`
- `probe <name> -- <command>` runs the measurement and keeps its exit code and output (up to 4,000 characters).
  Probes are kept as a list. A second probe is refused unless it says why with `--rerun-because "..."`, and the
  first stays in the record beside it. A probe after the decision is refused.
- `decide <name> --cancel-met yes|no --choice build|stop|other --because "..."` writes the decision once. If the
  probe it reads exited with an error, it is refused unless `--probe-failed-ok "..."` says why that exit is the
  measurement (a probe that exits 1 when the cancel line is met, for example). A decision that would leave the
  record out of order is refused and not written.
- `check <name>` reads the record and prints any reason it is out of order. Exit 0 means in order; exit 1 means
  refused, with each reason in words.

`check` refuses a record when:

- the question, or the cancel line, is missing;
- the cancel line was not written before the first probe;
- nothing was measured, or the probe the decision reads kept no output;
- a second probe gives no reason for being run;
- the probe the decision reads exited with an error, and the decision does not say why that is acceptable;
- the decision has no valid choice, or no reason, or a placeholder for one (`n/a`, `measured`, under three words);
- it is not written whether the cancel line was met, or the cancel line was met and the choice is not `stop`;
- the decision is not after the measurement.

Each step stores its time and a sequence number. The order is read from the sequence numbers, so two steps
inside one tick of a coarse clock still read in order; a time that runs backwards is refused. A time written
with a trailing `Z` reads as UTC.

Before its first command on a machine, the script runs its own self-test: sixteen cases on a fixed clock, each
checked by name. A passed self-test leaves a small marker in the system's temp folder, named by a hash of the
script and the Python version, so later commands skip it until one of those changes. It needs Python 3.8 or
newer, and uses no packages.

Exit codes: 0 in order (or recorded), 1 refused, 2 bad use of the command, 78 a record cannot be read or
written, or the probe's program cannot be started.

## A worked example

```bash
python3 skills/decide-first/scripts/decide_first.py open cache-scope \
    --question "Per user or shared cache?" \
    --cancel "A shared cache loses more than 5% hit rate"
python3 skills/decide-first/scripts/decide_first.py probe cache-scope -- python3 measure_hit_rate.py
python3 skills/decide-first/scripts/decide_first.py decide cache-scope --cancel-met no --choice build \
    --because "The shared cache holds 97% hit rate on the sample; the cancel line is not met"
python3 skills/decide-first/scripts/decide_first.py check cache-scope
```

On Windows, use `python` in place of `python3`; a probe's program is found the way the shell would find it, so
`npm` or `pytest` work without their extension. If the kit is installed for every project, the script is at
`~/.claude/skills/decide-first/scripts/decide_first.py` (on Windows,
`%USERPROFILE%\.claude\skills\decide-first\scripts\decide_first.py`); use that path instead.

**Commit `decisions/`** with the code it led to. The record is what the commit message points at, and a
reviewer reads the probe's output there.

## Rules of thumb for the probe

- Make it the smallest thing that can prove the cancel line met. A probe that takes a week is a design, not a
  probe.
- Run it on real or representative data, and say which data in the `--because` text.
- Keep the command. Someone should be able to run it again and get the same output.
- Do not run it twice and keep the better result. If the first run was wrong, say why with `--rerun-because`;
  the first run stays in the record.

## Limits, said plainly

- The script checks the order and the wording of the record. It cannot tell whether the measurement was honest.
  A reviewer still has to read the probe output.
- The record is a plain file. Someone who edits it by hand can change its times and sequence numbers; the check
  reads what is there.
- The cancel line is only as good as the person who writes it. A vague cancel line ("if it is slow") makes the
  rule useless, so write one with a number or a clear yes-or-no.
- A question with no way to measure it is not a decide-first question. Break it into a smaller one that can be
  measured, or have it decided by someone who has the authority and says so.

---

Part of CorvusWing. Created by Ron Brazil. MIT License.
