"""Project memory: a .litecode/ folder per project holds context and session history.

LITECODE.md is the human-editable project brief (like a README for the agent):
goals, conventions, build/test commands. It is injected into every system prompt.
"""
from __future__ import annotations
import json, time
from pathlib import Path

DIRNAME = ".litecode"
BRIEF = "LITECODE.md"

BRIEF_TEMPLATE = """# Project brief for litecode

Describe this project so the assistant has context. Edit freely.

## What this project is
(one or two lines)

## Conventions
(language, style, frameworks to match)

## Commands
- build:
- test:
- run:

## Notes
(anything the assistant should always keep in mind)
"""


class Memory:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.dir = self.root / DIRNAME
        self.dir.mkdir(exist_ok=True)
        self.history_path = self.dir / "history.jsonl"

    def brief(self) -> str:
        p = self.root / BRIEF
        if not p.exists():
            p = self.dir / BRIEF
        return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""

    def ensure_brief(self) -> Path:
        p = self.root / BRIEF
        if not p.exists():
            p.write_text(BRIEF_TEMPLATE, encoding="utf-8")
        return p

    def log(self, role: str, content: str):
        rec = {"t": time.time(), "role": role, "content": content[:4000]}
        with self.history_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def recent(self, n=20) -> list[dict]:
        if not self.history_path.exists():
            return []
        lines = self.history_path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
        out = []
        for ln in lines:
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
        return out
