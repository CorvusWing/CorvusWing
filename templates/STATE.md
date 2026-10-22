# STATE

Purpose: what is true about this project at this moment. Present tense only; history belongs in DECISIONS.md and the git log. A fact that has become history but still explains something (why a number changed, a caveat) moves unchanged into `archive/state/` at the session close; the pointer line at the bottom of this file names where.

Last checked at commit `<short hash>` on branch `<branch>` (YYYY-MM-DD).

Rows that begin with "Example:" are illustrations. Replace them with real rows.

## The project in one sentence

<what you are building>

## Done looks like

<the number or behavior that means done, and the command or action that shows it>

## What works now

| Area | Status | How we know |
|---|---|---|
| Example: sign-up form | works | `npm test -- signup` passes, 12 tests |
| Example: CSV export | slow | 10,000 rows take 41 s; the target is under 5 s |

## What is measured

| Measurement | Value | Conditions | Command |
|---|---|---|---|
| Example: test suite | 84 pass, 2 fail | main branch, local machine, test database reset first | `pytest -q` |

## Never touch

- Example: `db/migrations/` (already applied to the live database; editing one breaks it)

## Known traps

- Example: the test suite fails while the dev server is running, because both use port 3000.

## What is running

- Example: nothing. (Or: dev server on port 3000, started with `npm run dev`; stop it with Ctrl+C in its terminal.)

Older facts that still explain something: `archive/state/` (none yet).
