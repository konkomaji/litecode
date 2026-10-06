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


# Words that mean "do something in the project". Without them (and without a file name),
# a message is a chat: greeting, thanks, or a general question answered without tools.
ACTION = re.compile(
    r"\b(build|create|make|write|generate|scaffold|add|implement|fix|debug|edit|change|modify|update|"
    r"refactor|rename|move|delete|remove|run|execute|test|tests|install|setup|set up|deploy|commit|"
    r"read|open|show|list|find|search|grep|look at|check|review|scan|audit|analy[sz]e|explain (this|the|my)|"
    r"this (code|file|project|repo|function|error)|my (code|file|project|repo|app)|the (code|file|project|repo)|"
    r"folder|directory|repo|project|codebase)\b", re.I)
FILEISH = re.compile(r"(@\S+|\b[\w-]+\.(py|js|ts|tsx|jsx|java|c|cpp|h|cs|go|rs|rb|php|html|css|json|ya?ml|"
                     r"toml|md|txt|sh|ps1|bat|sql|kt|swift|vue|ini|cfg|env|lock|csv|log)\b|[\\/]\w)", re.I)


PROJECT_REF = re.compile(r"\b((this|my|the|our|current) (code|file|files|project|repo|function|class|error|bug|"
                         r"app|folder|directory|codebase|tests?|script|module)|in here|here in)\b", re.I)
# A plain question ("what is a list comprehension") is a chat even if it contains an action word.
# "can you build ..." is a request, not a question.
QUESTION = re.compile(r"^(what|how|why|when|where|which|who|whom|is|are|was|does|do|did|should|explain|"
                      r"define|tell me|difference|compare|meaning of)\b(?! you\b)", re.I)


def is_chat(task: str) -> bool:
    t = task.strip()
    if not t or "```" in t or "\n" in t.strip():
        return False
    if FILEISH.search(t) or PROJECT_REF.search(t):
        return False
    if QUESTION.search(t):
        return True
    return not ACTION.search(t)


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
