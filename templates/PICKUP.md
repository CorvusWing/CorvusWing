# PICKUP

Purpose: the paste-ready prompt that resumes work in a fresh session exactly where the last one stopped. Rewritten at every session close.

Copy everything inside the block below into a new session. Lines that begin with "Example:" are illustrations; replace them with real lines.

```text
Resume work on <project name> in <project folder>.

FIRST, before anything else, check these notes against the repository:
  git status
  git log --oneline -3
  <one test command>    (these notes say: <expected result>)
If anything disagrees with these notes, tell me what differs before doing any work.
The repository wins over the notes.

READ, in order: AGENTS.md, STATE.md, the top of HANDOFF.md (PLAN.md for where it fits).

OFF LIMITS:
- Example: db/migrations/ (do not edit)
- Example: do not push to any remote
- Example: do not add or upgrade dependencies

WHERE WE LEFT OFF:
Example: NEXT-01 (export timeout) is merged. Exporting 10,000 rows takes 3.1 s; 86 tests pass.
The task branch is deleted and main is clean.

NEXT TASK:
Example: NEXT-02 (welcome email). Done when a new test shows exactly one email queued per sign-up.
Cancel if sign-up already calls the email library. The order is in ORDER.md.
Make the branch task/NEXT-02-welcome-email first.
STOP and report when done. Do not start the next task.

ORDERS ALREADY CARRIED OUT (history; never do these again):
- Example: removed the old export function from src/export_old.py (commit 4f2a9c1)

STANDING RULES (still in force):
- Stay inside the files the order names. Need another file? Stop and ask first.
- Never delete, skip or weaken a test to make it pass.
- Example, learned the hard way: run the tests with the dev server stopped, because both use port 3000.

WHAT IS RUNNING:
- Example: nothing.

MANIFEST:
- branch: main                           check: git branch --show-current
- last commit: 7c1e0b2 "Merge NEXT-01"   check: git log --oneline -1
- tree clean: yes                        check: git status --short   (prints nothing)
- tests: 86 pass, 0 fail                 check: pytest -q
- next: NEXT-02 (welcome email)          check: top of HANDOFF.md

End every reply with a plain summary in bullets, with every term explained.
```
