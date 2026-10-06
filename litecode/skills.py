"""Skills: reusable instruction packs, like Claude Code skills.

A skill is a folder with a SKILL.md file:

    ---
    name: django-tests
    description: Write and run Django tests the way this team does
    triggers: django, test, pytest
    tools: read_file, edit_file, run
    ---
    Instructions for the model, in plain steps.

Search order (later wins on name clash):
  1. built-in   litecode/skills/*.md (shipped)
  2. user       <data_dir>/skills/<name>/SKILL.md
  3. project    <project>/.litecode/skills/<name>/SKILL.md

Use: type /<name> [task] to run a skill. A skill whose trigger words appear in a
task is also added to the context automatically (at most 2, to save tokens).
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path

BUILTIN_DIR = Path(__file__).parent / "skills"
NAME_RX = re.compile(r"^[a-z0-9][a-z0-9_-]{1,40}$")


@dataclass
class Skill:
    name: str
    description: str
    body: str
    triggers: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    scope: str = "builtin"
    path: Path | None = None

    def prompt(self) -> str:
        return f"Skill '{self.name}' is active. {self.description}\nFollow these steps:\n{self.body.strip()}"


def parse(text: str, scope: str = "user", path: Path | None = None) -> Skill | None:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return None
    meta = {}
    for ln in m.group(1).splitlines():
        if ":" in ln:
            k, v = ln.split(":", 1)
            meta[k.strip().lower()] = v.strip()
    name = meta.get("name", "").strip().lower()
    if not NAME_RX.match(name):
        return None
    split = lambda v: [x.strip().lower() for x in v.split(",") if x.strip()]
    return Skill(name=name, description=meta.get("description", ""), body=m.group(2),
                 triggers=split(meta.get("triggers", "")), tools=split(meta.get("tools", "")),
                 scope=scope, path=path)


def render(s: Skill) -> str:
    lines = ["---", f"name: {s.name}", f"description: {s.description}"]
    if s.triggers:
        lines.append("triggers: " + ", ".join(s.triggers))
    if s.tools:
        lines.append("tools: " + ", ".join(s.tools))
    lines += ["---", s.body.strip(), ""]
    return "\n".join(lines)


class Skills:
    def __init__(self, project_root: Path, data_dir: Path):
        self.project_dir = Path(project_root) / ".litecode" / "skills"
        self.user_dir = Path(data_dir) / "skills"
        self.items: dict[str, Skill] = {}
        self.reload()

    def reload(self):
        self.items = {}
        for p in sorted(BUILTIN_DIR.glob("*.md")):
            s = parse(p.read_text(encoding="utf-8"), "builtin", p)
            if s:
                self.items[s.name] = s
        for scope, d in (("user", self.user_dir), ("project", self.project_dir)):
            if d.exists():
                for p in sorted(d.glob("*/SKILL.md")):
                    s = parse(p.read_text(encoding="utf-8", errors="replace"), scope, p)
                    if s:
                        self.items[s.name] = s

    def get(self, name: str) -> Skill | None:
        return self.items.get(name.lower().lstrip("/"))

    def list(self) -> list[Skill]:
        return sorted(self.items.values(), key=lambda s: (s.scope, s.name))

    def match(self, task: str, limit: int = 2) -> list[Skill]:
        t = task.lower()
        words = set(re.findall(r"[a-z0-9_+#.-]+", t))
        scored = []
        for s in self.items.values():
            hits = sum(1 for tr in s.triggers if (tr in words if " " not in tr else tr in t))
            if hits:
                scored.append((hits, s))
        rank = {"project": 0, "user": 1, "builtin": 2}
        scored.sort(key=lambda x: (-x[0], rank.get(x[1].scope, 3)))
        return [s for _, s in scored[:limit]]

    def create(self, name: str, description: str, body: str, triggers=None, tools=None,
               scope: str = "project") -> Path:
        name = name.strip().lower()
        if not NAME_RX.match(name):
            raise ValueError("skill name: 2-41 chars, lowercase letters, digits, - or _")
        base = self.project_dir if scope == "project" else self.user_dir
        p = base / name / "SKILL.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(render(Skill(name, description, body, list(triggers or []), list(tools or []), scope)),
                     encoding="utf-8")
        self.reload()
        return p

    def remove(self, name: str) -> bool:
        s = self.get(name)
        if not s or s.scope == "builtin" or not s.path:
            return False
        s.path.unlink()
        try:
            s.path.parent.rmdir()
        except OSError:
            pass
        self.reload()
        return True


DRAFT_PROMPT = """Write a litecode skill: a short instruction pack another small model will follow.
Reply with ONLY the file content in this exact format:
---
name: <lowercase-name>
description: <one sentence>
triggers: <comma separated keywords>
---
1. <step>
2. <step>
Use 3 to 8 short numbered steps. Use simple words. Name the tools to use (read_file, grep, edit_file, run, scan)."""


def draft_with_model(server, request: str) -> Skill | None:
    reply = server.chat([{"role": "system", "content": DRAFT_PROMPT},
                         {"role": "user", "content": request}], max_tokens=500, temperature=0.2)
    reply = re.sub(r"^```\w*\n|```\s*$", "", reply.strip())
    return parse(reply.strip() + "\n", "project")
