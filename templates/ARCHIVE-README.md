# archive/: finished work, kept whole

Purpose: the index of everything moved out of the working notes. The start-here skill copies this file to `archive/README.md`; the session-close skill adds a row every time it moves something here.

The rules:

- **Moved, never trimmed.** A piece arrives here exactly as it left its document: same words, same numbers. Nothing is summarized on the way.
- **Every move leaves one pointer line** where the piece used to be, naming the file it went to. An agent that needs the detail follows the pointer; one that does not reads one line instead of a page.
- **Nothing here is ever deleted.** A finished task, an old decision or a fact that became history still explains why things are the way they are.
- **The pointer and the move go in the same commit**, so the two can never disagree.

Rows that begin with "Example:" are illustrations. Replace them with real rows.

| Path | What it holds | Moved from | When to open it |
|---|---|---|---|
| Example: archive/tasks/NEXT-01-pin-the-import/ | ORDER.md and REPORT.md for NEXT-01, as they stood when it finished | ORDER.md, REPORT.md (YYYY-MM-DD, commit 4f2a9c1) | when the import's tests are questioned, or a similar task is planned |
| Example: archive/plan/M-1-import-tests.md | M-1's task rows, each with its date and commit | PLAN.md (YYYY-MM-DD) | when you need to know how M-1 was done, or why a task was dropped |
| Example: archive/decisions/DEC-001-to-DEC-120.md | the first 120 decisions, unchanged | DECISIONS.md, when it passed 100 KB | before proposing an idea: search here as well as DECISIONS.md |
