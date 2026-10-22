# DECISIONS

Purpose: why things are the way they are. Append only: never edit an old entry; add a new one that supersedes it. When this file passes 100 KB, the session-close skill moves the oldest entries, unchanged, into `archive/decisions/` and lists each archived range on a pointer line here.

Archived: none yet.

Before proposing an idea, search this file and `archive/decisions/`. It may have been tried already, and the reason it was rejected may still be true (or may not be any more). Rows that begin with "Example:" are illustrations. Replace them with real rows.

| Id | Date | Decision | Why | What was rejected | Reversal cost |
|---|---|---|---|---|---|
| Example: DEC-001 | YYYY-MM-DD | Every agent task gets its own git branch and a written order | agents changed unrelated files, and the changes were hard to undo | letting agents work on main and reviewing afterward | low: stop doing it |
| Example: DEC-002 | YYYY-MM-DD | Keep SQLite for now | one user and small data; the export problem is one slow query, not the database | moving to Postgres | medium: about two sittings to switch later |
| Example: DEC-003 | YYYY-MM-DD | Supersedes nothing yet. When a decision changes, add a row like this one: "Supersedes DEC-00N because ..." | | | |
