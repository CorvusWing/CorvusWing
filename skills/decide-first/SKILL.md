---
name: decide-first
description: Makes a design question get a small, measured decision before any code is written. Use when a choice between designs, libraries, data shapes or approaches is open, when someone asks "should we build X", "is the slow part Y", or "which is better", or when an agent is about to start coding a design it has not measured. Ships one script, scripts/decide_first.py, that records the question, the cancel line, the measurement and the decision in that order, and refuses a record that breaks the order.
---

# Decide first: measure the design question before the code

**The problem.** A design question ("per user or shared cache?", "is the slow part the parser or the
disk?") can be answered with a plausible story in a minute. Building the wrong answer takes days, and the
story is then hard to test, because the code now exists and everyone has a stake in it.

**The rule.** Before any code for an open design question:

1. **Open** the question, and write the **cancel line**: the result that would make the answer "no". Write it
   before measuring, so the result cannot be bent to fit the answer you wanted.
2. **Probe**: run the smallest measurement that could show the cancel line is met. Keep its output.
3. **Decide**: read the output, say whether the cancel line was met, and choose: `build`, `stop`, or `other`
   (explain `other`). Give the reason in a sentence.

If the cancel line was met, the choice is `stop` (or a different question). Building anyway is the mistake this
rule exists to catch.

Only after that is the code written, and the commit message points at the decision record.

## What the script does

`scripts/decide_first.py` keeps one JSON record per question in `decisions/<name>.json`. It has four commands:

- `open <name> --question "..." --cancel "..."`
- `probe <name> -- <command>` runs the measurement and keeps its exit code and output (up to 4,000 characters).
- `decide <name> --cancel-met yes|no --choice build|stop|other --because "..."`
- `check <name>` reads the record and prints any reason it is out of order. Exit 0 means in order; exit 1 means
  refused, with each reason in words.

`check` refuses a record when:

- the question, or the cancel line, is missing;
- the cancel line was written at or after the measurement;
- nothing was measured, or the measurement kept no output;
- the decision has no valid choice, or no reason;
- the cancel line was met and the choice is not `stop`;
- the decision is not after the measurement.

The script runs its own self-test first, with one scratch record per case. It needs Python 3.8 or newer, and
uses no packages.

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

On Windows, use `python` in place of `python3`.

## Rules of thumb for the probe

- Make it the smallest thing that can prove the cancel line met. A probe that takes a week is a design, not a
  probe.
- Run it on real or representative data, and say which data in the `--because` text.
- Keep the command. Someone should be able to run it again and get the same output.
- Do not run it twice and keep the better result. If the first run was wrong, say why, and record the second
  run as the probe instead.

## Limits, said plainly

- The script checks the order and the wording of the record. It cannot tell whether the measurement was honest.
  A reviewer still has to read the probe output.
- The cancel line is only as good as the person who writes it. A vague cancel line ("if it is slow") makes the
  rule useless, so write one with a number or a clear yes-or-no.
- A question with no way to measure it is not a decide-first question. Break it into a smaller one that can be
  measured, or decide it by someone who has the authority and says so.
