"""Context and memory system for litecode.

Project memory (in <project>/.litecode/, or <data_dir>/projects/<id>/ when
project_memory = "central"):

  memory.jsonl           long-term facts about this project (decisions, conventions)
  sessions/<id>.jsonl    full turn history of every session (auto-captured, resumable)
  summaries/<id>.md      compacted summary of older turns
  checkpoints/           file snapshots for /undo

Global memory (in <data_dir>/, shared by all projects):

  profile.jsonl          what the user wants: style, preferences, corrections
  learn/examples.jsonl   finished tasks with outcome, retrieved as examples later
  scratch/<session>/     scratchpad files

ContextBuilder assembles the prompt inside a character budget. Small models have
small context windows, so old turns fold into a summary.
"""
from __future__ import annotations
import hashlib, json, re, time, uuid
from pathlib import Path

DIRNAME = ".litecode"
BRIEF = "LITECODE.md"

BRIEF_TEMPLATE = """# Project brief for litecode

Describe this project so the assistant always has context. Edit freely.

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


def _read_jsonl(p: Path, limit: int | None = None) -> list[dict]:
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    if limit:
        lines = lines[-limit:]
    out = []
    for ln in lines:
        try:
            out.append(json.loads(ln))
        except Exception:
            pass
    return out


def _append_jsonl(p: Path, rec: dict):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


_WORD = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]{2,}")


def _words(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text)}


def project_id(root: Path) -> str:
    root = Path(root).resolve()
    h = hashlib.sha1(str(root).lower().encode()).hexdigest()[:10]
    return f"{root.name}-{h}"


class Memory:
    def __init__(self, root: Path, cfg: dict | None = None):
        from . import config
        self.cfg = cfg or config.load()
        self.root = Path(root).resolve()
        self.data = Path(self.cfg.get("data_dir") or config.HOME)
        if self.cfg.get("project_memory") == "central":
            self.dir = self.data / "projects" / project_id(self.root)
        else:
            self.dir = self.root / DIRNAME
        for sub in ("sessions", "summaries", "checkpoints"):
            (self.dir / sub).mkdir(parents=True, exist_ok=True)
        self.facts_path = self.dir / "memory.jsonl"
        self.profile_path = self.data / "profile.jsonl"
        self.examples_path = self.data / "learn" / "examples.jsonl"

    # --- project brief ---
    def brief(self) -> str:
        for p in (self.root / BRIEF, self.dir / BRIEF):
            if p.exists():
                return p.read_text(encoding="utf-8", errors="replace")
        return ""

    def ensure_brief(self) -> Path:
        p = self.root / BRIEF
        if not p.exists():
            p.write_text(BRIEF_TEMPLATE, encoding="utf-8")
        return p

    # --- long-term project facts ---
    def remember(self, text: str, kind: str = "fact"):
        text = text.strip()
        if not text:
            return None
        if any(f["text"].lower() == text.lower() for f in self.facts(200)):
            return None
        rec = {"t": time.time(), "kind": kind, "text": text}
        _append_jsonl(self.facts_path, rec)
        return rec

    def facts(self, limit: int = 50) -> list[dict]:
        return _read_jsonl(self.facts_path, limit)

    def forget_all(self):
        if self.facts_path.exists():
            self.facts_path.unlink()

    # --- global user profile (what the user wants, across projects) ---
    def prefer(self, text: str, kind: str = "preference"):
        text = text.strip()
        if not text or any(p["text"].lower() == text.lower() for p in self.profile(200)):
            return None
        rec = {"t": time.time(), "kind": kind, "text": text}
        _append_jsonl(self.profile_path, rec)
        return rec

    def profile(self, limit: int = 40) -> list[dict]:
        return _read_jsonl(self.profile_path, limit)

    def forget_profile(self):
        if self.profile_path.exists():
            self.profile_path.unlink()

    # --- examples: finished tasks, retrieved for similar future tasks ---
    def add_example(self, task: str, answer: str, ok: bool | None = None, files=None, role=""):
        rec = {"t": time.time(), "project": project_id(self.root), "task": task[:2000],
               "answer": answer[:3000], "ok": ok, "files": files or [], "role": role}
        _append_jsonl(self.examples_path, rec)
        return rec

    def rate_last_example(self, ok: bool) -> bool:
        ex = _read_jsonl(self.examples_path)
        if not ex:
            return False
        ex[-1]["ok"] = ok
        self.examples_path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in ex),
                                      encoding="utf-8")
        return True

    def similar_examples(self, task: str, k: int = 2, min_overlap: float = 0.25) -> list[dict]:
        """Keyword-overlap retrieval. No embeddings: cheap on a weak CPU."""
        q = _words(task)
        if not q:
            return []
        scored = []
        for e in _read_jsonl(self.examples_path, 2000):
            if e.get("ok") is False:
                continue
            w = _words(e["task"])
            if not w:
                continue
            score = len(q & w) / len(q | w)
            if e.get("ok"):
                score *= 1.3
            if score >= min_overlap:
                scored.append((score, e))
        scored.sort(key=lambda x: -x[0])
        return [e for _, e in scored[:k]]

    # --- sessions (auto-captured) ---
    def new_session(self) -> str:
        sid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
        (self.dir / "sessions" / f"{sid}.jsonl").touch()
        return sid

    def sessions(self) -> list[str]:
        return [p.stem for p in sorted((self.dir / "sessions").glob("*.jsonl"))]

    def latest_session(self) -> str | None:
        s = [x for x in self.sessions() if self._session_path(x).stat().st_size > 0]
        return s[-1] if s else None

    def _session_path(self, sid: str) -> Path:
        return self.dir / "sessions" / f"{sid}.jsonl"

    def append_turn(self, sid: str, role: str, content: str):
        _append_jsonl(self._session_path(sid), {"t": time.time(), "role": role, "content": content})

    def turns(self, sid: str) -> list[dict]:
        return _read_jsonl(self._session_path(sid))

    def scratch(self, sid: str) -> Path:
        p = self.data / "scratch" / sid
        p.mkdir(parents=True, exist_ok=True)
        return p

    # --- session summary (compaction target) ---
    def summary(self, sid: str) -> str:
        p = self.dir / "summaries" / f"{sid}.md"
        return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""

    def set_summary(self, sid: str, text: str):
        (self.dir / "summaries" / f"{sid}.md").write_text(text, encoding="utf-8")

    # --- checkpoints for undo ---
    @staticmethod
    def _cp_name(rel_path: str) -> str:
        return rel_path.replace("/", "__").replace("\\", "__").replace(":", "")

    def checkpoint(self, rel_path: str, data: str) -> None:
        stamp = f"{time.time_ns():020d}"   # monotonic sort order, even for edits in the same second
        (self.dir / "checkpoints" / f"{stamp}__{self._cp_name(rel_path)}").write_text(data, encoding="utf-8")

    def last_checkpoint(self, rel_path: str) -> Path | None:
        cands = sorted((self.dir / "checkpoints").glob(f"*__{self._cp_name(rel_path)}"))
        return cands[-1] if cands else None

    def pop_checkpoint(self, rel_path: str) -> str | None:
        """Return the newest snapshot and delete it, so repeated /undo walks back."""
        cp = self.last_checkpoint(rel_path)
        if cp is None:
            return None
        data = cp.read_text(encoding="utf-8")
        cp.unlink()
        return data


class ContextBuilder:
    """Assemble the message list for a task within a character budget.

    Layout: system prompt (rules + brief + profile + project facts + skills +
    similar past examples) + optional running summary + recent raw turns + task.
    When raw history exceeds the budget, the oldest turns fold into the summary.
    """

    def __init__(self, memory: Memory, budget_chars: int = 16000, keep_recent: int = 8,
                 summarize=None):
        self.mem = memory
        self.budget = budget_chars
        self.keep_recent = keep_recent
        self.summarize = summarize  # callable(list[dict]) -> str, else heuristic

    def _block(self, title: str, items: list[dict]) -> str:
        if not items:
            return ""
        return title + "\n" + "\n".join(f"- {i['text']}" for i in items)

    def system_text(self, base_system: str, task: str = "", skills_text: str = "") -> str:
        parts = [base_system]
        prof = self._block("What this user wants (always follow):", self.mem.profile(limit=25))
        if prof:
            parts.append(prof)
        brief = self.mem.brief()
        if brief:
            parts.append("Project brief:\n" + brief[:4000])
        fb = self._block("Remembered facts about this project:", self.mem.facts(limit=30))
        if fb:
            parts.append(fb)
        if skills_text:
            parts.append(skills_text)
        ex = self.mem.similar_examples(task) if task else []
        if ex:
            lines = [f"Task: {e['task'][:300]}\nResult: {e['answer'][:500]}" for e in ex]
            parts.append("Similar past tasks in your history (reuse what worked):\n" + "\n---\n".join(lines))
        return "\n\n".join(parts)

    def _heuristic_summary(self, turns: list[dict]) -> str:
        bullets = []
        for t in turns:
            c = t["content"].strip().replace("\n", " ")
            bullets.append(f"- {t['role']}: {c[:160]}")
        return "Earlier in this session:\n" + "\n".join(bullets[-40:])

    def compact(self, sid: str):
        """Fold older turns into the session summary if raw history is over budget."""
        turns = self.mem.turns(sid)
        raw = turns[-self.keep_recent:]
        older = turns[:-self.keep_recent]
        total = sum(len(t["content"]) for t in turns)
        if total <= self.budget or not older:
            return
        prev = self.mem.summary(sid)
        new = (self.summarize(older) if self.summarize else self._heuristic_summary(older))
        combined = (prev + "\n" + new).strip() if prev else new
        self.mem.set_summary(sid, combined[-self.budget // 2:])
        # archive the full history before trimming, so nothing captured is lost
        arch = self.mem.dir / "sessions" / f"{sid}.full.jsonl.bak"
        with arch.open("a", encoding="utf-8") as f:
            for t in older:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")
        p = self.mem._session_path(sid)
        with p.open("w", encoding="utf-8") as f:
            for t in raw:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")

    def build(self, sid: str, base_system: str, task: str, skills_text: str = "") -> list[dict]:
        self.compact(sid)
        msgs = [{"role": "system", "content": self.system_text(base_system, task, skills_text)}]
        summ = self.mem.summary(sid)
        if summ:
            msgs.append({"role": "user", "content": "Context summary so far:\n" + summ})
            msgs.append({"role": "assistant", "content": "Understood, I have the earlier context."})
        recent = self.mem.turns(sid)[-self.keep_recent:]
        # chat templates want alternating roles; merge consecutive same-role turns
        for t in recent:
            role = t["role"] if t["role"] in ("user", "assistant") else "user"
            if msgs[-1]["role"] == role and len(msgs) > 1:
                msgs[-1]["content"] += "\n" + t["content"]
            else:
                msgs.append({"role": role, "content": t["content"]})
        if msgs[-1]["role"] == "user" and len(msgs) > 1:
            msgs[-1]["content"] += "\n\n" + task
        else:
            msgs.append({"role": "user", "content": task})
        return msgs
