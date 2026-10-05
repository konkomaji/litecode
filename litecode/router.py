"""Task router: map a user request to a role (model) + profile, by rules first.

Keeps work off the model where a rule is enough. The chosen role is resolved to
an installed model by config; if the role has no model, it falls back to 'code'.
"""
from __future__ import annotations
import re

PROFILES = {
    "fim":      {"role": "fim", "thinking": False, "max_tokens": 120},
    "security": {"role": "security", "thinking": True, "max_tokens": 1200},
    "chat":     {"role": "chat", "thinking": False, "max_tokens": 1024},
    "code":     {"role": "code", "thinking": False, "max_tokens": 1500},
    "quality":  {"role": "quality", "thinking": True, "max_tokens": 1800},
}

SEC_HINT = re.compile(r"\b(vuln|vulnerab|exploit|cve|xss|sqli|csrf|ssrf|rce|payload|"
                      r"pentest|security|owasp|cwe|malware|reverse|decompil|apk|audit)\b", re.I)
HARD_HINT = re.compile(r"\b(architect|design|refactor .* across|prove|complex|hard|why does)\b", re.I)


def route(task: str, available_roles: set) -> dict:
    t = task.lower()
    if SEC_HINT.search(t) and "security" in available_roles:
        role = "security"
    elif HARD_HINT.search(t) and "quality" in available_roles:
        role = "quality"
    else:
        role = "code"
    prof = dict(PROFILES.get(role, PROFILES["code"]))
    if role not in available_roles:
        prof["role"] = "code" if "code" in available_roles else next(iter(available_roles), "code")
    return prof
