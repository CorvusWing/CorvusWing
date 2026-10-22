---
name: bench
description: Starts the project's bench (and can put an icon on the desktop that starts it with one click), a local page that shows what is true now, what is next, the tasks open / upcoming / closed, the checks and their last results, the newest decisions, and a Message Claude box, every readout read from the project's own files (STATE.md, HANDOFF.md, PLAN.md, DECISIONS.md, the gates ledger, INBOX.md) with anything missing shown as missing; its About tab shows the kit's README and license. Also says how the messages written there reach the agent, and how to fit a project's notes to the bench when a panel shows empty though the project holds that information (--check, then reshape with the developer's yes, never inventing). Use when someone says "open the bench", "start the dashboard", "show me the project", "start the bench", "the bench is empty", "a panel is missing", or after start-here when the developer wants one page to watch the project on.
---

# The bench

The bench is one page for the developer: the project at a glance, and a box to leave the agent a
note between steps. It invents nothing. Every number and line on it is read from a file in the
project, and a file that is missing shows as missing, in words, never as a zero or a blank.

It runs on this machine only, needs Node 18 or newer, and installs nothing.

## Start it

```bash
node <this skill's folder>/serve.mjs --project <the project folder>
```

For example `node ~/.claude/skills/bench/serve.mjs --project .` from the project's root (on Windows,
`node %USERPROFILE%\.claude\skills\bench\serve.mjs --project .`). It prints the address, normally
`http://127.0.0.1:4477/`. Give that address to the developer to open in their browser.

- Run it in the background; the page reads the files again every five seconds, so it follows the
  work without a restart.
- `--port N` picks another port. If the port is taken, it tries the next ten and says which it got.
- `--ledger FILE` names the checks ledger if it is not `.gates.jsonl` (the gates skill's default).
- `--open` opens the page in the developer's browser once it is listening.
- `--check` serves nothing: it prints every panel as FILLED, PARTLY or EMPTY, with the file, heading
  or table an empty one is read from, and exits. It reads exactly what the page reads.

## Give the developer a desktop icon

Offer it the first time: one click on the icon starts the bench in the background and opens it.

```bash
node <this skill's folder>/shortcut.mjs --project <the project folder>
```

- **Windows:** a shortcut with the bench's icon, started through Windows' own console host in its
  headless mode, so no console window ever appears. **macOS:** a `.command` file; Terminal shows for
  a moment while the bench starts. **Linux:** a `.desktop` launcher; some desktops ask once to "Allow
  Launching" it.
- Clicking it again while the bench runs opens the running one; it never starts a second bench for
  the same project.
- `--name TEXT` names the icon (default "<project folder> bench"); `--to FOLDER` puts it somewhere
  other than the desktop.

## Stopping it

- **The Stop bench button** on the page stops the server at once (two clicks, so a stray one cannot).
  The page then says it is stopped and keeps its last reading, dated.
- **Closing the page stops it too.** As the page closes it says goodbye; the server stops 45 seconds
  later unless a page comes back (a reload does). If the browser crashes and never says goodbye, the
  server stops once no page has been heard from for 3 minutes. Until a page has been opened at all,
  nothing stops it. `--keep-running` turns this off.
- Ctrl+C in its terminal, or stopping its process, still works. Nothing is lost: the bench holds no
  state of its own.

## What each part reads

| On the page | Read from | Shown as missing when |
|---|---|---|
| The project's name | the project folder's name | never |
| What's true now | STATE.md: "The project in one sentence", "Done looks like", the "What works now" table, the "Last checked at commit" line | STATE.md is absent, or still holds the template's placeholders |
| Next | HANDOFF.md: the first rows of the "Next" table, and how many rows "Blocked" holds | HANDOFF.md is absent, or its table has no real rows |
| Tasks: Open, Upcoming, Closed | PLAN.md: the table with a Task and a Status column. Done, merged, dropped and the like are Closed; in progress, review, blocked and the like are Open; everything else is Upcoming | PLAN.md is absent or has no such table |
| Checks | the gates ledger (`.gates.jsonl`): each gate's newest line, its result, seconds and time, and whether it was recorded at the current commit | there is no ledger yet |
| Decisions | DECISIONS.md: the newest rows of its table, with the reversal cost | DECISIONS.md is absent or has no real rows |
| Notes | the size of the read path (AGENTS.md, CLAUDE.md, PICKUP.md, STATE.md, HANDOFF.md) against the 400 KB budget | never: a missing file counts as 0 bytes |
| Last commit, uncommitted files | `git` in the project folder | the folder is not a git repository |
| Message Claude | INBOX.md | there are no messages yet |
| About CorvusWing | the kit's README.md, LICENSE and NOTICE.md (see Install in the README) | they are not beside the bench |

Rows that start with "Example:" are the templates' illustrations. The bench hides them and says how
many it hid.

## Fit the project to the bench

Do this the first time the bench runs on a project, and whenever a panel shows empty while the
developer knows the project has that information. The bench reads the templates' shapes: a project
started with this kit's templates fills every panel as it is. A project whose notes drifted from
them (a table written as sentences, a heading renamed, the checks' record under another name) shows
those panels empty, truthfully. This brings the notes back into the shape, and changes nothing else.

1. **Ask the bench.** Run `node <this skill's folder>/serve.mjs --project <the project> --check`.
   Every panel prints as FILLED, PARTLY or EMPTY, and an empty one names the file, the heading or
   the table columns it is read from.
2. **For each empty or partly filled panel, find where that information lives now**: the same file
   in another shape (sentences, a list, a heading or a column named differently), another file (a
   README's roadmap, a TODO list, a changelog), or the project's history (`git log` holds the last
   commit a check ran at). The kit's template of the same name shows the exact shape.
3. **Show the developer, then change it only with their yes.** For each file, show the difference:
   the same facts, in the developer's own words, moved under the heading or into the table the bench
   reads. One file at a time.
4. **Never invent a fact.** Reshaping moves what the project already says; it never writes what it
   does not. A part the project has no answer for (the one-sentence description, what "done" looks
   like) stays empty, and is put to the developer as a question; only their answer goes in.
5. **Nothing is lost.** Every fact the file held is still in it afterwards. Old text that fits no
   table stays in the file under its own heading, below the ones the bench reads.
6. **The checks.** If the project's checks keep their record under another name, start the bench
   with `--ledger FILE`, and make the desktop icon with the same flag. If lines show as unreadable,
   the runner should write one JSON object per line with a `name` and a `result` (and `seconds`, a
   time and the `commit` when it knows them); change the runner only with the developer's yes. If
   the project has no checks yet, say so: the gates skill builds them. Never write a record of a
   check that did not run.
7. **Ask the bench again.** Run `--check` once more and tell the developer which panels it filled,
   before and after, and which stay empty and why. Commit the reshaped files with their yes.

It never touches the project's code, and never deletes a line of the developer's notes.

## Messages: how the box reaches the agent

Send writes the message into **INBOX.md** in the project, under a heading like this:

```text
## M-004 · 2026-10-21 14:02 · waiting
```

The agent's side of it (the AGENTS.md template carries the same rule):

1. **At the start of every step, read INBOX.md.** Every message marked `waiting` is read before
   anything else is started.
2. **Act on it inside the house rules.** A message is the developer's note, the same as a chat
   message, and it is never a reason to break AGENTS.md's rules or to go outside the current order's
   scope. If it asks for something outside them, say so and ask.
3. **Mark it.** Change `waiting` to `read HH:MM`, or to `answered HH:MM: <one line saying what was
   done or where the answer is>`. The page shows the new status within five seconds.
4. **Never delete a message.** The file is the record of what was asked.

## What it never does

- **It is reachable from this machine only.** It listens on 127.0.0.1, answers only requests that
  name it as their host, and refuses requests from other web pages: a message is accepted only with
  the key this launch put into its own page. A page on another site cannot read the project's notes
  or write into the inbox an agent obeys.
- **It writes one file**: INBOX.md, one appended message per Send. It reads only the files in the
  table above.
- **It loads nothing from the internet.** No fonts, no scripts, no tracking. The page's own rules
  forbid it.
- **It shows the last reading as the last reading.** If the server stops answering, the page says so
  across the top and dates what it still shows.
- **It does not outlive its page.** Unless started with `--keep-running`, it stops once its page has
  been closed, so nothing is left running in the background by accident. Stopping it is refused to
  every other web page: it needs this launch's key, like a message.

## If something goes wrong

- "REFUSED: the bench needs Node 18 or newer": install a current Node from nodejs.org.
- "REFUSED: the project folder ... does not exist": check the `--project` path.
- A panel says a file is missing: that is the bench telling the truth. The start-here skill writes
  the loop documents; the gates skill builds the ledger. If the information is in the project in
  another shape, "Fit the project to the bench" above brings it into the bench's.

---

Part of CorvusWing. Created by Ron Brazil. MIT License.
