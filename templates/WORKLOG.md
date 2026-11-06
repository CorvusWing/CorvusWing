# Work log

What got done, one section per day, newest at the bottom. The agent adds the day's section at the day's close (session-close);
the bench shows it by day, week and month in its Work log tab. Nothing here is ever deleted.

The shape, which the bench reads:

- a heading `## YYYY-MM-DD` for each day with work; a day with no work gets no section (the bench shows it as "no entry", never
  as zero);
- a table of two columns, what got done and its proof;
- a proof is `commit <hash>`, `file <path>` or `check <name>`. The bench says whether it holds: the commit must exist in this
  repository, the file inside the project. A check is named, and its result is in the checks ledger.

The week and month totals are counted by the bench from these sections, so they are never written here.

An example section, indented so the bench does not count it:

    ## 2026-01-05

    | What got done | Proof |
    |---|---|
    | Totals now survive a restart | commit 3f2a9c1 |
    | Wrote down how the counter starts | file STATE.md |
    | The unit tests pass on the new code | check unit tests |
