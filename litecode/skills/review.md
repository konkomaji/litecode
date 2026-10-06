---
name: review
description: Security review of code. Static scan first, then confirm and fix each finding.
triggers: review, audit, vulnerability, vulnerabilities, vuln, security, owasp, cwe
tools: scan, read_file, edit_file
---
1. Run scan on the target path. Do not search by hand first.
2. For each finding, read_file around the flagged line.
3. Decide: real issue or false positive. State the reason in one sentence.
4. For a real issue, give severity, CWE, and the smallest safe fix.
5. Apply a fix with edit_file only if the user asked for fixes.
6. In final, list findings as: file:line, severity, CWE, verdict, fix.
