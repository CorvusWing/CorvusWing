# HANDOFF

Purpose: what to do next, in order: the next few tasks, copied from PLAN.md. Rewritten (not appended to) at every session close.

Every item has an id with a short description, a done-criterion anyone can check, a cancel condition, and a size in sittings (one sitting = one focused session). Rows that begin with "Example:" are illustrations. Replace them with real rows.

## Next

| Id | Task | Done when | Cancel if | Size | Status |
|---|---|---|---|---|---|
| Example: NEXT-01 (export timeout) | Make the CSV export of 10,000 rows finish in under 5 s | `pytest tests/test_export.py` passes, including a new timing test | the export already takes under 5 s from the command line (then the slowness is in the page) | 1 sitting, about 60 lines | ready |
| Example: NEXT-02 (welcome email) | Send a welcome email after sign-up | a new test shows exactly one email queued per sign-up | sign-up already calls the email library | 1 sitting, about 40 lines | after NEXT-01 |

## Blocked

| Id | What blocks it | What would unblock it | Owner |
|---|---|---|---|
| Example: NEXT-05 (refunds) | no test account with the payment service | the developer creates one | developer |

## Not doing, and why

- Example: switching databases. Rejected in DEC-002; the slowness is in one query, not the database.
