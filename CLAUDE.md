# Project notes

## OpenSpec workflow

After any change to OpenSpec planning artifacts (`openspec/changes/**`: proposal, specs, design, tasks), always run both checks before reporting the change as done:

1. `openspec validate --all --strict`: checks the artifacts are well-formed.
2. `/opsx:update <change-name>` as a coherence review: re-reads every artifact in the change and checks they agree with each other. Report any inconsistencies it finds and wait for confirmation before fixing them.

Do this even for small edits, and say in the summary that both checks ran.
