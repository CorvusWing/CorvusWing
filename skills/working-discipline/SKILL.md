---
name: working-discipline
description: How to work inside a codebase that has history, covering the first ten minutes in any project, how to read code and measure without fooling yourself, how to spend tool calls, how to build, and how to report. Use at the start of every session in an existing project, before the first tool call in an unfamiliar codebase, before writing any probe, benchmark or measurement, before proposing an idea in a project that keeps a decision log, and before writing a handoff. Pairs with solution-integrity, which owns the questions before and after a specific change; this skill owns everything around the change. Use on "pick up where we left off", "continue the project", "measure this", "benchmark", "let's try", "why is this slow", or any session that begins by reading a state file.
---

# Working discipline: the habits around the change

`solution-integrity` asks the questions before and after a change. This is everything else:
how you arrive, how you read, how you measure, how you spend tool calls, how you build, how
you report. Most of the failures these habits prevent are a capable agent doing the natural
thing.

**The seam:** the moment you are about to change something other code depends on, stop and
run `solution-integrity`. Come back here to measure the change and to write it up. For the
edges of the task itself (scope, size budget, branches), see `scope-guard`.

---

## 1. The first ten minutes, in any project

1. **Find the loop documents before the code.** A project with history keeps a state file, a
   handoff, a decision log and plans (in this kit: PLAN.md, STATE.md, HANDOFF.md, DECISIONS.md,
   PICKUP.md). Read the state file, then the top item in the handoff. Read AGENTS.md (the house rules) once.
   **Do not open source code until you know what the last session found**, because it found
   something, and finding it cost money.
2. **Check the notes against the repository.** `git status`, `git log --oneline -3`, and one
   test whose result the notes state. Notes are a hypothesis about the repository, not a fact.
   If they disagree, the repository wins; say so before doing anything else.
3. **Run the fast checks, and read their output, not only the exit code.** A pass recorded
   against different file contents is not a pass. A failure with no saved output is not a
   failure either; it is an unknown.
4. **Start slow checks in the background now**, before reading anything else. A ten-minute
   suite started at the end of the session is ten minutes of waiting; started at the
   beginning, it is free. First check that nothing else holds what it needs (an old dev server
   still running, a database another script is using), because **a refusal is not a result**,
   and a suite that refused to start looks just like one that failed.
5. **Find or start the project's two tables.** A **file map** (which file holds what, so nobody
   reads a huge file to find a small function; in this kit, FILEMAP.md) and a
   **do-not-re-derive list** (what has been measured, decided or abandoned, with a pointer to
   where it is written; in this kit, DECISIONS.md). The first one you write pays for itself the
   same day.
6. **Say how much effort the task deserves**, out loud, before starting.

---

## 2. Reading

- **Search, then read the range, never whole files.** `grep -n` for the name, then read the
  lines around it. Batch the ranges you need into one call.
- **Read to the `return`. Then read the caller.** A function is what it returns and what its
  caller does with the result, not what its first six lines suggest.
- **The label is not the fact.** A filename, a banner, a docstring, a status string, a comment:
  each is a claim. Count the lines. Run it. A check that searches for a pattern will still find
  it in the comment that explains the code after the code itself is deleted. Strip comments
  before asserting.
- **Before writing any function, search for it.** If it exists, use it. If it exists twice,
  that is the defect you were about to make three of.
- **Name the units of every value** as you read: cents or dollars, seconds or milliseconds, UTC
  or local, raw or escaped. The costliest bugs are an output used as the next input with no
  conversion, and they look like a poor result, not a broken one.
- **Search the decision log and any switched-off settings before proposing an idea.** It has
  usually been tried. The reason it was rejected is worth reading, and so is whether that
  reason is still true.

---

## 3. Measuring

- **Write the probe that could cancel the task, and run it first.** Write its cancel condition
  *before* running it. A probe that cannot cancel anything is decoration.
- **Run the control before the claim**, especially when the result is the one you hoped for.
  > **Example:** a new sort order on a product page raises clicks by 8%. The control: a random
  > new order raises them by 7%, because anything new gets clicks for a week. The real gain is
  > 1%, inside the noise.
- **Every row prints its own inputs.** A total cannot be audited; a row showing the input, the
  expected value and the actual value can. A check that tests one thing while the rest is still
  broken will pass. **Measure after the system has settled**, and print what settled.
- **Two versions compared: the disagreements first, listed; the totals second.** Agreeing on 950
  of 1,000 is 50 pieces of evidence, not 1,000.
- **No number without its conditions:** how many, measured with what, against what baseline, in
  which mode. If the system changes itself while you measure (a cache warming up, a table
  growing), measure in a fixed state and say so.
- **The instrument before the number.** A measurement made by a script you throw away is one you
  will make again next month, slightly differently. Build the tool, name it, keep it in the
  repository, and make it print rows.
- **Held-out data, or it is the training set.** Anything tuned on the data and tested on the same
  data reports how well it memorized.
- **Measure the shipped function**, never a copy of it inside the probe. A probe that re-derives
  the arithmetic measures its own reimplementation.
- **If you cannot measure it, say so.**
  > **Example:** a test suite that replaces the payment API with a fake cannot verify the
  > payment API. Write that sentence, not the one you wish were true.

---

## 4. Spending tool calls

- **Batch every independent read into one message.** Five ranges in one turn cost one round
  trip.
- **Put anything over a minute in the background, at the start.** Do not poll it.
- **Do not spend a screenshot on what a script answers exactly.** Save the eye for the one
  question no script answers: does this look right to a person.
- **Run scripts from the directory the code expects.** A script with relative paths writes its
  output wherever you happen to stand.
- **Stop processes by process id, and confirm they are gone.** A stop that reports nothing and
  leaves the old dev server running means the next test talks to the old build.
- **Never hand-edit a generated file.** Find the generator and change that.
- **A new file gets its FILEMAP.md row in the same commit.** A description written later is
  written from the filename.

---

## 5. Building

- **One definition, and every caller goes through it.** A fast path and a readable path that
  both exist will drift apart; a switch that reaches only one of them measures nothing.
- **Widen a check by naming the new case, never by loosening the pattern.**
- **Start a loop or timer exactly once**, and assert the count.
  > **Example:** a polling timer started inside a function that runs on every page view adds
  > one more timer each time; after an hour the page polls forty times a second.
- **Every status must be able to say the other thing.** Before shipping it, write the input that
  makes it say the bad value.
- **A refusal is a first-class result**, in words, never a silent no-op.
- **Keep the old behavior behind a switch and measure it against the new.** Retire it by its
  number, not by taste.
- **Not a second date parser, config loader, import path or definition.** If the project has
  one, reuse it. Two that can disagree is the most frequent defect in a large codebase.
- **Verify a patch with the strictest check that can fail the way it fails.** A linter that
  accepts a misspelled variable name is not a test; starting the program is.

---

## 6. Reporting

- **Say which checks ran.** A skipped slow suite must never read as a pass.
- **The negative rows are the useful ones.** A record of only wins is an advertisement, and a
  reader learns to discount all of it.
- **Every change gets its gain on both axes:** against what it replaced, and against the
  ordinary standard, including when it goes the wrong way. A dashboard that shows fewer
  numbers because it stopped showing made-up placeholders is a gain; say why.
- **Re-read your own plan before writing the handoff.** No check catches stale documents. Mark
  what you saw working as built; mark what you did not verify as unverified.
- **Estimates overshoot.** Give sizes in sittings (one sitting is one focused session), and cut
  the first estimate once before writing it down.
- **End with the plain version**, in bullets, every term explained. Explain every reference in a
  clause, and put a short description in parentheses after any id: "NEXT-03 (the export
  timeout)", not a bare "NEXT-03".

---

## The short version

**Arrive:** loop documents first · check the notes against git · fast checks and their output ·
slow suite in the background now · the file map and the decision log · name the effort.

**Read:** search, then the range · to the return, then the caller · the label is not the fact ·
search before you write · name the units.

**Measure:** the probe that could cancel · control before claim · rows print inputs ·
disagreements first · conditions on every number · instrument before number · held-out data ·
the shipped function, not a copy.

**Spend:** batch reads · background early · scripts over screenshots · the expected directory ·
stop by process id · never hand-edit generated files · describe files as you create them.

**Build:** one definition · widen by naming · one loop, once · status can say the other thing ·
refusal is a result · old behind a switch.

**Report:** which checks ran · negative rows · both axes · re-read the plan · plain version last.

**Then, for the change itself: `solution-integrity`.**

---

Part of CorvusWing. Created by Ron Brazil. MIT License.
