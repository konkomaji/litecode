"""Static analysis first. Find suspect code with zero model tokens, then let the
model explain and fix only the flagged lines.

Uses Semgrep or Bandit when installed. Always runs a built-in regex rule set so the
tool works offline with no extra installs. Built-in rules are a coarse filter: they
flag candidates, the model and the user confirm.
"""
from __future__ import annotations
import json, re, shutil, subprocess
from dataclasses import dataclass, asdict
from pathlib import Path

SKIP_DIRS = {".git", ".litecode", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}


@dataclass
class Finding:
    file: str
    line: int
    rule: str
    cwe: str
    severity: str
    message: str
    snippet: str
    source: str = "builtin"

    def short(self) -> str:
        return f"{self.file}:{self.line} [{self.severity}] {self.rule} ({self.cwe}) {self.message}"


# (rule id, extensions, regex, cwe, severity, message)
RULES = [
    ("py-eval", {".py"}, r"\b(eval|exec)\s*\(", "CWE-95", "high", "eval/exec on possibly untrusted data"),
    ("py-pickle", {".py"}, r"\bpickle\.loads?\s*\(", "CWE-502", "high", "pickle deserialization of untrusted data"),
    ("py-yaml-load", {".py"}, r"\byaml\.load\s*\((?![^)]*SafeLoader)", "CWE-502", "high", "yaml.load without SafeLoader"),
    ("py-shell-true", {".py"}, r"subprocess\.\w+\([^)]*shell\s*=\s*True", "CWE-78", "high", "subprocess with shell=True"),
    ("py-os-system", {".py"}, r"\bos\.(system|popen)\s*\(", "CWE-78", "medium", "shell command via os.system/popen"),
    ("py-sql-format", {".py"}, r"\.execute\s*\(\s*(f[\"']|[\"'][^\"']*[\"']\s*(%|\+|\.format))", "CWE-89",
     "high", "SQL built with string formatting"),
    ("py-weak-hash", {".py"}, r"hashlib\.(md5|sha1)\s*\(", "CWE-328", "low", "weak hash (fine for checksums, not passwords)"),
    ("py-verify-false", {".py"}, r"verify\s*=\s*False", "CWE-295", "medium", "TLS certificate check disabled"),
    ("py-flask-debug", {".py"}, r"\.run\([^)]*debug\s*=\s*True", "CWE-489", "medium", "debug mode enabled"),
    ("py-mktemp", {".py"}, r"tempfile\.mktemp\s*\(", "CWE-377", "medium", "insecure temp file"),
    ("py-random-token", {".py"}, r"random\.(random|randint|choice)\([^)]*\).*(token|secret|password|key)",
     "CWE-338", "medium", "non-crypto random used for a secret"),
    ("js-eval", {".js", ".ts", ".jsx", ".tsx"}, r"\beval\s*\(|new\s+Function\s*\(", "CWE-95", "high", "eval / new Function"),
    ("js-innerhtml", {".js", ".ts", ".jsx", ".tsx"}, r"\.(innerHTML|outerHTML)\s*=|document\.write\s*\(",
     "CWE-79", "high", "DOM HTML sink (possible XSS)"),
    ("js-dangerous-html", {".jsx", ".tsx", ".js"}, r"dangerouslySetInnerHTML", "CWE-79", "medium", "raw HTML in React"),
    ("js-child-exec", {".js", ".ts"}, r"child_process|\bexec(Sync)?\s*\(\s*`", "CWE-78", "medium", "shell command from JS"),
    ("php-exec", {".php"}, r"\b(system|exec|shell_exec|passthru|popen|proc_open)\s*\(", "CWE-78", "high", "shell command in PHP"),
    ("php-eval", {".php"}, r"\beval\s*\(|\bassert\s*\(\s*\$", "CWE-95", "high", "eval in PHP"),
    ("php-sqli", {".php"}, r"(mysqli?_query|->query)\s*\([^)]*\$_(GET|POST|REQUEST|COOKIE)", "CWE-89", "high",
     "SQL with request data"),
    ("php-include", {".php"}, r"\b(include|require)(_once)?\s*\(?\s*\$_(GET|POST|REQUEST)", "CWE-98", "high",
     "file include from request data"),
    ("php-unserialize", {".php"}, r"\bunserialize\s*\(\s*\$_", "CWE-502", "high", "unserialize of request data"),
    ("any-aws-key", None, r"AKIA[0-9A-Z]{16}", "CWE-798", "high", "hardcoded AWS access key"),
    ("any-private-key", None, r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----", "CWE-798", "high", "private key in source"),
    ("any-hardcoded-secret", None, r"(?i)\b(password|passwd|secret|api_?key|token)\s*[:=]\s*[\"'][^\"'\s]{6,}[\"']",
     "CWE-798", "medium", "hardcoded credential"),
]
_COMPILED = [(r, exts, re.compile(rx), cwe, sev, msg) for r, exts, rx, cwe, sev, msg in RULES]
CODE_EXTS = {".py", ".js", ".ts", ".jsx", ".tsx", ".php", ".rb", ".go", ".java", ".c", ".cpp", ".cs",
             ".sh", ".env", ".yml", ".yaml", ".json", ".toml", ".ini", ".cfg"}


def _files(root: Path, target: Path):
    if target.is_file():
        yield target
        return
    for p in target.rglob("*"):
        if p.is_file() and p.suffix.lower() in CODE_EXTS and not (SKIP_DIRS & set(p.relative_to(root).parts)):
            if p.stat().st_size < 1_000_000:
                yield p


def builtin_scan(root: Path, target: Path) -> list[Finding]:
    out = []
    for f in _files(root, target):
        ext = f.suffix.lower()
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        rel = str(f.relative_to(root)).replace("\\", "/")
        for i, ln in enumerate(lines, 1):
            s = ln.strip()
            if s.startswith(("#", "//")) and "BEGIN" not in s:
                continue
            for rid, exts, rx, cwe, sev, msg in _COMPILED:
                if exts is not None and ext not in exts:
                    continue
                if rx.search(ln):
                    out.append(Finding(rel, i, rid, cwe, sev, msg, s[:200]))
    return out


def _semgrep(root: Path, target: Path) -> list[Finding]:
    exe = shutil.which("semgrep")
    if not exe:
        return []
    try:
        r = subprocess.run([exe, "--config", "auto", "--json", "--quiet", "--metrics", "off", str(target)],
                           cwd=root, capture_output=True, text=True, timeout=600)
        data = json.loads(r.stdout or "{}")
    except Exception:
        return []
    out = []
    for res in data.get("results", []):
        ex = res.get("extra", {})
        cwe = ex.get("metadata", {}).get("cwe", [""])
        out.append(Finding(str(Path(res["path"])).replace("\\", "/"), res["start"]["line"], res["check_id"].split(".")[-1],
                           (cwe[0] if isinstance(cwe, list) and cwe else str(cwe)).split(":")[0],
                           ex.get("severity", "medium").lower(), ex.get("message", "")[:160],
                           ex.get("lines", "").strip()[:200], "semgrep"))
    return out


def _bandit(root: Path, target: Path) -> list[Finding]:
    exe = shutil.which("bandit")
    if not exe:
        return []
    try:
        r = subprocess.run([exe, "-r", "-f", "json", "-q", str(target)], cwd=root,
                           capture_output=True, text=True, timeout=600)
        data = json.loads(r.stdout or "{}")
    except Exception:
        return []
    out = []
    for res in data.get("results", []):
        p = Path(res["filename"])
        rel = str(p.relative_to(root) if p.is_absolute() else p).replace("\\", "/")
        out.append(Finding(rel, res["line_number"], res["test_id"], f"CWE-{res.get('issue_cwe', {}).get('id', '')}",
                           res["issue_severity"].lower(), res["issue_text"][:160], res["code"].strip()[:200], "bandit"))
    return out


SEV_ORDER = {"high": 0, "error": 0, "medium": 1, "warning": 1, "low": 2, "info": 3}


def scan(root: Path, target: str = ".") -> list[Finding]:
    root = Path(root).resolve()
    t = (root / target).resolve()
    found = _semgrep(root, t) + _bandit(root, t) + builtin_scan(root, t)
    seen, uniq = set(), []
    for f in found:
        key = (f.file, f.line, f.cwe)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f)
    uniq.sort(key=lambda f: (SEV_ORDER.get(f.severity, 2), f.file, f.line))
    return uniq


def context_for(root: Path, f: Finding, radius: int = 6) -> str:
    """The flagged line plus a few lines around it: ~300 tokens per finding."""
    try:
        lines = (Path(root) / f.file).read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return f.snippet
    a, b = max(0, f.line - 1 - radius), min(len(lines), f.line + radius)
    return "\n".join(f"{i+1}\t{lines[i]}" for i in range(a, b))


def report(findings: list[Finding]) -> str:
    if not findings:
        return "(no findings)"
    return "\n".join(f.short() for f in findings[:80]) + (
        f"\n...({len(findings) - 80} more)" if len(findings) > 80 else "")


def to_json(findings: list[Finding]) -> str:
    return json.dumps([asdict(f) for f in findings], indent=2)
