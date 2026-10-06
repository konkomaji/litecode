# Use cases

litecode focuses on coding and security. It also helps with writing, study, and everyday questions, because the same local models do those tasks well.

## Coding (main focus)

- Fix bugs: "test_cart.py fails, find the root cause and fix it."
- Add features with tests: "add a --json flag and update the tests."
- Refactor safely: "rename get_usr to get_user in every file." litecode runs the tests before and after.
- Explain code: "explain @parser.py step by step."
- Test-fix loop: `/test` runs your tests, reads the failure, fixes the code, and runs them again.
- Commit messages: `/commit` writes a message from the diff.
- Autocomplete in your editor: `litecode fim`.

## Security (main focus)

- Static scan with zero model tokens: `/scan`.
- Review with a verdict per finding: `/review src/`.
- Fix common classes: SQL injection, XSS, command injection, path traversal, unsafe deserialization, hardcoded secrets.
- Authorized pentest and CTF practice with an official security model (Foundation-Sec-8B or WhiteRabbitNeo).

See [Security](SECURITY.md).

## Writing

- Emails and messages: "write email.txt telling the team the update moves to Friday 18:00, max 80 words."
- Summaries: "summarize notes.txt in 3 bullet points with the budget and the deadline."
- Documentation: "write API.md for every public function in lib.py."
- README files, release notes, reports.

Answers use plain, short sentences (ASD-STE100 rules). Text is easy to read for second-language English speakers.

## Study and questions

- Ask about a concept: "what is a race condition? give a 5-line Python example."
- Learn a codebase: "which function in the app package is never called?"
- Practice offline: no internet and no data charges after setup.

## Data tasks

- CSV and JSON reports: "write report.py that prints total sales per region."
- Log analysis: "count status codes and the top IP in access.log."
- Config edits: "set debug to false in settings.json."

## Proof

Every use case above is a challenge in the litecode test suite. See which models pass which tasks on the [Benchmarks](BENCHMARKS.md) page.
