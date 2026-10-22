---
name: holding-the-goal
description: The questions to run before saying something is blocked, impossible, not worth it, or needs the owner's decision, and before giving up on a goal because one measurement refused one claim about it. Use whenever you are about to write "cannot", "blocked", "needs your decision", "not achievable" or "we should stop here", or to report a limitation. Also use when a measured difference is too small for anyone to notice but is being treated as a blocker, when your caution contradicts someone's unmeasured gut feeling, when you have found a limitation and only thought about removing it, when someone pushes back on a "no" ("is that even necessary", "why can't we", "that seems irrelevant"), and, in the other direction, before proposing to fix a defect nobody has seen cause harm.
---

# Holding the goal: before you say a thing cannot be done

Every question here comes from one repeating shape: an agent said "no", the person
who owned the project pushed back, and they turned out to be right. It repeats because the mistake is structural,
not careless. A careful engineer who measures honestly can still arrive at a false stop,
because **the measurement was about the method and the sentence was about the goal.**

This is not permission to be optimistic. It is a requirement to **name the limiter
precisely** before writing a sentence that closes a door.

---

## The one distinction the whole skill rests on

> **A refused claim and a refused goal are different sentences, and the second one closes a
> door the first never touched.**

Before writing "blocked", "cannot", "not worth it" or "your decision", say which of these you
actually established:

| What was measured | What it lets you write |
|---|---|
| One mechanism does not work | "That mechanism is refused." Nothing about the goal. |
| A number differs by an amount nobody can notice | "My chosen test cannot pass." Nothing about the work. |
| A property does not hold | "The property is absent." The goal may not need it. |
| The goal is unreachable by every route you listed | "I found no route." Not the same as none existing. |

---

## The six questions

Questions 1 to 5 guard against stopping too early. Question 6 guards against starting too
early. It comes last because it is the more comfortable failure: proposing work feels like
diligence.

### 1. Is the blocker big enough for anyone to notice, or only big enough for my test?

**This is the highest-yield question and the easiest to skip**, because the number is real
and you measured it honestly.

Write the number down in a unit a person can feel: two hundredths of a cent, a tenth of a
millisecond on a two-second page load. **Then ask whether anything downstream can tell.** If
nothing can, the blocker is not in the world. It is in the instrument you chose, and **the
instrument is yours to change.**

> **Example:** an agent moves a report script to a newer CSV library. The new output differs
> from the old only in number formatting: `1.5` where the old file had `1.50`. The agent
> reports "blocked: outputs do not match, needs your decision." Nothing that reads the file
> cares; the spreadsheet that opens it shows the same value. The byte-for-byte comparison was
> a tool the agent picked, not a requirement of the job. The accurate sentence was "my test
> needs changing", not "the work is blocked."

### 2. What is fixed and what is negotiable, and do I have them the right way around?

**The goal is fixed. The method, the test, the tolerance, the order of work and the schedule
are negotiable.** When a stop is being written, check which one is bending. If the goal is
bending to protect a method, it is backwards.

> **Example:** the owner says, "The app has to work offline. Tell me if you have a real reason
> it can't." That sentence sits at the right altitude, and it shows at once that the agent
> had been letting its choice of a sync library decide the scope of the project.

The inverse is a real answer too. If the goal truly cannot be reached, say so plainly, name
the limiter, and do not soften it. Holding a goal is not refusing to report a wall.

### 2b. When I offer two options and one is "change the thing we are copying", my own code is the option I forgot

This is question 2 in its most common disguise. The shape is always the same: something
upstream is hard to reproduce, and the agent writes:

> "Either we keep X, which I cannot match, or we change X, which makes it worse. Your call."

**Two options, and neither of them is the agent's own work.** The third, *reproduce X exactly
in my own implementation*, never gets written down, because the agent already decided how its
side works and stopped treating that decision as a decision.

> **Example:** a rewritten date parser disagrees with the old system on a few inputs. The
> agent reports that the old parser "uses a complex locale-aware algorithm", says matching it
> means pulling in a heavy dependency, and hands the choice to the owner. One probe shows the
> old parser is simple: it reads two-digit years below 50 as 2000s and the rest as 1900s. Ten
> lines in the new parser match it on every input. "Your call" becomes "identical output",
> and nothing got heavier.

Before writing any sentence that hands the owner a choice:

1. **Is my side written down as a choice, or as a fixed fact?** If my implementation shows up
   in the sentence as a given, that is the bug.
2. **Have I measured what the thing I cannot reproduce actually is?** "It is a careful
   algorithm" is a belief until a probe says otherwise.
3. **Is the difference in a quiet default instead of the logic?** Libraries carry defaults
   (rounding mode, time zone, locale, sort stability, text encoding) that make the same call
   behave two ways. Reproducible, just not guessable.

Only when all three come back "yes, and it still cannot be done" is a choice worth putting to
anybody. An option list with none of my own work in it is not a decision. It is a request to
approve my first idea.

### 3. Can the limitation be used instead of removed?

**A limitation is usually a measurement of something, and the thing it measures is often the
information you were missing.** Before writing "we would need to fix X", spend one paragraph
on: what is X telling me, and is that useful?

> **Example:** a test suite fails whenever the laptop is offline, and the report treats it as
> a nuisance to fix. But the failures are a free list: they name exactly the tests that reach
> the network. Using that list to split the suite into fast offline tests and slow online ones
> is a better design than the planned fix. The defect was the better design, dressed as a
> fault.

### 4. Does my caution contradict someone's gut feeling, and have I measured it?

Expert caution is usually right about what *could* go wrong and often wrong about what
*did*. When somebody's gut says "surely that is faster / simpler / possible" and your answer
is a careful "not necessarily", **that is a measurement waiting to be taken, not an argument
to be won.**

> **Example:** the agent says caching the product list will not make the page noticeably
> faster. The developer's gut says it will. Timed, the page goes from 1.2 seconds to 0.4.
> The agent's statement was defensible; its confidence was not.

### 5. If somebody pushes back on my "no", what is the best version of their case?

**Do not defend the stop. Build their argument for them and see whether it stands.** Pushback
on a "no" is information: either the sentence did not carry the reasoning, or the reasoning
was wrong. Both are worth finding out, and only one is comfortable.

**And know where this ends.** This skill is not "never stop". It is "stop for a real reason,
stated precisely". A stop is earned when:

- the limiter is **named**, not gestured at;
- it has been **measured**, not assumed;
- somebody could **check** it without repeating your work;
- and the sentence separates **what is refused** from **what is merely unreached**.

If all four hold, stop, and say so plainly. If any one is missing, you do not have a stop
yet. You have a feeling with a number attached.

---

## 6. The mirror: before saying "we should fix this", not only before saying "we cannot"

Everything above guards one direction: do not *stop* on reasoning alone. This guards the
other: do not *start* on reasoning alone. They are the same error with opposite signs, and
the second survives longer because proposing work feels like diligence.

> **A defect named from what something might do is not a defect. Measure what it does.**

The test is one sentence: **name the consumer, then go and read it.** "A caller that checks
the status code would be misled", with no file and line beside it, is a hypothetical dressed
as a finding. If the consumer cannot be named, the defect has not been found yet.

> **Example:** an agent reports that an API endpoint returns status 200 on an error, so "a
> caller checking the status would think it succeeded", and proposes a fix plus new tests.
> Reading the only caller: it never looks at the status. It reads a `success` field in the
> body, which is set correctly. The fix is canceled, and an afternoon of changes to working
> code is avoided.

### 6b. When a fix turns out to be unnecessary, ask what made it unnecessary

**This is where the real defect usually is.** A fix that proves redundant means *something
already handles it*, and that something is a mechanism you did not know about. **Find it,
name it, and check that every other place that needs it has it too.**

> **Example:** an agent proposes adding input checks to one form handler. Testing first shows
> bad input is already rejected before the handler runs, by a shared middleware (a function
> every request passes through). That middleware is the finding: the newer half of the app
> never registered it, so three other forms accept anything. Asking why the fix was not needed
> is what found it.

### 6c. A check that names its own blind spot is useless until somebody reads the line

**The hardest failure in this family, because nothing is broken anywhere.** A careful check
prints exactly what it cannot see. It goes green. The line scrolls past on every run, for
weeks, and the thing it named sits unexamined, protected by the very honesty that was supposed
to expose it.

> **Example:** a test run prints, every time, "refunds: 0 tests (no fixture contains a
> refund)". It is true, it is printed hundreds of times, and the refund code has no coverage
> at all. Two other modules in the same project hold the same shape: a constant with a comment
> saying what it will become "when the API is ready".

So the rule has a mechanical half, because a rule asking people to read more is not a rule:

1. **Every "not evidence" a check prints gets an expiry condition:** the input that would make
   it evidence, written beside it.
2. **Then something asserts that the condition is still unmet.** A blind spot that has quietly
   become reachable is worse than one that never was, because the note now reads as current.
3. **A constant whose comment says what it will become is the same defect in another
   costume.** "This will be real when X is built" is a caveat, and a caveat is a note for
   somebody who will not be reading. Give it a check or give it a refusal.

---

## The short version

**Before writing "cannot":** is the blocker's size something anyone can notice, or only my
test · is the goal bending to protect a method · is my own code the missing option · can the
limitation be used instead of removed · does my caution contradict a gut feeling I have not
measured · what is the best version of the case against me.

**Before writing "we should fix":** name the consumer and go read it · if the fix proves
unnecessary, find what made it unnecessary · read the line where a check names its own blind
spot, because nothing else will.

**A stop is earned when the limiter is named, measured, checkable, and separated from the
goal. A fix is earned the same way: by a consumer that can be named, not by a sentence that
sounds careful.**

---

Part of CorvusWing. Created by Ron Brazil. MIT License.
