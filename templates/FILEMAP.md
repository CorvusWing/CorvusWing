# FILEMAP

Purpose: one row per file or folder that matters, saying what it is. A new file gets its row in the same commit that creates it.

Rows that begin with "Example:" are illustrations. Replace them with real rows.

| Path | What it is | Notes |
|---|---|---|
| AGENTS.md | House rules every agent session reads first, in any agent tool | keep under about 80 lines; at most ten lessons |
| SAFE-COPY.md | Where the untouched original and its sealed snapshot are, with the counts that proved them | written once, at setup |
| LESSONS.md | Every lesson the project paid for, with its story | append only; never deleted |
| archive/ | Finished work, moved unchanged, each move leaving a pointer line | never deleted; its README.md says when to open each file |
| CLAUDE.md | One line importing AGENTS.md for Claude Code, plus Claude-only notes | project rules go in AGENTS.md |
| PLAN.md | The route from today to done: premises, milestones, tasks | changed only after a DECISIONS.md entry |
| STATE.md | What is true now | present tense only |
| HANDOFF.md | What to do next, in order | rewritten at each session close |
| DECISIONS.md | Why things are the way they are | append only; past 100 KB its oldest entries move, unchanged, to archive/decisions/ |
| PICKUP.md | The paste-ready resume prompt | rewritten at each session close |
| ORDER.md | The current task order for an agent | one task at a time |
| REPORT.md | The report on the last finished task | written before the merge |
| FILEMAP.md | This file | |
| Example: src/export.py | Builds the CSV export from the orders table | slow on big tables; see NEXT-01 |
| Example: tests/ | The pytest tests; run them with `pytest -q` | |
| Example: db/migrations/ | Database schema changes | never touch (see AGENTS.md) |
