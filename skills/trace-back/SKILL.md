---
name: trace-back
description: Ariadne's thread for a surprising number. Before a count, score, benchmark or report is accepted, repeated or acted on, follow it back from the symptom in a fixed order -- reproduce it with the instrument that made it, rule out the test and the tool before blaming the product, read a random sample by eye, reconcile with whoever else computes it, ask the system why, deduce where the answer lives, and turn what is not known into the plan. Use whenever a number says something is missed, broken, slower, worse, better or surprising; before planning a fix for a finding you did not reproduce yourself; on "is it the test or the tool", "triage this", "why does it miss X", "is this real", "trace it back"; and before writing "might be noise" or any cause you have not read. It puts solution-integrity, working-discipline and holding-the-goal in an order; it replaces none of them.
---

# Trace back: follow the thread from the symptom

**The picture.** In the old story, the way out of the labyrinth was not a map. It was a thread tied at the
door. Here the door is the symptom you can see. The thread is a chain of "if this shows, then that must be
true", each knot checked before the next. And what you do not know yet tells you which way the thread runs.

**The problem.** A number arrives: "the search misses 30% of the matches", "the nightly job got 40%
slower", "the new model is 6 points better". The easy moves are all wrong. Accepting it starts a fix for
something that may be a measuring mistake. Rejecting it ("probably noise") hides a real defect behind a
guess. Scheduling "a check for later" and writing a plausible cause beside it feels like triage and is not.

**The rule.** A finding that arrives as a number is followed back in the order below, cheapest knot first,
before anyone accepts it, repeats it or plans its fix. Most of it is read-only and takes minutes.

---

## The thread, in order

### 1. Reproduce it with the instrument that made it

- Run the number again through the instrument's own code -- import its functions, never a copy you wrote
  (`working-discipline`, "measure the shipped function").
- **A number you cannot reproduce is a rumor.** Stop and say so. Nothing below is worth doing on it.

### 2. Rule out the test and the tool before blaming the product

Name every way the count could come from how it was measured, and split the count by each:

- **matching**: does the truth land on the right thing -- the right line, the right row, the right run?
- **the labels**: who made them, and how? Labels made by a program are claims too.
- **definitions**: does the yardstick's category mean what the system's does ("a title" against "a heading",
  "a failure" against "a retry")?
- **selection**: was the sample picked by the system's own uncertainty? Then weakness there is partly true
  by construction. Size it against the whole before calling it a weakness.
- **quirks**: empty items, duplicates, things neither side should count.

Then **read a random sample by eye**, its seed written down first (20 to 40 items), and state what share is
an artifact of the measurement -- and how unsure a sample that size leaves you.

**"It might be noise" is a guess with a caption until this step has a number beside it.**

### 3. Who else computes it, and do they agree?

Find a recorded result for the same thing, and the instrument that recorded it (`solution-integrity`, "who
else computes this").

- **Agreement** means the weakness is long-standing: newly measured, not a regression.
- **Disagreement** is the finding itself. Chase it before anything else.
- **A different measure on a different set** agrees with nothing and contradicts nothing. Say so, and
  convert one into the other's terms where the arithmetic allows.

### 4. Ask the system why

Most systems can explain a decision: an `explain` command, a debug log, a trace, the largest contributions
to a score. **Read it on the failures, a few of each kind.** The mechanism usually names itself.

Then read how the named fact is computed, all the way to its `return`. "The width pulls it down" is a
symptom. "The width is measured against the page, and on a two-column page that is one column" is a
mechanism.

### 5. Deduce from the symptom

The shape of the move: "It shows X. We miss X here. A simple reader that sees only Y gets it right. So Y
carries the answer, and the fix has to see Y, measured correctly."

- **A simple control that works is a map.** Whatever a stripped-down approach still gets right tells you
  where the signal lives.
- Then **work backwards** from the finished thing to the first knot you can check today. Each link is a
  claim and a test.
- **Before adding a part, check whether it already exists and is measuring wrong.** The fix is often to make
  an existing part's facts true, not to build a new one.

### 6. Two lists: what we know, what we do not

- **Known**: each fact with its number, the instrument that produced it and its conditions. The negatives
  too: a cause that was tested and ruled out.
- **Not known**: each unknown written as a question, with the probe that would answer it and the result
  that would cancel or resize the work.
- **The second list is the next step's plan.** An unknown with no probe beside it is a worry, not a question.

### 7. The correction plan

- **The goal is fixed; every method is negotiable** (`holding-the-goal`).
- **The yardstick before any candidate**: the scorer, the results that must not get worse, the pass marks
  written down first, a fresh set kept for the verdict, and a deliberately bad candidate the yardstick must
  reject -- proof that it can tell good from bad. For a piece nobody has designed yet, that is `bake-off`.
- **Candidates in the order of the measured causes**, each with its kill line written before it runs. A
  dead candidate stays dead.
- **The first step is always the probes from the "not known" list.**

### 8. Report it the size of the evidence

What is known, what is not, and what the sample cannot say -- the negative half included. **Never "we can
fix it" before a candidate has passed.** Say "likely, and why", or "not known".

---

## An example

A dashboard says the nightly import got 40% slower after a release. The thread:

1. The import's own timing script, run twice on the same machine, gives the same slowdown: reproduced.
2. The machine ran a backup during both new runs and during none of the old ones: the slowdown splits
   cleanly by "backup running". Two quiet re-runs show 6%, not 40%.
3. The release notes' own benchmark, on a quiet machine, recorded 5%: agreement. A small slowdown, already
   known.
4. The import's profile shows the extra time in one new validation pass.
5. Known: 6% on a quiet machine, from the validation pass. Not known: whether the backup clash happens every
   night (probe: a week of the scheduler's log).
6. The report: "about 6%, explained; the 40% was the backup; whether they clash nightly is not known yet."

No fix was planned for the 34 points that were never in the product.

---

## Where the thread ends

- A finding fully explained as an artifact (step 2), or as the recorded level of a trade already accepted
  (step 3), is a result. Say so and stop. That stop is earned the way `holding-the-goal` defines one: named,
  measured, checkable.
- The thread is followed in one sitting when the instrument is at hand. A knot that needs a long run goes
  into the plan as a probe, never into the triage.

## The short version

**Reproduce** with its own instrument · **rule out the test and the tool**, then read a random sample ·
**reconcile** with whoever else computes it · **ask the system why**, then read how that fact is computed ·
**deduce**: what a stripped-down approach gets right is where the answer lives · **two lists**, and the
unknowns become the plan · **the yardstick and a deliberately bad candidate** before any fix · **report it
the size of the evidence**.

---

Part of CorvusWing. Created by Ron Brazil. MIT License.
