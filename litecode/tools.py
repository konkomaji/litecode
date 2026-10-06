"""Agent tools: file, search, shell, git, scan, memory, and MCP tools.

All paths are sandboxed to the project root. Mutating tools need approval unless the
permission mode is "auto". In "readonly" mode, mutating tools are refused.
"""
from __future__ import annotations
import os, re, shutil, subprocess
from pathlib import Path

SKIP = (".git", ".litecode", "node_modules", "__pycache__", ".venv", "venv")
MUTATING = {"write_file", "edit_file", "run"}


def bash_path() -> str | None:
    """Full path to a real bash. On Windows, CreateProcess finds the WSL stub in
    System32 before Git Bash, so always pass an absolute path and skip the stub."""
    exe = shutil.which("bash")
    if os.name == "nt":
        low = (exe or "").lower()
        if not exe or "system32" in low or "windowsapps" in low:
            git = shutil.which("git")
            cands = [Path(git).parent.parent / "bin" / "bash.exe"] if git else []
            cands.append(Path("C:/Program Files/Git/bin/bash.exe"))
            exe = next((str(c) for c in cands if c.exists()), None)
    return exe


def default_shell() -> str:
    return "bash" if bash_path() else "powershell"


class Tools:
    def __init__(self, root: Path, approve, memory=None, mode: str = "ask", mcp=None):
        self.root = Path(root).resolve()
        self.approve = approve          # callable(action:str, detail:str) -> bool
        self.memory = memory            # for checkpoints / remember (optional)
        self.mode = mode                # ask | auto | readonly
        self.mcp = mcp                  # mcp.Hub or None
        self.changed: list[str] = []    # files changed in this run

    def _safe(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        if self.root not in p.parents and p != self.root:
            raise ValueError(f"path escapes project root: {rel}")
        return p

    def _ok(self, action: str, detail: str) -> bool:
        if self.mode == "readonly":
            return False
        if self.mode == "auto":
            return True
        return self.approve(action, detail)

    # --- read-only (no approval) ---
    def list_dir(self, path="."):
        p = self._safe(path)
        if not p.exists():
            return f"(no such dir: {path})"
        out = []
        for c in sorted(p.iterdir()):
            if c.name in SKIP:
                continue
            out.append(("DIR  " if c.is_dir() else "FILE ") + str(c.relative_to(self.root)).replace("\\", "/"))
        return "\n".join(out) or "(empty)"

    def glob(self, pattern="**/*"):
        hits = []
        for f in sorted(self.root.glob(pattern)):
            if f.is_file() and not (set(SKIP) & set(f.relative_to(self.root).parts)):
                hits.append(str(f.relative_to(self.root)).replace("\\", "/"))
                if len(hits) >= 200:
                    return "\n".join(hits) + "\n...(200+ files)"
        return "\n".join(hits) or "(no files)"

    def read_file(self, path, start=1, end=None, max_bytes=40000):
        p = self._safe(path)
        if not p.exists():
            return f"(no such file: {path})"
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, int(start or 1))
        end = min(len(lines), int(end)) if end else len(lines)
        body = "\n".join(f"{i}\t{lines[i-1]}" for i in range(start, end + 1))
        more = f"\n...(truncated; file has {len(lines)} lines, use start/end)" if len(body) > max_bytes else ""
        return (body[:max_bytes] + more) or "(empty file)"

    def grep(self, pattern, glob="**/*"):
        try:
            rx = re.compile(pattern)
        except re.error:
            rx = re.compile(re.escape(pattern))
        hits = []
        for f in self.root.glob(glob):
            if not f.is_file() or set(SKIP) & set(f.relative_to(self.root).parts):
                continue
            try:
                for i, ln in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if rx.search(ln):
                        hits.append(f"{f.relative_to(self.root)}:{i}:{ln.strip()[:160]}".replace("\\", "/"))
                        if len(hits) >= 100:
                            return "\n".join(hits) + "\n...(100+ matches)"
            except Exception:
                pass
        return "\n".join(hits) or "(no matches)"

    def _git(self, *args) -> str:
        if not shutil.which("git"):
            return "(git not installed)"
        r = subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True, timeout=60)
        out = (r.stdout + r.stderr).strip()
        return out[:12000] or "(no output)"

    def git_status(self):
        return self._git("status", "--short", "--branch")

    def git_diff(self, path=""):
        return self._git("diff", "--", path) if path else self._git("diff")

    def scan(self, path="."):
        from . import scan as sc
        self._safe(path)
        fs = sc.scan(self.root, path)
        return sc.report(fs)

    def remember(self, text, kind="fact"):
        if self.memory is None:
            return "(memory not available)"
        self.memory.remember(text, kind)
        return "remembered."

    # --- mutating (need approval) ---
    def _checkpoint(self, p: Path, rel: str):
        if self.memory is not None and p.exists():
            try:
                self.memory.checkpoint(rel, p.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                pass

    def write_file(self, path, content):
        p = self._safe(path)
        if not self._ok("write_file", f"{path} ({len(content)} bytes)"):
            return "(denied: read-only mode)" if self.mode == "readonly" else "(denied by user)"
        self._checkpoint(p, path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        self.changed.append(path)
        return f"wrote {path} ({len(content)} bytes)"

    def edit_file(self, path, find, replace):
        """Replace one exact occurrence of `find` with `replace`. Safer than a
        full rewrite for small models: it changes only the targeted span."""
        p = self._safe(path)
        if not p.exists():
            return f"(no such file: {path})"
        data = p.read_text(encoding="utf-8", errors="replace")
        n = data.count(find)
        if n == 0:
            return "(find text not found; read the file and copy an exact snippet)"
        if n > 1:
            return f"(find text matches {n} places; add more surrounding context to make it unique)"
        new = data.replace(find, replace, 1)
        if not self._ok("edit_file", f"{path}\n{_mini_diff(find, replace)}"):
            return "(denied: read-only mode)" if self.mode == "readonly" else "(denied by user)"
        self._checkpoint(p, path)
        p.write_text(new, encoding="utf-8")
        self.changed.append(path)
        return f"edited {path} (1 replacement)"

    def run(self, cmd, shell=None):
        shell = shell or default_shell()
        bash = bash_path()
        if shell == "bash" and not bash:
            shell = "powershell"
        if not self._ok("run", f"[{shell}] {cmd}"):
            return "(denied: read-only mode)" if self.mode == "readonly" else "(denied by user)"
        exe = (["powershell", "-NoProfile", "-Command", cmd] if shell == "powershell"
               else [bash, "-c", cmd])
        try:
            r = subprocess.run(exe, cwd=self.root, capture_output=True, text=True, timeout=180)
            out = (r.stdout + r.stderr).strip()
            out = (out[:8000] + "\n...(truncated)") if len(out) > 8000 else out
            return f"(exit {r.returncode})\n{out}" if out else f"(exit {r.returncode}, no output)"
        except subprocess.TimeoutExpired:
            return "(command timed out after 180s)"

    # dispatch table for the agent
    def call(self, name, args: dict):
        if not isinstance(args, dict):
            return "(args must be a JSON object)"
        fns = {
            "list_dir": lambda a: self.list_dir(a.get("path", ".")),
            "glob": lambda a: self.glob(a.get("pattern", "**/*")),
            "read_file": lambda a: self.read_file(a["path"], a.get("start", 1), a.get("end")),
            "grep": lambda a: self.grep(a["pattern"], a.get("glob", "**/*")),
            "git_status": lambda a: self.git_status(),
            "git_diff": lambda a: self.git_diff(a.get("path", "")),
            "scan": lambda a: self.scan(a.get("path", ".")),
            "remember": lambda a: self.remember(a["text"], a.get("kind", "fact")),
            "write_file": lambda a: self.write_file(a["path"], a.get("content", "")),
            "edit_file": lambda a: self.edit_file(a["path"], a["find"], a["replace"]),
            "run": lambda a: self.run(a["cmd"], a.get("shell")),
        }
        try:
            if name in fns:
                return fns[name](args)
            if self.mcp is not None and self.mcp.has(name):
                if not self._ok("mcp", f"{name} {str(args)[:200]}"):
                    return "(denied)"
                return self.mcp.call(name, args)
            return f"(unknown tool: {name})"
        except KeyError as e:
            return f"(missing arg {e} for {name})"
        except Exception as e:
            return f"(tool error: {type(e).__name__}: {e})"


def _mini_diff(old: str, new: str, limit=12) -> str:
    o = ["  - " + x for x in old.splitlines()[:limit]]
    n = ["  + " + x for x in new.splitlines()[:limit]]
    return "\n".join(o + n)


SPEC = """Tools. Reply with ONE JSON object per step:
- list_dir   {"tool":"list_dir","args":{"path":"."}}
- glob       {"tool":"glob","args":{"pattern":"**/*.py"}}
- read_file  {"tool":"read_file","args":{"path":"src/x.py","start":1,"end":80}}
- grep       {"tool":"grep","args":{"pattern":"TODO","glob":"**/*.py"}}
- scan       {"tool":"scan","args":{"path":"."}}   static security scan, use before a security review
- git_status {"tool":"git_status","args":{}}
- git_diff   {"tool":"git_diff","args":{"path":""}}
- edit_file  {"tool":"edit_file","args":{"path":"src/x.py","find":"exact old text","replace":"new text"}}
- write_file {"tool":"write_file","args":{"path":"src/x.py","content":"full file"}}
- run        {"tool":"run","args":{"cmd":"python -m pytest -q"}}
- remember   {"tool":"remember","args":{"text":"tests run with: pytest -q","kind":"fact"}}
- final      {"tool":"final","args":{"message":"the answer or what you did"}}"""
