---
name: compaction
description: Carry a long session across a context compaction (the automatic summary that frees up room, after which the agent works from the summary) without losing what cannot be worked out again. Commits first, compacts only at a seam, sorts what to carry by what it costs if the next session gets it wrong, keeps orders already carried out apart from rules still in force, ends with a flat manifest whose every line has a command that checks it, and makes the session on the other side test the note before trusting it. Writes PICKUP.md. Use when someone says "compact", "we're running out of context", "carry this across" or "write the pickup", when the context-guard skill's line is crossed, and at the end of every session (session-close runs it).
---

# Compaction: carry a session across the summary

A long session is eventually compacted: the conversation is summarized to free up room, and the
agent carries on from the summary. Stopping for the day loses the same things. Both lose them in
the same order: first the constraints, then the traps, then the exact numbers. The goal survives.
That is why an agent can come back from a compaction knowing what to build and having forgotten
what not to touch.

Two things make it worse than it sounds:

- **A summary compresses evenly, and what it holds is not evenly cheap to get back.** A file on
  disk costs one read to recover. A rule the developer said once, an hour ago, costs a mistake.
- **The worst case is not a lost fact. It is a fact worked out again, slightly differently.** A
  lost fact announces itself: the next session finds a hole and measures again. A number
  reconstructed a little wrong announces nothing, and sits in the notes looking exactly like the
  measured one.

This skill writes the note that crosses the gap, PICKUP.md, sorted by what each piece costs if it
comes out wrong, and makes the next session check it before trusting it.

## Part 1: Commit first

Before writing anything:

```bash
git status
git add -A                          # or add specific files, if some should not be committed
git commit -m "<what changed, with the numbers>"
```

The working tree is the largest block of state with no home on disk. A thousand uncommitted lines
become a paragraph in a summary; the same work committed is one hash. If the work is half done,
commit it on its task branch anyway, with "WIP:" (work in progress) at the start of the message.

## Part 2: Compact only at a seam

A seam is a point where:

- the working tree is clean (everything committed);
- a test has just been run and its result is known;
- no edit is half made.

Compacting in the middle of an edit means the summary describes a file that no longer matches the
disk. If you are mid-edit, finish it or undo it first. A session told it will run for hours picks
its seams in advance (after each task) instead of discovering one when the room is already gone.

## Part 3: Sort what to carry, by what it costs if wrong

Put each thing this session learned into one of these five kinds:

| Kind | How to carry it | Why |
|---|---|---|
| **Has a home on disk** (a file, a commit, a document) | Cite it by path or commit hash, with one clause saying what it is. Never copy it. | A copy is a second store of the same fact, and the two will drift. The file does not. |
| **Exact values** (ids, hashes, counts, timings, error messages, names of functions and fields) | Copy them character for character, each with its conditions: which command, on what data, at which commit. | A number without its conditions gets misquoted. A paraphrased error message cannot be searched for. |
| **Traps** (things that look fine and are not) | One sentence each, with the mechanism: "Tests fail while the dev server runs, because both use port 3000." | A rule without its reason gets broken by the first agent that thinks it knows better. A summary left to itself keeps the wins and drops these. |
| **Open state** (unfinished work, things running, questions waiting) | In full, each with an owner: the developer, the next session, or a named tool. | Open state is the one thing nobody can work out from the code. |
| **Narrative** (how we got here, what was tried in what order) | Compress hard. One line per dead end, with why it died. | The next session needs the dead ends, not the journey. |

**When room is short, cut in this order:** the narrative first, then the citations' clauses down to
bare paths, then the oldest traps. **Exact values and open state are never cut.** If they alone do
not fit, the compaction was left too late, and the fix is an earlier seam, not a cleverer note.

## Part 4: Two instruction sections, never one

This is the most important rule in the skill.

Every session gets instructions. Some were orders: do this once. Some were rules: always do this.
A note that mixes them causes the worst kind of drift: the next session reads "delete the old
export code" and does it again, on code that has been rewritten since.

So the note always keeps two separate sections:

- **Orders already carried out.** Past tense, with what was done and where: "Deleted the old CSV
  export in `src/export_old.py` (commit 4f2a9c1)." These are history. **They are never executed
  again.** If the next session thinks one needs doing again, it asks first.
- **Standing rules still in force.** Present tense, written as rules, each with when it was set and
  by whom: "Do not touch `db/migrations/` (the developer, at the start)." These apply to every
  future step.

When in doubt, it is a past order. A rule that was meant to stand will be repeated by the
developer; an order that is run twice can destroy work. A rule left inside a story gets read as
history, so a rule always goes in the rules section.

## Part 5: End with a flat, checkable manifest

The last part of the note is a list of facts the next session can check, one per line, each with
the command that checks it:

```text
MANIFEST
- branch: task/NEXT-02-csv-header          check: git branch --show-current
- last commit: 4f2a9c1 "Fix CSV header"    check: git log --oneline -1
- tree clean: yes                          check: git status --short   (prints nothing)
- tests: 86 pass, 0 fail                   check: pytest -q
- running: nothing                         check: no dev server expected
- next: NEXT-03 (export timeout)           check: top of HANDOFF.md
```

Flat means no nesting and no prose. Checkable means every line has a command whose output can be
compared with it. A count that carries its command and commit goes visibly stale; a bare count
looks current forever.

Its blind spot, said plainly: **a manifest catches a fact that was carried wrong, never a fact that
was not carried.** Nothing in it knows what is missing from it. That is what Parts 3 and 4 are for.

## Part 6: Write the note: PICKUP.md

PICKUP.md is the prompt the developer pastes into the next session. It is not a story of what
happened. It tells a fresh session what is true, what is decided, what is dangerous and what to do
first, in the order it needs them:

1. **The premise check** (Part 7), then the read order: AGENTS.md, STATE.md, HANDOFF.md.
2. **Off limits:** paths not to touch, actions not to take.
3. **Where we left off**, in two or three sentences, ending with the state it is in.
4. **The next task**, by id with a short description, its done-criterion and its cancel condition,
   and "STOP and report when done; do not start the next task."
5. **Orders already carried out** (past tense; never run again).
6. **Standing rules still in force**, including the rules this project learned the hard way, each
   with its mechanism in one sentence.
7. **What is running**, if anything: what it is, how it was started, how to stop it.
8. **The manifest** (Part 5), last.

Start it from the template (`templates/PICKUP.md` in the start-here skill's folder). Write it to be
read tired, late at night: short lines, the important thing first, no reference the reader has to
go and look up. If a line is merely true but would not change what the next session does, cut it.

Commit it, and print it in the response in **one fenced block**, alone in its fence, so it can be
copied in one action.

## Part 7: On the other side, a premise check before anything else

A summary is a hypothesis about the repository, not a fact about it. So the first thing the next
session does, before any other work, is test it:

```bash
git status
git log --oneline -3
<the one test whose number the note asserts>
```

If any of these disagrees with the note, the repository wins. The session says what differs, in a
sentence, before doing anything else. "Resume directly, do not recap" is right about tone and wrong
if it is read as "trust the summary". This instruction is the first thing in PICKUP.md so it cannot
be skipped.

## Finish

Say, in a plain line, whether it is safe to compact now. It is, if the tree is clean, PICKUP.md is
committed and its manifest is written. Then give the paste in its one fenced block.

## The short version

Commit first · compact only at a seam · cite what lives on disk, copy exact values with their
conditions, carry traps with their mechanism, carry open state in full with owners, compress the
story · cut the story first and never the values or the open state · past orders and standing rules
in separate sections · a flat manifest with a check on every line, which catches what was carried
wrong but never what was left out · PICKUP.md in one fenced block · the next session tests the note
before trusting it.

---

Part of CorvusWing. Created by Ron Brazil. MIT License.
