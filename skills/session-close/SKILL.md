---
name: session-close
description: Close a working session so the next one loses nothing. Commits first, updates STATE.md, PLAN.md, HANDOFF.md, DECISIONS.md, FILEMAP.md and REPORT.md, moves finished work into archive/ with a pointer line, keeps the files read at every session start under a 400 KB budget, and ends by running the compaction skill, which writes PICKUP.md (the paste that resumes the work) with its two instruction sections and a checkable manifest. Use at the end of any real session, and when someone says "wrap up", "close the session", "we're done for now" or "update the notes". Also use unprompted when a session has produced findings or unfinished work that a fresh session would otherwise have to rediscover.
---

# Session close

A session ends in one of two ways: you stop for the day, or the conversation grows long and is
compacted (summarized to free up room, after which the agent works from the summary). Both lose the
same things, in the same order: first the constraints, then the traps, then the exact numbers.

This skill brings the project's notes current, so they say what is true now, and then hands over to
the compaction skill, which writes the note that carries the session across: PICKUP.md. The
compaction skill is the one place that says how that note is written; this skill never repeats it.

## Step 1: Commit first

Before writing any notes:

```bash
git status
git add -A                          # or add specific files, if some should not be committed
git commit -m "<what changed, with the numbers>"
```

A commit message is the only record that travels with the code. Put the measurement in it:
"Export timeout fixed: 10,000 rows in 3.1 s (was 41 s); 86 tests pass."

If the work is half done, commit it on its task branch anyway, with "WIP:" (work in progress) at
the start of the message. Uncommitted work is the first thing a crash, a mistyped command or an
agent's cleanup destroys.

## Step 2: Update the loop documents

If a document does not exist yet, start it from the templates in the start-here skill's
`templates/` folder.

- **STATE.md:** rewrite it to what is true now, present tense only. A plain finished to-do just goes
  (PLAN.md already has its date and commit). A fact that has become history but still explains
  something moves to the archive first (Step 2b). Update the test numbers, with their conditions.
- **PLAN.md:** give every task that finished its date and commit hash. If a probe failed or the route
  changed, add the DECISIONS.md entry first, then edit the route; a dropped milestone stays as a row
  marked "dropped (DEC-00N)". When a milestone is done, break the next one into tasks.
- **HANDOFF.md:** rewrite it from PLAN.md; do not append. Take out finished items. Every remaining
  item keeps or gets an id, a done-criterion and a size. The next task goes at the top.
- **DECISIONS.md:** append each decision made this session: id, date, decision, why, what was
  rejected, and the cost of reversing it. Never edit an old entry; add a new one that supersedes it.
- **FILEMAP.md:** a row for every new file; remove the row of every deleted file.
- **REPORT.md:** if a task finished, make sure its report is filled in: negative results first, what
  changed, the measurement, what is still open.
- **INBOX.md** (if the bench is in use): every message marked `waiting` is either answered now or
  carried into PICKUP.md's open state with an owner.

## Step 2b: Archive what is finished, with a pointer

Notes that only ever grow get skimmed, and then they stop protecting anything. So finished work moves
out of the working notes into `archive/`, and leaves one line behind saying where it went. An agent
that needs the detail follows the pointer; one that does not reads one line instead of a page.

What moves, and when:

| When | What moves | To | The pointer left behind |
|---|---|---|---|
| A task finished this session | ORDER.md and REPORT.md as they stand (then the next task starts both fresh from the templates) | `archive/tasks/<id>-<short-name>/` | the task's row in PLAN.md: date, commit hash, and that folder |
| A milestone finished | its task rows in PLAN.md | `archive/plan/<milestone>-<short-name>.md` | the milestone's row: "done YYYY-MM-DD, commit <hash>, tasks in archive/plan/..." |
| A fact in STATE.md became history but still explains something | that fact, word for word | `archive/state/YYYY-MM-DD.md` | the line at the bottom of STATE.md naming `archive/state/` |
| DECISIONS.md passed 100 KB | its oldest entries, enough to bring it back near 50 KB | `archive/decisions/DEC-<first>-to-DEC-<last>.md` | the "Archived:" line at the top of DECISIONS.md, one range per file |
| A lesson left AGENTS.md's short list | nothing moves: it is already in LESSONS.md | | AGENTS.md's pointer to LESSONS.md |

The rules, every time:

1. **Move, never trim.** The words and numbers arrive in the archive exactly as they left. Nothing is
   summarized on the way, and nothing in `archive/` is ever deleted.
2. **One pointer line per move**, in the place the piece left.
3. **A row in `archive/README.md`** for every new archive file: what it holds, where it came from, and
   when to open it.
4. **The move and its pointer go in the same commit**, so they can never disagree.
5. **Only what is finished moves.** Open work, standing rules and traps stay where they are, however
   long the file gets.

## Step 2c: Check the read path's size

The read path is what every session reads before it does anything: AGENTS.md, CLAUDE.md, PICKUP.md,
STATE.md and HANDOFF.md. Every session pays for it, so it has a budget: **400 KB together, with a
100 KB reservoir above it, and a soft warning at 300 KB.**

Measure it:

```bash
wc -c AGENTS.md CLAUDE.md PICKUP.md STATE.md HANDOFF.md
```

On Windows PowerShell:

```powershell
(Get-Item AGENTS.md,CLAUDE.md,PICKUP.md,STATE.md,HANDOFF.md | Measure-Object Length -Sum).Sum
```

Then:

- **Under 300 KB:** fine. Say the number in the close.
- **300 to 400 KB:** archive what is finished in those files now (Step 2b), and say what moved.
- **400 to 500 KB, the reservoir:** allowed only in the middle of a task. This close does not end until
  the read path is back under 400 KB.
- **Over 500 KB:** stop. Archive before any other work, and tell the developer which file grew and why.

Never fill room just because it is there. A small read path is the point; the budget is the ceiling,
not the target.

Then commit the documents: `git commit -m "Session close: update loop documents"`.

## Step 3: Write PICKUP.md with the compaction skill

Run the compaction skill now. It sorts what this session learned by what it costs if the next session
gets it wrong, keeps orders already carried out apart from rules still in force, ends with a flat
manifest that has a check on every line, puts the premise check at the top, commits PICKUP.md, and
prints it in one fenced block so it can be copied in one action.

## Finish

End the response with a plain summary in bullets:

- What was committed, with the commit hash.
- Which documents were updated, and what moved to the archive (or "nothing finished to archive").
- The read path's size in KB, against the 400 KB budget.
- The next task, by id with a short description.
- Anything left running, or "nothing running".
- Whether it is safe to compact or close now. It is, if the tree is clean and PICKUP.md and its
  manifest are committed.

## The short version

Commit first · update STATE, PLAN, HANDOFF, DECISIONS, FILEMAP and REPORT (and answer or carry the
inbox) · move what is finished into archive/, unchanged, one pointer line each · the read path under
400 KB (warn at 300, reservoir to 500 mid-task only) · then the compaction skill writes, commits and
prints PICKUP.md.

---

Part of CorvusWing. Created by Ron Brazil. MIT License.
