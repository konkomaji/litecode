---
name: refactor
description: Change code structure without changing behavior.
triggers: refactor, clean up, cleanup, simplify, rename
tools: read_file, grep, edit_file, run
---
1. Read the code and find every caller with grep.
2. Run the tests first and note the result.
3. Make small edits with edit_file. One change per edit.
4. Update every caller.
5. Run the tests again. Behavior must not change.
6. In final, list each change and the test result before and after.
