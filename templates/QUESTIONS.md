# Questions

Decisions only the developer can make, one section each, newest at the bottom. The agent writes them; the bench shows each as a
card with the recommendation first and a button per option. A click writes one message to INBOX.md that starts
`Answer to Q-nnn:`, and the agent reads it at its next step. Nothing here is ever deleted; an answered question stays as the record
of what was asked.

The shape, which the bench checks (a question with fewer than two options, or not exactly one marked recommended, is shown as
"cannot be answered yet" with the reason):

- a heading `## Q-nnn · <a few words>`;
- `What it is:` the situation in plain words, for someone who was not watching;
- `The question:` one question, the decision alone;
- `Options:` a numbered list; mark exactly one `(recommended)`, and give each option its cost.

## Q-001 · Example: where the totals are kept

What it is: the counter keeps its totals in memory today, so a restart loses them.
The question: Should the totals survive a restart?
Options:
1. Keep them in a file (recommended) -- about twenty lines and one test; nothing to install
2. Keep them in memory -- nothing to build; every restart starts from zero
