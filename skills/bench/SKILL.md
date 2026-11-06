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
- `--rooms DIR` names the folder of extra rooms (default: `rooms/` beside `serve.mjs`). A room is one
  `.js` file that exports `mount(element)`; the page gives it a tab named after the file. Only the
  `.js` and `.css` files found there when the bench starts are ever served.
- `--self-test` checks the bench itself: it starts the real server on scratch projects in the
  system's temp folder, and prints one row per behavior (the panels on a full and an empty project,
  the host, origin and key checks, the rooms, and that a message changes INBOX.md and nothing else).
  Exit 0 means every row is as expected. It needs git.

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
| A room's tab | the room's `.js` file in the rooms folder | its tab says it could not be opened, and why |
| Checks history (a room) | the gates ledger: every check's results, oldest to newest (the last 20), its newest and slowest time | there is no ledger yet; a check with no line at the ledger's newest commit reads "not run at" that commit; REFUSED is its own mark, never a pass or a fail |
| Questions (a room) | QUESTIONS.md's `## Q-nnn` sections, their pictures in `.bench/pictures/Q-nnn/`, and INBOX.md for which are answered | QUESTIONS.md is absent; a question with fewer than two options, or not exactly one `(recommended)`, shows as "cannot be answered yet" with the reason |

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

## Questions: a decision as one click

When a decision is the developer's, the agent writes it into **QUESTIONS.md** in the shape of
`templates/QUESTIONS.md`: what it is, the question, and numbered options each with its cost, exactly
one marked `(recommended)`. The Questions tab shows each one as a card, the recommendation first, with
a button per option and "Ask me first". A click writes one message to INBOX.md:

```text
## M-005 · 2026-10-21 14:09 · waiting

Answer to Q-001: 1. Keep them in a file (the recommended one)
```

The bench never edits QUESTIONS.md. A question reads answered once INBOX.md holds a message starting
`Answer to Q-nnn:`, from a click or written by hand; the newest one wins. The agent acts on it like any
other message. A question titled `Example: ...` is the template's illustration and is hidden.

**Approve** sends the option marked `(recommended)`, whichever number it has. **Collect a batch** turns
clicks into saved picks instead of sends; **Send batch (N)** then writes ONE message with an
`Answer to Q-nnn:` line per card, each with its note. The bench checks every answer first, and a batch
with an unknown question, a question twice, or nothing in it is refused whole, with nothing written. The
batch lives in the page only, so a reload empties it.

**Tabs and search.** Waiting (N), Answered (N) and All (N) are counted from the same list the cards come
from; a search box matches a question's id, title or text, and while it is on each tab says "N of M".
**Keys** (never while typing in a box, `?` shows the list): `j`/`k` move between cards, `a` approves,
`1`-`9` pick that option, `b` turns Collect a batch on or off, `n` opens the note, `/` focuses search.
Each key calls its button's own handler, so a key can never do something its button does not.

**The reply comes back on the card.** When the agent marks the answer's message
`answered HH:MM: <one line>`, that line shows on the card as the reply; `read HH:MM` shows as read with
no reply yet. The bench never invents a reply.

**Pictures**: a question may list screenshots under `Pictures:`, saved in `.bench/pictures/Q-nnn/`
(PNG, JPEG or WebP; the bench serves only those names, from only that folder). Each gets Yes, No and
Say more; one Send writes one message with a line for every picture, an unmarked one as "no verdict":

```text
Pictures for Q-006: 2 of 3 pictures marked

- home.png: yes
- menu.png: no
- gone.png: no verdict (the picture is missing)
```

A picture the question names but the folder lacks is shown as missing, never as a blank tile, and
cannot be judged. A question with pictures and no options is answered by this message.

## What it never does

- **It is reachable from this machine only.** It listens on 127.0.0.1, answers only requests that
  name it as their host, and refuses requests from other web pages: a message is accepted only with
  the key this launch put into its own page. A page on another site cannot read the project's notes
  or write into the inbox an agent obeys.
- **It writes one file**: INBOX.md, one appended message per Send, per answer or per set of picture verdicts. It reads only the
  files in the table above.
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
