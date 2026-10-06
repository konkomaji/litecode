---
name: test-fix
description: Run the tests, read the failure, fix the code, run again until green.
triggers: failing, tests, test, pytest, unittest, jest, broken
tools: run, read_file, edit_file
---
1. Find the test command in the project brief. Else try: python -m pytest -q, npm test, go test ./...
2. Run the tests.
3. If all pass, report that and stop.
4. Read the first failure. Read the code it names.
5. Fix the code, not the test, unless the test is wrong. Use edit_file.
6. Run the tests again. Repeat at most 3 times.
7. In final, say what failed, what you changed, and the last test result.
