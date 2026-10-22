# PLAN

Purpose: the route from today to done, written backwards from done. HANDOFF.md holds only the next few tasks, copied from here: the plan is the map, the handoff is today's directions. When the route changes, add a DECISIONS.md entry saying why first, then change this file.

Rows that begin with "Example:" are illustrations. Replace them with real rows.

## Goal and done

Goal: <one sentence, in the developer's words>

Done when: <a check anyone can run, and what it should print or show>

## The premises this plan rests on (riskiest first)

A premise is something the whole plan assumes and nobody has measured yet. Test the riskiest one first, with the cheapest probe that could prove it false. Write the cancel line before the probe runs. If a probe fails, the plan changes before anything is built on it.

| Id | Premise | The probe that could cancel it | Cancel line (written before the probe) | Status (dated) |
|---|---|---|---|---|
| Example: P-1 | Most files users import are under 10,000 rows | count the rows in last month's uploads | if more than 10% pass 10,000 rows, milestone M-2 moves to first | untested |
| Example: P-2 | The report library can draw the charts we need | build one chart from real data in a scratch script | if it cannot draw a stacked bar, choose the library before M-3 | untested |

## The route, written backwards

Start at done and ask: what must be true just before it? Write each answer as a state anyone can check, never an activity ("a 10,000-row import finishes in under 5 seconds", not "work on the import"). Keep asking until you reach today. Then read it forwards: if this is true, does the next one really follow?

| Milestone | True when (a check anyone can run) | Needs first | Size (sittings) | Status (dated) |
|---|---|---|---|---|
| Example: M-3 (done) | a visitor signs up, imports a file and downloads the report in under a minute | M-2 | 3 | |
| Example: M-2 | a 10,000-row import finishes in under 5 s | M-1 | 2 | |
| Example: M-1 | the import has tests that pin down today's behavior | nothing: it starts today | 1 | |

Three to six milestones is usual. More than eight means the steps are too small, or the goal is two projects.

## Tasks for the first milestone only

Break only the first milestone into tasks. The later ones will look different once it is done. Size each task in sittings (one sitting is one focused session), then cut the estimate once: estimates overshoot.

| Id | Milestone | Task | Done when | Cancel if | Size | Status (dated) |
|---|---|---|---|---|---|---|
| Example: NEXT-01 (pin the import) | M-1 | Write tests that pin today's import behavior on three sample files | `pytest tests/test_import.py` passes, 3 new tests | the import already has tests covering these files | 1 sitting, about 80 lines | ready |

## Not doing, and why

Writing these down stops an eager agent from "helpfully" starting them, and stops the same idea being argued again next week.

- Example: a mobile app. Not needed for done; revisit after M-3.

## How this plan changes

- A task finishes: its status gets the date, the commit hash and a pointer to its ORDER and REPORT in `archive/tasks/<id>-<short-name>/`.
- A milestone finishes: its task rows move, unchanged, into `archive/plan/<milestone>-<short-name>.md`, and its row here keeps one pointer line: "done YYYY-MM-DD, commit <hash>, tasks in archive/plan/...". This file then holds only the route ahead.
- A probe fails, or a better route turns up: a DECISIONS.md entry first (what changed, why, what it costs), then edit the route.
- A milestone is never deleted silently: mark it "dropped (DEC-00N)" and leave the row.
- When the first milestone is done, break the next one into tasks, the same way.
