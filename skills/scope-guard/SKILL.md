---
name: scope-guard
description: The rules that keep an AI coding agent from rewriting code nobody asked it to touch, and the git commands that make any agent run reversible. Use before handing any task to an agent, before any unattended or long run, before merging an agent's work, when a diff is much bigger than expected, and when work needs to be undone. Also use whenever an agent proposes to "refactor", "clean up", "modernize", "simplify" or "rewrite" something it was not ordered to.
---

# Scope guard

An agent that rewrites half a codebase is not malicious, and usually not even careless. It
is doing what an eager helper does with a vague order and no edge. This skill gives every
task an edge, and makes going past it cheap to catch and cheap to undo.

Three ideas carry the whole thing:

1. **Every task has a written edge:** the files it may touch, and roughly how many lines it
   may change.
2. **Every task is reversible:** a commit before, a branch during, a tag before any
   unattended run.
3. **Size is checked before content:** `git diff --stat` first. A change far over budget is
   rejected without being read.

## Why agents drift

- **Long unsupervised runs.** Each step builds on the last. A small misreading in minute
  five becomes a rewrite by minute sixty, and every step in between looked reasonable.
- **Vague orders.** "Fix the login" has no edge, so the agent picks one. Its edge is usually
  bigger than yours.
- **No stop condition.** An agent with no written "done" keeps finding things to do. Most of
  them are things you did not want.
- **Summaries that lose state.** When a long session is compacted (summarized to free up
  room), the goal usually survives and the constraints often do not. "Do not touch the
  billing code" is exactly the kind of line that falls out.
- **Fixing a symptom by rewriting the module.** A test fails; the agent rewrites the module
  until it passes. The bug may still be there, and everything around it is new.
- **"While I'm here."** One rename, one tidy-up, one updated dependency. Each is small.
  Together they make a diff nobody can review.

Every rule below closes one of these.

## Before any task

**1. Commit, then branch.**

```bash
git status                          # must be clean: commit or stash first
git switch main                     # or whatever your main branch is called
git switch -c task/NEXT-01-export-timeout
```

A branch is a separate line of commits. If the task goes badly, you delete the branch and
main is untouched.

**2. Write the order.** Fill in ORDER.md (template in the start-here skill's `templates/`
folder). The parts that matter most here:

- **Files in scope**, by path. Add "and new test files under `tests/`" if new tests are
  expected.
- **Size budget** in lines changed. A rough guide: a bug fix, 10 to 50; a small feature, 50
  to 200. Anything bigger is two tasks.
- **Done-criterion:** a command, and what it should print.
- **Stop and report conditions**, ending with: "STOP and report when done. Do not start the
  next task."

**3. Plan first for anything big.** If a task is near its budget or touches more than about
three files, ask for a plan before any edit. In Claude Code, plan mode makes the agent
propose a plan and change nothing until you approve it. Press Shift+Tab to cycle to it, or
start with `claude --permission-mode plan`. Approve the plan only if its file list matches
the order.

## While the agent works

**4. Out of scope means stop and ask.** Put this sentence in every order:

> If you need to change any file not listed in scope, STOP and ask. Say which file, why,
> and roughly how many lines. Do not change it first and explain later.

**5. These words are off limits unless the order uses them:** refactor, clean up,
modernize, rewrite, simplify, reorganize, rename, reformat, upgrade. An agent that wants to
do one of these may suggest it in its report, as a future task with its own order.

Watch reformatting in particular. A formatter run over a whole file changes every line, and
the real change disappears inside it.

**6. Never delete, skip or weaken a test to make it pass.** That includes loosening an
assertion, marking a test as expected to fail, and changing an expected value to match new
output. If a test looks wrong, the agent stops and says why. You decide.

**7. No new dependencies without asking.** A new library is a change to the whole project,
not to one file.

## Before merging

**8. Size first.**

```bash
git diff --stat main...HEAD         # files touched and lines changed on this branch
git diff --shortstat main...HEAD    # one-line total
```

Compare it with the budget and with the scope list.

**9. Far over budget means reject it unread.** If the budget was 50 lines and the stat says
900, do not read the 900. Reading it costs more than redoing the task, and a review of 900
lines is mostly a skim anyway. Throw the branch away, make the order smaller or sharper,
and run it again. A fair line: more than twice the budget, reject. Between one and two
times, read it carefully and ask why.

**10. Files out of scope get put back.** If the stat lists a file outside scope and the rest
looks fine:

```bash
git restore --source=main --staged --worktree -- path/to/out-of-scope-file
git commit -m "Put back out-of-scope file"
```

If that file is new on this branch, `git rm path/to/file` instead.

**11. Then read it, test it, report it, merge it.**

```bash
git diff main...HEAD                # read the change itself
<the done-criterion command>        # run the tests
git switch main
git merge --no-ff task/NEXT-01-export-timeout
git branch -d task/NEXT-01-export-timeout
```

Fill in REPORT.md before the merge, not after. A report written after the merge is written
from memory.

## Unattended runs

An unattended run is any time the agent works while you are not watching each step: a long
task, an overnight run, a script that calls the agent in a loop.

**12. Tag before you leave.** `git tag before-NEXT-01`. Coming back to a mess is then one
command away from coming back to where you were.

**13. Write the stop condition and the caps before starting.**

- **Stop condition:** "Stop when `pytest tests/test_export.py` passes, or after 3 failed
  attempts at the same test, or if any file outside scope needs changing."
- **Time cap:** a number of minutes. Start at 30. Raise it only after several runs that
  stayed in scope.
- **Budget cap:** a spend limit or a turn limit. Claude Code's print mode
  (`claude -p "..."`) accepts `--max-turns`. Check `/cost` or your plan's usage page
  afterward, and write the number in REPORT.md.

**14. Fence the protected paths.** Claude Code supports permission deny rules in
`.claude/settings.json` (one project) or `~/.claude/settings.json` (all projects). For
example:

```json
{
  "permissions": {
    "deny": [
      "Edit(./db/migrations/**)",
      "Edit(./.env)",
      "Read(./.env)",
      "Bash(git push:*)"
    ]
  }
}
```

The pattern syntax can change between versions; run `/permissions` inside Claude Code to see
what it accepted. A deny rule is a fence, not a lock: a shell command could still change a
fenced file. The lock is step 8.

## How to roll back

| Situation | Command |
|---|---|
| Undo uncommitted changes to one file | `git restore path/to/file` |
| Undo all uncommitted changes to tracked files | `git restore .` |
| List new untracked files an agent created | `git clean -n` (lists only, deletes nothing) |
| Delete those untracked files | `git clean -f` (check the `-n` list first) |
| Throw away a whole task branch | `git switch main`, then `git branch -D task/NEXT-01-...` |
| Put the current branch back to a tag | `git reset --hard before-NEXT-01` |
| Find a commit you think is lost | `git reflog` |

`git reset --hard` and `git clean -f` throw away uncommitted work for good. Run `git status`
first; if anything there matters, `git stash` it before.

## The short version

**Before:** clean tree, commit, branch, an order with scope and budget, plan mode for
anything big.

**During:** out of scope means stop and ask · no refactor, clean up, modernize or rewrite
unless ordered · never touch a test to make it pass · no new dependencies.

**Before merging:** `git diff --stat` first · over twice the budget, reject unread · put back
out-of-scope files · read, test, report, merge.

**Unattended:** tag, written stop condition, time cap, budget cap, fences.

**Undo:** restore, `branch -D`, reset to the tag, reflog.

---

Part of CorvusWing. Created by Ron Brazil. MIT License.
