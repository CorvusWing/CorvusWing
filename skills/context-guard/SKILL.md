---
name: context-guard
description: Keeps an automatic compaction from ever taking unwritten work. The session reads its own context use (how full its conversation window is) at every commit and before every long run; at about 85% of the window it starts nothing new, commits, and runs the compaction skill and the session-close documents, so the note and the project's notes are current before any summary can happen. Use at every commit, before every report, before any run expected to take more than about ten minutes, at least once an hour in a long session the developer is not watching, and when someone says "how much context is left" or "guard the context".
---

# Context guard: the summary never takes unwritten work

When a conversation fills its window, Claude Code compacts it automatically: the conversation is
summarized and the session carries on from the summary. If that happens in the middle of a task,
the summary is written for the session, not by it: no seam, no manifest, no separate list of rules
still in force. Whatever the session knew and had not written down is now only as good as the
summary's guess.

The compaction skill writes a note that survives that. This skill makes sure the note is written
**before** the automatic summary can come, by watching one number.

## The reading: a number, never a guess

- **If the session has a tool that reports its own context use**, read it. (The Claude desktop app
  gives a session one that reports the tokens used, the window's size, and where the automatic
  compaction starts.) That is the number.
- **In a terminal**, the `/context` command shows the developer how full the window is. Ask the
  developer for the number at a seam if you cannot read it yourself.
- **If no reading is available at all**, say so once, in words, and then treat **every commit** as if
  the line below were crossed: the note and the documents current at each one. A missing reading
  is never a silent pass.
- **Never estimate the context from how long the conversation feels.** It is the one number this
  skill exists to read.

Read it at every commit, before every report, before starting any run expected to take more than
about ten minutes, and at least once an hour in a long session nobody is watching.

## The line: about 85% of the window

At 85%, the room left is enough for one careful note and its checks, and not enough for a long
run's output on top. With a window of 1,000,000 tokens, the line is 850,000; with 200,000, it is
170,000. If you know where the automatic compaction starts, keep the line at least a tenth of the
window below it.

At or past the line:

1. **Start nothing new.** A run already going keeps running; stopping a run that is making progress
   throws the progress away.
2. **Commit everything.** A "WIP:" commit if mid-step. Never leave edits uncommitted.
3. **Bring the notes current.** Run the session-close skill's document steps (STATE.md, PLAN.md,
   HANDOFF.md, DECISIONS.md, the archive and the read path's size), then the compaction skill, which
   writes PICKUP.md with its two instruction sections and its manifest.
4. **Tell the developer in one message**: the reading, the note's commit, and "safe to compact", with
   the paste in one fenced block.
5. **Then carry on with the work.** If the automatic compaction comes, the note carries the session
   across it, and the first act on the other side is the note's premise check, never a recap.

## Below the line

Nothing extra. The standing habit still holds: commit early and small, and bring the notes current
at every seam.

## The negative half, said plainly

- **Only the session can read its own context.** Another session, or a tool outside it, cannot see
  it cross the line, so this is each session's own duty.
- **85% is a starting line, not a measurement.** If a careful note at the line ever runs out of room,
  move the line down, and write the new line and the reason in DECISIONS.md.
- **The reading depends on the tool you run in.** Some clients show it to the agent and some only to
  the person. When only the person can see it, the guard works through them, or through the
  every-commit fallback above.

## The short version

Read the number at every commit · never guess it · at about 85% of the window start nothing new,
commit, bring the notes current, write PICKUP.md with the compaction skill, say "safe to compact"
with the paste in one block · no reading means every commit is treated as past the line.

---

Part of CorvusWing. Created by Ron Brazil. MIT License.
