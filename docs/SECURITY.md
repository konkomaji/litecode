# Security review

litecode finds security problems in two stages. Stage 1 costs no model tokens. Stage 2 uses the model only on the flagged lines.

## Stage 1: static scan

```
litecode scan            # whole project
litecode scan src/api    # one folder
litecode scan --json     # machine-readable output
```

litecode runs:

1. Semgrep, if installed (`pip install semgrep`).
2. Bandit, if installed (`pip install bandit`).
3. Built-in rules, always. They need no install and no internet.

Built-in rules cover Python, JavaScript/TypeScript, PHP, and secrets in any file:

| Class | CWE | Examples |
|---|---|---|
| SQL injection | CWE-89 | SQL built with f-strings, `$_GET` in queries |
| Command injection | CWE-78 | `shell=True`, `os.system`, PHP `system()` |
| Code injection | CWE-95 | `eval`, `exec`, `new Function` |
| XSS | CWE-79 | `innerHTML =`, `document.write`, `dangerouslySetInnerHTML` |
| Unsafe deserialization | CWE-502 | `pickle.loads`, `yaml.load`, PHP `unserialize` |
| File inclusion | CWE-98 | `include($_GET[...])` |
| Hardcoded secrets | CWE-798 | API keys, AWS keys, private keys |
| Weak crypto and TLS | CWE-328, CWE-295 | MD5/SHA1, `verify=False` |

## Stage 2: model review

```
litecode review src/
```

For each finding, the model reads about 13 lines around the flagged line. It answers in exactly 4 lines:

```
VERDICT: real | false-positive | needs-context
SEVERITY: high | medium | low
WHY: one sentence
FIX: the smallest safe change
```

A grammar forces this format, so small models cannot drift into long text. The report is saved in `.litecode/reviews/`.

## Fixing

Ask in plain words: "fix the SQL injection in db.py with a parameterized query." litecode edits the code and you approve the diff. Run your tests after: `/test`.

## Security models

`litecode setup` can install an official security model:

- Foundation-Sec-8B (Cisco): analysis, triage, CVE knowledge.
- WhiteRabbitNeo-V3-7B: offensive security and exploit research.

Security tasks route to it automatically when it is installed.

## Rules of use

Use litecode security features only on code and systems that you own or have written permission to test. The model refuses attacks on third parties.
