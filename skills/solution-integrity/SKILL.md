---
name: solution-integrity
description: Twelve questions to answer before, during and after any non-trivial change to a codebase that has grown big enough to hide its own defects. Use before writing a fix, adding a setting, tuning a value, restructuring code or acting on a measurement, and again before calling the work done. Also use when someone asks "should I build X", "is this the fix", "why does this keep coming back" or "let's add a setting for it", when a bug comes back in a new place, when a benchmark and the live app disagree, or when a result seems too good.
---

# Solution integrity: the questions that stop a fix from being a mask

A big codebase hides its own defects, and the ways it hides them are few and repeatable. Each
question below guards one of those ways. **The order is not the order these occur to you in.**
It is sorted by the cost of a mistake: a wrong answer at question 1 wastes a week; at question
10 it wastes an afternoon. Answer them in this order even when a later one feels more urgent.
**And answer them out loud, in the response.** An unstated answer is an assumption dressed as a
decision.

## The one technique under all of it: work backwards

Most of these questions are hard forwards and easy backwards. When the path from here is not
obvious, do not search forwards. State the finished thing and walk back:

> For this to be true at the end, X must be true just before it.
> For X, Y must hold. For Y, Z must already be solved.
> Z is something I can do today.

**Keep walking until you reach something you can do this afternoon.** If the chain never reaches
one, the problem is not the implementation. The goal has an unmet precondition nobody has named,
and finding it is worth more than any amount of forward effort. **Then walk it the other way, because that is where the traps are:** if I do Z, does Y really
follow? A chain that only works forwards is a plan. A chain that survives both directions is a
design.

## Part 1: Before you write anything (the cheapest place to be wrong)

### 1. What is the actual defect: the mechanism, not the symptom?

Name what is broken in terms of **what it does**, not what you observed. "Checkout fails for some
users" is a symptom. "The discount step divides by the item count, which is zero for gift cards"
is a mechanism. **The test: can you state the defect without mentioning the number that made you
notice it?** If not, you are about to fix the number.

**And before you name the mechanism, read to the `return`.** Then read the caller. A mechanism
named from the first six lines of a seven-line function is a guess with a confident caption.

> **Example:** a cleanup command is documented as "deletes old drafts". Six lines of its function
> were read. The seventh moves the drafts to an archive folder instead. The false description
> shipped.

**When a difference is between groups, take it apart before you build a setting for it.** "These
three customers need different timeouts" is not a mechanism. It is an observation with several
possible mechanisms under it. **Take the parts out one at a time.** The difference is made of
something, and it is often one component misbehaving, not the groups truly differing.

> **Example:** three customers' sync jobs seem to need three different timeout values, and a
> per-customer setting looks like the next step. Timing each step separately shows the whole
> difference is the image upload, which only one customer uses heavily. Fixing the upload lets one
> timeout serve all three. A per-customer setting would have been a number tuned to hide a slow
> step.

### 2. Has this been tried, and is the reason it was rejected still true?

Search the decision log, the plan, the code comments and any setting left switched off. **A
rejected idea was usually rejected for a reason that was correct at the time.**

**The second half of this question is the one people skip.** A rejection depends on the baseline
it was measured against. When something else changes, every earlier rejection becomes a *stale*
rejection, and nothing about a switched-off setting records when it was last checked. **So keep
a way to re-test every switched-off setting in one command.** If none exists, building it is
often cheaper than the thing you came to build.

> **Example:** a page cache was tried and rejected: "saves 5% on one page, costs 2% on another."
> Later an unrelated slow database query is fixed. Tried again, the same cache saves 40%. The
> slow query's noise had been hiding it.

### 3. Is the premise measured, or is it just what everybody believes?

**This is the highest-value question in the list and the easiest to skip, because the premise is
the part nobody is arguing about.** Before building the fix, **measure the thing the fix
assumes.** Not the fix: the assumption under it. **The move: write the probe that could cancel
the task, and run it first.** Give it a name that says so (`probe_could_cancel_dedup.py`). **A
probe that cannot cancel the task is not checking the premise; it is decorating it.**

> **Example:** the task is "add de-duplication to the import script, because duplicate rows slow
> it down." Counting first: the import files hold 12 duplicate rows in 200,000. The slowness is
> somewhere else. **A twenty-minute count canceled a week of work.**

**And the label is not the fact.** A premise is often an artifact's own description of itself: a
filename, a banner, a status field, a docstring. Count the lines. Run the thing. Make the status
field print the other value.

> **Example:** a file named `customers_full_export.csv` holds 500 rows, not the full list. A
> README badge says "tests passing" while the suite has not run in a month. A health check prints
> `OK` while the database is down. Each label gets quoted as evidence until somebody looks inside.

## Part 2: Designing

### 4. Work backwards from the finished solution

Apply the technique above, in writing. **State the end condition first**, then the chain of
preconditions, until you reach today. **The chain is also your test plan.** Every link is a
claim, and each one that can be checked cheaply should be checked before the next is built.

### 5. What else is this the answer to?

A real fix to a real mechanism usually fixes **more than the thing you noticed**, and the other
places are where the value is. **Ask: does anything else in this codebase have the same shape as
the defect I just found?** If one function trusted user input, do its neighbors? If one code path
missed a feature flag, which other paths have flags?

**And the inverse, which stops double-counting: if this fixes the same underlying fault as
something already built or measured, measure that thing again on the new baseline before writing
either number down.**

> **Example:** a retry wrapper cut failed requests by 30 in the morning. In the afternoon a
> different fix to the same flaky connection landed. Tested again on top of it, the retry
> wrapper was worth 2. Recording both numbers would claim an improvement that does not exist.

### 6. What is the better solution I am not considering?

**List at least one alternative you are rejecting, and say why.** A design with no rejected
alternatives has not been designed; it has been arrived at. Reach for these specifically:

- **Can this be fixed at a lower layer**, so the problem stops existing instead of being handled?
  The usual form: find **the one definition every call passes through** and guard it there.
  Guarding the callers one by one is the wrong altitude.
  > **Example:** four places that write log files get a size limit, and the disk still fills,
  > because the real writer is a fifth function on the main request path, one level down. The
  > limit belongs in the one function they all call.
- **Can it be a property of the data instead of a setting?** A solution with no tuned number is
  worth more than one with a tuned number, because a tuned number needs data to tune it on, and it
  gets tuned on whatever is handy.
- **Is the honest fix "remove it" instead of "improve it"?**

## Part 3: Before it ships

### 7. What does this break now?

Everything downstream of what you changed. **Including the numbers:** if a measurement runs
through what you changed, every number recorded through it is now history and must be labeled
that way, not silently replaced. **And including the documents:** every plan, state file and
caption that describes the thing you changed now describes the previous thing. No test catches
this. **Re-read what you wrote before you write the handoff.**

> **Example:** a plan still says "NOT BUILT" about a settings page that has been live for weeks,
> and a report's title promises ten fixes while its body describes four.

### 8. What will break later, and what do I put in now to stop it?

**A failure mode written down with its guard is worth more than one written down as a caveat.** A
caveat is a note for a person who will not be reading it. For each future failure you can name,
choose one **now**:

- a **check** that fails when it happens,
- a **loud refusal** at the point of use, or
- a **written decision** saying it was accepted and what it costs.
- Not "we'll deal with it when it happens". That is the caveat, and it is how a footnote becomes
  the biggest unmeasured problem in a project.

**A status field must be able to say the other thing, and a refusal must be a result.** Before
shipping any field that reports an outcome, write the input that makes it report the bad outcome
and confirm it does. A field that can only print one value is a claim dressed as a readout. And a
tool or check that cannot run must say so in words: a silent no-op looks exactly like a pass.

> **Example:** a backup script's upload step could not find its credentials, skipped itself
> without a word, and the script printed "Backup complete" every night for a month.

### 9. Who else computes this, and will they still agree tomorrow?

**This is the most frequent failure in large codebases, and it is almost invisible.** A formula
gets shared but one of its inputs does not. Or a fast path and a readable path both exist and
only one learns the new behavior. Ask, in order:

1. **Is there a second implementation?** A cached version, a batch version, a test double, a copy
   inside a report or a checker.
2. **Does the switch I just added reach all of them?** Check at a setting where the switch
   changes the answer; at the default, the paths agree by construction and prove nothing.
3. **Are the inputs the same?** Not the function: what is fed to it.
4. **Does the thing I measured match the thing that ships?** Same units, same data size, same
   preprocessing.
5. **What units does each value carry?** Cents or dollars, UTC or local time, bytes or kilobytes,
   raw or escaped text. **An output fed back in as an input with no stated conversion compares
   two units against each other**, and it looks like a poor result, not a broken one.

> **Example:** a billing job writes monthly totals in dollars; next month's run reads them back
> expecting cents. One line item comes out 100 times too small, and it looks like an odd
> discount, not a bug.
>
> **Example:** a feature flag is added to the normal code path but not the cached one, so every
> benchmark ignores it. Two screens compute "active users" two different ways. A benchmark runs on
> a 10-row table while the live tables hold 10 million rows, and the conclusion reverses at full
> size.

## Part 4: After it is built

### 10. Does it fail when it should?

**Break it on purpose, the way a future maintainer plausibly would**, and confirm the check
catches each break:

- **The tidy-up:** someone simplifies the clever line away.
- **The silent revert:** the behavior goes back to what it was, with the name kept.
- **The plausible alternative:** the version someone would write who had not read the reason.
- **The drift:** one of the two copies from question 9 stops matching.

**And confirm the break actually broke something.** A change that does nothing makes a working
check look broken, and the natural next move (loosening the check until it catches it) makes a
good check worse.

> **Example:** the tests caught every deliberate break but one: removing the call to the discount
> function from the checkout handler. The tests called the discount function directly, so they
> stayed green. They tested the function, not its caller.

### 11. Is my measurement of the fix the right measurement?

**A fix verified by the wrong comparison is unverified.** Four traps:

- **The baseline moved under you.** If your instrument reads the current configuration, then the
  moment your fix ships, its "before" row quietly becomes your fix. Pin the baseline to the
  unchanged version and say so in the output's header.
- **The denominator.** When comparing two versions on the same inputs, the evidence is the cases
  where they **disagreed**, not the cases tested. Two spam filters that agree on 950 of 1,000
  emails give 50 pieces of evidence, not 1,000. **Report both numbers, never one.**
- **The gain belongs to something else.** See question 5: measure again anything that aimed at
  the same fault.
- **The change scored well by not running.** **Print how often the new code actually did
  anything, beside the result**, and a "turned off entirely" row next to it. Otherwise a change
  that silences a component looks the same as one that improves it.

### 12. Is the claim the size of the evidence?

Write down what you now believe, and check each part against what was actually measured:

- **On what:** which data, which settings, which units.
- **Against what:** and was the comparison given its best shot, or a weak one?
- **How sure:** and does the number survive the checks in question 11?
- **What it does not say.** A finding stripped of its limits becomes a bigger claim every time it
  is repeated.

**And if it came out the wrong way, that is the result.** A record that holds only its
author's wins is an advertisement, and a reader learns to discount all of it, including the parts
that are true.

## The short version, for when there is no time

- **Before:** what is actually broken · was this rejected before, and is that still true · **is
  the premise measured or assumed**
- **During:** walk it backwards · what else does this fix · what am I not considering
- **Before shipping:** what breaks now · what breaks later, and what guard goes in today · **who
  else computes this**
- **After:** break it on purpose · **was that the right comparison** · is the claim the size
  of the evidence

**If you only ever ask three, ask 3, 9 and 11.** They cancel wasted work, catch defects nothing
else can see, and stop a false result from being recorded.

---

Part of CorvusWing. Created by Ron Brazil. MIT License.
