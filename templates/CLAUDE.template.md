@AGENTS.md

# CLAUDE.md: the Claude-only notes

Purpose: Claude Code reads this file at the start of every session. The first line imports AGENTS.md, so Claude follows the same house rules as every other agent tool. Put project rules in AGENTS.md, never here: a rule written only here is one the other tools never see.

## Claude-only notes

- Every task opens with the three skills, as AGENTS.md says: holding-the-goal whole, through the Skill tool, then the parts of solution-integrity and working-discipline the task needs. Say which parts you used, in the reply.
- At every commit, read how full this session's context is (the context-guard skill). At about 85% of the window, start nothing new: commit, bring the notes current, and write PICKUP.md with the compaction skill before the automatic summary can come.
- Example: run anything that takes more than a minute in the background, and check on it instead of waiting.
