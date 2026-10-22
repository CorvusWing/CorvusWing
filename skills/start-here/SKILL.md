---
name: start-here
description: First-run setup for a project worked on by AI coding agents. First keeps the original work safe (a sealed, fingerprint-checked snapshot and a clean working copy; the original folder is never touched again). Then interviews the developer one or two questions at a time, then writes the project's loop documents (STATE, HANDOFF, DECISIONS, PICKUP, FILEMAP, ORDER, REPORT, LESSONS) and an archive folder for finished work, house rules in AGENTS.md (with a CLAUDE.md that imports them), a git safety net, writes a PLAN from done backwards to today with the riskiest assumptions tested first, and ends by naming one small next task with a done-criterion and a cancel condition. Use the first time this kit is used in a project, or when someone says "start here", "set up the loop", "set up my project for agents" or "my agents keep drifting". Never builds anything in the same session.
---

# Start here

This skill sets up a project so AI agents can work on it without drifting. Before anything
else it keeps the developer's original work safe: a sealed snapshot, the original folder left
untouched, and a clean working copy where the loop is set up. Then it has four parts: ask, set
up, plan, name the first task. It does not build anything. The first real work happens in the
next session, on top of what this one puts in place.

Tell the developer that at the start, in about these words:

> First I'll keep your original work safe: I'll make a sealed snapshot of your project and a
> clean working copy, check that every file arrived, and leave your original folder exactly as
> it is. Then, in the working copy, I'll ask about ten short questions, one or two at a time,
> set up a few notes files, house rules for agents and a git safety net, write a plan with you
> from today to done, and suggest one small first task.
> I won't change any of your code today.

## Part 0: Look before asking (read only)

Spend a few tool calls getting oriented, so you do not ask what the project already says:

- List the project root. Note the language, the test folder, the build files.
- Run `git status` and `git log --oneline -5`, if it is a repository.
- Read README.md and any existing AGENTS.md or CLAUDE.md.
- Look for STATE.md, HANDOFF.md, DECISIONS.md or PICKUP.md. If they exist, this project
  was set up before: read them, then ask whether to refresh them or stop here.
- Look for the developer's own notes: a TODO list, a notes file, a plan or design document, a
  `docs/` folder. List them with one line each. Part 2 offers to bring their open items into the
  plan.
- Look for `SAFE-COPY.md` in the project root. If it is there, this folder IS the working copy
  and the original is already safe: read it, say in one line where the original and the
  snapshot are, and go straight to Part 1.

Change nothing in this part.

## Part 0b: Keep the original safe (once, before anything changes)

Nothing in this kit ever needs the developer's original folder to change. So the first thing
that happens is three places, each with one job:

| Place | What it is | Who touches it |
|---|---|---|
| **The original folder** | the project exactly as it was | nobody, from now on: not this skill, not any agent after it |
| **The snapshot** | a zip of the original, with a list of every file's size and fingerprint (a SHA-256 hash: a short code that changes if one byte of the file changes) | nobody; it is opened only to get something back |
| **The working copy** | a fresh copy of the original, where the loop is set up and all work happens from now on | the developer and the agents |

Say that in plain words first, then ask before each step.

1. **Ask where.** Suggest names beside the original: the working copy as `<project>-work`, and
   the snapshot in `<project>-originals/<project>-ORIGINAL-YYYY-MM-DD.zip`. Use the names the
   developer prefers.
2. **Measure first.** Count the original's files and total size, and read the disk's free space.
   If the copies will not fit with room to spare, stop and say so. List every folder over 100 MB
   and say which are rebuildable (`node_modules/`, `.venv/`, `build/`, `dist/`, `target/`,
   `__pycache__/`), with the command that rebuilds each (`npm install`,
   `pip install -r requirements.txt`).
3. **The snapshot holds everything** unless the developer says to leave a rebuildable folder out.
   Write the manifest (one line per file: its path, its size and its SHA-256) beside the zip.
4. **Prove the snapshot.** Open the zip, count its files and bytes, and check every fingerprint
   against the manifest. Say the result in numbers: "1,284 files, 212 MB, every fingerprint
   matches." Then make the zip and its manifest read-only (`attrib +R` on Windows,
   `chmod a-w` on Mac and Linux). A snapshot that was never checked is a hope, not a backup.
5. **Make the working copy** of everything, leaving out only the rebuildable folders the
   developer agreed to rebuild. Prove it the same way, by count and by fingerprint.
6. **Git.** If the original is a git repository, the working copy carries its history (the
   `.git` folder comes with it). If it pushes to a remote (GitHub or similar), say: from now on,
   commit and push only from the working copy, and never from the original; two folders pushing
   to one place will fight.
7. **Write `SAFE-COPY.md`** in the working copy: where the original is (untouched), where the
   snapshot and its manifest are, the date, the counts and fingerprint result, what was left out
   and how to rebuild it, and how to get anything back (unzip the snapshot, or copy from the
   original). It goes into the first commit.
8. **Tell the developer**, in a short block they can keep: the three places, the counts, and
   the one rule: "your original is safe; we work only in the working copy."
9. **Move to the working copy.** Ask the developer to open a new Claude Code session in the
   working copy and run `/start-here` again. It finds `SAFE-COPY.md` and starts at Part 1. Every
   later step of this skill works in the working copy, never in the original.

Rules for this part: copy, never move; never delete, rename or edit anything in the original;
never skip the proof; if any count or fingerprint disagrees, stop and say which file.

## Part 1: The questions

Ask one or two at a time. Use the AskUserQuestion tool if it is available; otherwise ask in
plain text and wait for the reply. Never send the whole list at once. Ten questions in one
message get skimmed; two at a time get real answers.

For each answer:

- Write it down in the developer's own words. Their goal in their words beats a tidy
  rewrite.
- If an answer is vague, ask one follow-up, not five.
- "I don't know" is a fine answer. Record "unknown"; it becomes a task later.
- Do not give advice yet. Collect first.

**Round 1**

1. What are you building, in one sentence?
2. What does "done" look like, and how would you know? Name a number or a behavior you
   could see. (Example: "a visitor can sign up and gets a welcome email", or "the import
   handles 10,000 rows in under a minute".)

**Round 2**

3. What is measured today, if anything? Tests, a timing, an error count, or nothing yet.
   ("Nothing yet" is common and fine.)

**Round 3**

4. Which AI agent tools do you use? How long do they usually run without you watching: a
   few minutes, an hour, overnight?
5. Is the project in git? Only on this machine, or also pushed somewhere (GitHub, GitLab, a
   server)? About how often do you commit?

**Round 4**

6. What went sideways most recently? Tell me the drift story: what you asked for, what the
   agent did, and what it cost you (time, money, code lost or thrown away).

   This one can be painful to tell. Thank them, acknowledge it in one sentence, and move
   on. It is the most useful answer in the interview: it tells you which rule to put first.

**Round 5**

7. What is your weekly budget for agent usage (money, or hours of plan usage)?
8. Which files or folders must an agent NEVER touch? (Examples: database migrations, the
   payment code, config files with secrets, generated files, a copied-in library.)

**Round 6**

9. How do you review an agent's changes today? (Read every diff, skim, run the tests, try
   the app, or honestly not much.)

Then read back a five-line summary of the answers and ask: "Is that accurate?" Fix what
they correct before going on.

## Part 2: Set up

First say what you are about to do, as a short list, and ask before doing it. The developer
owns this repository. Nothing below is destructive, but ask anyway.

### Step 1: The git safety net

Git is the undo button for agent work. Set it up so every change can be taken back.

- **Not a repository yet:**
  1. `git init`
  2. Write a `.gitignore` before the first commit: secrets and bulky output for the
     language, such as `.env`, `*.pem`, `*.key`, `node_modules/`, `__pycache__/`, `.venv/`,
     `dist/`, `build/`.
  3. Look for files that hold secrets (API keys, passwords, tokens). If you find any, add
     them to `.gitignore` and tell the developer the file names only. Never print a secret.
  4. `git add -A`, then show `git status` and let the developer look over the list.
  5. `git commit -m "Baseline before agent work"`
- **A repository with uncommitted changes:** do not commit them silently. Show
  `git status` and ask: commit them as "work in progress", stash them (`git stash`), or
  leave them and stop here.
- **A clean repository:** good. Note the current branch name.
- **Tag the starting point:** `git tag baseline`. A tag is a named bookmark on a commit;
  `git reset --hard baseline` can always get back here (it throws away anything not committed, so run `git status` first).
- **Explain the branch-per-task habit:** every task gets its own branch, made when the task
  starts (`git switch -c task/NEXT-01-short-name`). If the task goes badly, the branch is
  deleted and main never knew. Do not create the branch today. The next session does, when
  the task begins; write its name into ORDER.md.
- **If there is a remote** (a copy on GitHub or similar), say that pushing after each merge
  is a good off-machine backup. Local git alone is enough to recover from an agent.

### Step 2: Measure what exists (ask first)

If the project has tests, ask whether to run them once now. Record the result in STATE.md
as the baseline: how many pass, how many fail, the command, how long it took. A failing
test today is not a problem to fix today. It is a fact to write down.

If running the tests could touch anything real (send email, charge a card, write to a
shared database), do not run them. Write that in STATE.md instead.

### Step 3: The loop documents

The templates are in `templates/` next to this file. If they are missing, ask the developer
where they unpacked the kit. Create each document in the project root, filled with the
answers; PLAN, HANDOFF, ORDER and PICKUP get their route and task rows in Parts 3 and 4. Leave no field blank: write the answer, or "unknown" plus the HANDOFF id of the
task that will find out.

| File | Fill it with |
|---|---|
| STATE.md | Q1 goal, Q2 done-criterion, Q3 what is measured, the test baseline from Step 2, the never-touch list (Q8), the current branch and commit. |
| PLAN.md | The route from today to done (Part 3): the goal, the premises with their probes (riskiest first), the milestones written backwards, the first milestone's tasks, and what is not being done. |
| HANDOFF.md | The first task (Part 4) at the top, then the rest of the first milestone's tasks, copied from PLAN.md. Each gets an id, a done-criterion, a cancel condition and a size. |
| DECISIONS.md | DEC-001: adopt this loop, and why (from Q6). DEC-002: the never-touch list and the reason for each path. DEC-003: the weekly budget and the time cap for unattended runs. |
| PICKUP.md | The resume prompt for the next session, with the first task named. |
| FILEMAP.md | One row per top-level file and folder, plus a row for each loop document. |
| ORDER.md | The order for the first task (Part 4), filled in and ready to hand to an agent. |
| REPORT.md | A setup report: what is unknown or unmeasured (first), what changed today (files and git), the baseline number, what is open. |
| LESSONS.md | L-001 from the drift story (Q6): the rule, its mechanism, and what it cost. |
| archive/README.md | Copied from `templates/ARCHIVE-README.md`, with no rows yet. The `archive/` folder is where finished work goes, unchanged, each move leaving a pointer line (the session-close skill does it). |

Delete the "Example:" rows once real rows replace them.

**The developer's own notes** (found in Part 0), in the working copy: ask whether to bring
their open items into PLAN.md and HANDOFF.md. If yes, copy each item's text, naming the file it
came from. Then, with a yes, tidy the root: the loose notes files move, unchanged, into
`archive/original-notes/`, each with a row in `archive/README.md`, so the working copy's root
holds the code and the loop's notes and nothing else. They are copies; the originals sit safe in
the snapshot and the original folder. **Code stays exactly where it is**: moving source files
breaks imports and builds, so reorganizing code is a task in the plan, with an order, a branch
and a review, never part of setup.

### Step 4: AGENTS.md, the house rules (and CLAUDE.md, which imports them)

AGENTS.md is the rules file most coding agents read at the start of a session (Codex, Cursor,
Copilot, Gemini CLI, Aider and others). Claude Code reads CLAUDE.md instead, so CLAUDE.md's
first line is `@AGENTS.md`, which pulls the same rules in. One set of rules, every tool. If
the developer uses more than one agent tool (Q4), this is what makes them all follow the
same rules. Fill the AGENTS.md template (`templates/AGENTS.template.md`) from the answers:

- the goal and the done-criterion (Q1, Q2);
- the opener, word for word: the template's "Before any decision or code design" section,
  which has every task start with holding-the-goal whole, then the parts of
  solution-integrity and working-discipline it needs. Keep it as written; it is the habit
  the rest of the kit leans on;
- the never-touch list (Q8), path by path, each with its reason;
- the size budget per task. Start small: about 100 lines changed, or less if the drift
  story (Q6) involved huge diffs;
- the unattended time cap. If agents run unwatched for hours today (Q4), start at 30
  minutes with a written stop condition;
- the review rule, built from Q9. If the answer was "not much", the rule is
  `git diff --stat main...HEAD` before every merge, which takes ten seconds;
- the spending rule from Q7: what the agent does when half the week's budget is gone;
- the "Keeping the notes small" section as written: the read path's 400 KB budget, its 100 KB
  reservoir and 300 KB warning, and finished work moving into `archive/` with a pointer;
- one "learned the hard way" rule from the drift story (Q6), with its mechanism in one
  sentence. It also goes into LESSONS.md as L-001, with its story; AGENTS.md's list holds at
  most ten, and LESSONS.md holds them all.

Then write CLAUDE.md from `templates/CLAUDE.template.md`: the import line, and nothing else
yet. (The two templates carry `.template` in their names so that no agent tool mistakes them
for live rules while they sit in this skill's folder.)

If an AGENTS.md or CLAUDE.md already exists, do not overwrite it. Add a "Loop rules"
section to AGENTS.md (making the file if needed), make sure CLAUDE.md's first line is
`@AGENTS.md`, and show the developer the difference. Keep the whole file under about 80 lines; agents skim long rule
files the same way people do.

### Step 5: Optional fences

If the developer agrees, add permission deny rules for the never-touch paths in
`.claude/settings.json` (the scope-guard skill shows the shape). Explain that a deny rule is
a fence, not a lock, and that the real lock is looking at the diff before merging.

### Step 6: Hold the commit

Do not commit yet. The plan and the first task come next (Parts 3 and 4), and everything is
committed once, at the end of Part 4.

## Part 3: Write the plan, together

A project without a plan is a pile of tasks that each made sense on the day. This part writes
the route from today to done, so every task after this one has a place on it. Do it WITH the
developer: propose, ask, correct. It takes about fifteen minutes.

1. **Work backwards from done** (Q2). Ask: "For done to be true, what must be true just
   before it?" Write the answer as a milestone: a state anyone can check, never an activity
   ("a 10,000-row import finishes in under 5 seconds", not "work on the import"). Then ask
   the same of that milestone, and keep going until you reach today. Three to six milestones
   is usual; more than eight means the steps are too small or the goal is two projects.
2. **Read it forwards.** For each step: if this is true, does the next one really follow? A
   chain that only works backwards is a wish list. One that works both ways is a plan.
3. **List the premises, riskiest first.** A premise is something the whole plan assumes and
   nobody has measured: that the core idea works at all, that the data looks the way everyone
   thinks, that users want it. For each, write the cheapest probe that could prove it false,
   and the cancel line that would change the plan, written now, before the probe runs. The
   riskiest premise is the one that would sink the most milestones if it were false.
   > Example: "P-1: most imported files are under 10,000 rows. Probe: count the rows in last
   > month's uploads. Cancel line: if more than 10% pass 10,000 rows, the speed milestone
   > moves to first."
4. **Break only the first milestone into tasks.** Each gets an id, a done-criterion, a cancel
   condition and a size in sittings (one sitting is one focused session). Leave the later
   milestones as one line each; they will look different once the first is done. Estimates
   overshoot: size each task, then cut the estimate once.
5. **Write what is not being done, and why.** It stops an eager agent from "helpfully"
   starting it, and stops the same idea being argued again next week.
6. **Read the plan back** in five lines and ask: "Is this the route you want?" Fix what the
   developer corrects.

Write it into PLAN.md. HANDOFF.md holds only the next few tasks, copied from the plan: the
plan is the map, the handoff is today's directions.

## Part 4: Name the first task, and commit

The first task comes from the plan, in this order:

- **An untested premise comes first.** The first task is the riskiest premise's cheapest
  probe. Building on an untested premise is how months disappear.
- **If nothing is measured yet** (Q3), the first task is a measurement: one test that pins
  down the current behavior, or a script that prints the number "done" depends on. Without
  one, nobody can tell whether an agent helped or hurt.
- **Otherwise**, the first task of the first milestone.

It must fit in one sitting, inside the size budget, touching a handful of files at most.

Write it as:

- **Id and name:** NEXT-01 (a short description)
- **Done when:** a check anyone can run, and what it should print.
- **Cancel if:** the probe that could show the task is not needed, run before any building.
  (Example: "Cancel if the export already finishes 10,000 rows in under 5 seconds from the
  command line, because then the slowness is in the page, not the export.")
- **Files in scope** and a **size budget** in lines changed.

Put it at the top of HANDOFF.md, fill ORDER.md for it, and name it in PICKUP.md.

Then commit everything once: `git add` SAFE-COPY.md, the plan, the loop documents, LESSONS.md,
the `archive/` folder with its README.md, `.gitignore`, AGENTS.md and CLAUDE.md, then `git commit -m "Add plan, loop documents and house rules"`. Show
`git log --oneline -3`.

## Finish

End the session here. Do not start the task, even if it looks tiny. If the developer wants
to keep going, suggest a fresh session that begins by pasting PICKUP.md. A fresh session that
checks the notes before working is the loop doing its job.

Close with a plain summary in bullets:

- Where the original is safe: the original folder (untouched), the snapshot and its manifest,
  with the counts, and the working copy where all work happens now.
- What was set up: the files, the git commits, the `baseline` tag.
- The baseline number, if one was measured.
- The plan: each milestone in one line, and the riskiest premise with its probe.
- The first task, its done-criterion and its cancel condition.
- How to start next time: open Claude Code in the project and paste PICKUP.md.
- How to ask from now on: the opener in AGENTS.md (holding-the-goal whole, then the parts of
  solution-integrity and working-discipline the task needs), followed by the request.
- If the project has no single command that runs every check: the `gates` skill comes next,
  one part per session, before most feature work.
- To watch the project on one page (what is true, what is next, the tasks, the checks, and a
  box to leave the agent a message): the `bench` skill starts it on this machine.
- One sentence of encouragement that is true, not cheerleading. (Example: "The project now
  has an undo button, a route to done and a written next step, which is most of what was
  missing.")

## Rules for this skill

- Never build in the setup session.
- Never change, move or delete anything in the original folder or the snapshot.
- Never write a secret into any document, and never print one.
- Ask before any git command that changes the repository.
- Fill every field, or mark it unknown with the id of the task that will find out.
- Use the developer's own words for the goal and the drift story.
- Explain every term the first time it comes up: commit, branch, tag, diff, merge.

---

Part of CorvusWing. Created by Ron Brazil. MIT License.
