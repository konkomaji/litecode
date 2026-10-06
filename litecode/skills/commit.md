---
name: commit
description: Write a commit message from the current git diff.
triggers: commit, commit message
tools: git_status, git_diff
---
1. Run git_status and git_diff.
2. Write one subject line, max 60 characters, imperative mood ("Add", "Fix").
3. Add a short body only if the reason for the change is not obvious.
4. Do not run git commit yourself. Put the message in final.
