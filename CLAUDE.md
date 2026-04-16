# Project guidelines

## Git hygiene

Commit small, reversible changes. Don't let the working tree accumulate a large unreviewed changeset before proposing a commit.

- Prefer one logical change per commit, even within a single feature
- After each working step (tests green, feature verified), pause and propose a commit
- Follow the repo's existing commit message style — check recent `git log` before writing a message
- Only commit when the user explicitly asks; never stage or amend on your own initiative
