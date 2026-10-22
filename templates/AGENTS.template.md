# AGENTS.md: house rules for agents in this project

Purpose: the short list of rules every agent session reads first. AGENTS.md is the shared convention most coding agents read (Codex, Cursor, Copilot, Gemini CLI, Aider and others); Claude Code reads it through the import line at the top of CLAUDE.md, so one set of rules serves every tool. The start-here skill fills in the parts in angle brackets; keep the whole file under about 80 lines (ten lessons at most included), because long rule files get skimmed.

## The project

What we are building: <one sentence, in the developer's words>

Done looks like: <the number or behavior, and how to check it>

## Before any decision or code design (every task, every session)

Prior to any decisions or code design I want you to run the whole skill holding-the-goal, and then invoke the appropriate portions of the next two skills that allow you to successfully complete the task (name the parts you use of these two skills): solution-integrity, working-discipline.

The developer's request comes after this. If your tool has no skill command, open each skill's SKILL.md and follow it.

## Read first, every session

1. PICKUP.md (if you were given it), then STATE.md, then the top of HANDOFF.md. PLAN.md when choosing what comes next.
2. Check the notes against the repository: `git status`, `git log --oneline -3`, and the test command in STATE.md. If they disagree, say so before doing anything else.
3. If INBOX.md has messages marked `waiting` (the bench's Message Claude box writes them), read them now, act on them inside these rules, and change each `waiting` to `read HH:MM` or `answered HH:MM: <one line>`. Never delete one.

## Never touch

- <path> (<why>)

## How we work

1. One task at a time, from ORDER.md. When it is done, STOP and report. Do not start the next task.
2. Before any change: the tree is clean and committed, then a branch: `git switch -c task/<id>-<short-name>`.
3. Stay inside the files the order names. Need another file? STOP and ask first.
4. Do not refactor, clean up, modernize, rewrite, rename or reformat anything the order does not name.
5. Never delete, skip or weaken a test to make it pass. If a test looks wrong, stop and say why.
6. No new dependencies without asking.
7. Size budget: about <N> lines changed per task. Heading past twice that: STOP and report.
8. Before any run nobody will watch: a tag (`git tag before-<id>`), a written stop condition, and at most <M> minutes.
9. Spending: the weekly budget is <amount>. When half of it is gone, say so before starting a new task.

## Before saying "done", "blocked" or "we should fix this"

- "Done": run the done-criterion command and the quick gates, and paste their output. Before a merge, the whole suite, with its ledger read (the gates skill).
- "Blocked": name the limiter and how it was measured (see the holding-the-goal skill).
- "We should fix this": name the code that would be harmed, by file and line.

## How changes are reviewed

<from the interview, for example: `git diff --stat main...HEAD` first, then read the diff, then run the tests>

## Reports

Fill in REPORT.md before asking for a merge: negative results first, then what changed, the measurement, and what is open. End every reply with a plain summary in bullets, every term explained.

## Keeping the notes small

- The read path (AGENTS.md, CLAUDE.md, PICKUP.md, STATE.md and HANDOFF.md, read at every session start) stays under 400 KB together. Past 300 KB, archive what is finished at the next close. The 100 KB above 400 is a reservoir for the middle of a task only; every close ends back under 400 KB. Never fill room just because it is there.
- Finished work moves, unchanged, into `archive/`, leaving one pointer line (the session-close skill does it). Nothing is trimmed, summarized or deleted.

## Rules learned the hard way (the ten that matter most now)

One line each, with its mechanism. Every lesson, with its story, is in LESSONS.md: add it there first, and never delete from it. This list holds at most ten; when a new one belongs here, the least needed one leaves this list and stays in LESSONS.md.

- <rule from the drift story> (<why: the mechanism in one sentence>)
- Example: never run the formatter over the whole project during a task; it changed 3,000 lines and hid a 20-line fix.
