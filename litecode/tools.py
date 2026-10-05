"""Agent tools: file + shell + search, sandboxed to the project root with approvals."""
from __future__ import annotations
import subprocess
from pathlib import Path


class Tools:
    def __init__(self, root: Path, approve):
        self.root = root.resolve()
        self.approve = approve          # callable(action:str, detail:str) -> bool

    def _safe(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        if self.root not in p.parents and p != self.root:
            raise ValueError(f"path escapes project root: {rel}")
        return p

    # --- read-only (no approval) ---
    def list_dir(self, path="."):
        p = self._safe(path)
        if not p.exists():
            return f"(no such dir: {path})"
        out = []
        for c in sorted(p.iterdir()):
            if c.name in (".git", ".litecode", "__pycache__", "node_modules"):
                continue
            out.append(("DIR  " if c.is_dir() else "FILE ") + str(c.relative_to(self.root)))
        return "\n".join(out) or "(empty)"

    def read_file(self, path, max_bytes=60000):
        p = self._safe(path)
        if not p.exists():
            return f"(no such file: {path})"
        data = p.read_text(encoding="utf-8", errors="replace")
        lines = data.splitlines()
        body = "\n".join(f"{i+1}\t{ln}" for i, ln in enumerate(lines))
        return body[:max_bytes] + ("\n...(truncated)" if len(body) > max_bytes else "")

    def grep(self, pattern, glob="**/*"):
        import re
        rx = re.compile(pattern)
        hits = []
        for f in self.root.glob(glob):
            if not f.is_file() or any(x in f.parts for x in (".git", ".litecode", "node_modules", "__pycache__")):
                continue
            try:
                for i, ln in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if rx.search(ln):
                        hits.append(f"{f.relative_to(self.root)}:{i}:{ln.strip()[:160]}")
                        if len(hits) >= 100:
                            return "\n".join(hits) + "\n...(100+ matches)"
            except Exception:
                pass
        return "\n".join(hits) or "(no matches)"

    # --- mutating (need approval) ---
    def write_file(self, path, content):
        p = self._safe(path)
        if not self.approve("write_file", f"{path} ({len(content)} bytes)"):
            return "(denied by user)"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"wrote {path} ({len(content)} bytes)"

    def run(self, cmd, shell="bash"):
        if not self.approve("run", f"[{shell}] {cmd}"):
            return "(denied by user)"
        exe = {"bash": ["bash", "-lc", cmd], "powershell": ["powershell", "-NoProfile", "-Command", cmd]}[shell]
        try:
            r = subprocess.run(exe, cwd=self.root, capture_output=True, text=True, timeout=120)
            out = (r.stdout + r.stderr).strip()
            return (out[:8000] + "\n...(truncated)") if len(out) > 8000 else (out or f"(exit {r.returncode}, no output)")
        except subprocess.TimeoutExpired:
            return "(command timed out after 120s)"

    # dispatch table for the agent
    def call(self, name, args: dict):
        fns = {
            "list_dir": lambda a: self.list_dir(a.get("path", ".")),
            "read_file": lambda a: self.read_file(a["path"]),
            "grep": lambda a: self.grep(a["pattern"], a.get("glob", "**/*")),
            "write_file": lambda a: self.write_file(a["path"], a.get("content", "")),
            "run": lambda a: self.run(a["cmd"], a.get("shell", "bash")),
        }
        if name not in fns:
            return f"(unknown tool: {name})"
        try:
            return fns[name](args)
        except KeyError as e:
            return f"(missing arg {e} for {name})"
        except Exception as e:
            return f"(tool error: {type(e).__name__}: {e})"


SPEC = """Available tools (reply with ONE JSON object per step):
- list_dir   {"tool":"list_dir","args":{"path":"."}}
- read_file  {"tool":"read_file","args":{"path":"src/x.py"}}
- grep       {"tool":"grep","args":{"pattern":"TODO","glob":"**/*.py"}}
- write_file {"tool":"write_file","args":{"path":"src/x.py","content":"..."}}
- run        {"tool":"run","args":{"cmd":"python -m pytest -q","shell":"bash"}}
- final      {"tool":"final","args":{"message":"what you did / the answer"}}"""
