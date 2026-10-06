"""Learning from use, without retraining weights on the user's PC.

Weight fine-tuning a 2B+ model on a 4-core CPU takes days, so litecode improves in
three cheap ways instead, every session, automatically:

1. Preference capture: user messages like "always use type hints" or "don't add
   comments" go into the global profile. Rule-based, zero model tokens.
2. Fact capture: when a session ends, the model extracts durable project facts
   (build commands, conventions, decisions) into project memory.
3. Example retrieval: every finished task is stored with its outcome (/good, /bad,
   tests passed). Similar later tasks get the best past result as an example.

For real fine-tuning, `litecode learn export` writes a chat-format JSONL dataset
from the rated history. Train a LoRA on a GPU machine (for example a free Colab),
convert it to GGUF, and set `lora = "path/to/adapter.gguf"` in config.toml. The
server loads it on the next start.
"""
from __future__ import annotations
import json, re
from pathlib import Path

PREF_RX = re.compile(
    r"^\s*(?:please\s+)?(always|never|don'?t|do not|stop|prefer|i prefer|i want|i like|use .+ instead of|"
    r"from now on|make sure to|avoid)\b(.{4,200})$", re.I)
NOT_PREF = re.compile(r"\?\s*$")


def capture_preferences(text: str) -> list[str]:
    """Find standing instructions in a user message. One per line or sentence."""
    out = []
    for part in re.split(r"(?<=[.!])\s+|\n", text):
        part = part.strip()
        if len(part) < 8 or len(part) > 220 or NOT_PREF.search(part):
            continue
        if PREF_RX.match(part):
            out.append(part.rstrip("."))
    return out


EXTRACT_PROMPT = """From this coding session transcript, list durable facts worth remembering for future
sessions in this project: build/test/run commands, conventions, file layout, decisions, known problems.
Skip anything temporary. Reply with JSON only: {"facts": ["...", "..."]} with at most 6 short facts.
Example: {"facts": ["Tests run with: python -m pytest -q", "Config lives in settings/base.py"]}
If nothing is worth keeping, reply {"facts": []}."""


FACTS_GRAMMAR = r'''root ::= "{\"facts\": [" ( fact ( ", " fact ){0,5} )? "]}"
fact ::= "\"" [^"\\\n]{5,200} "\""
'''


def extract_facts(server, turns: list[dict], max_chars=8000) -> list[str]:
    if not turns:
        return []
    text = "\n".join(f"{t['role']}: {t['content'][:400]}" for t in turns)[-max_chars:]
    try:
        reply = server.chat([{"role": "system", "content": EXTRACT_PROMPT},
                             {"role": "user", "content": text}], max_tokens=300, thinking=False,
                            temperature=0, grammar=FACTS_GRAMMAR)
    except Exception:
        return []
    m = re.search(r"\{.*\}", reply, re.S)
    if not m:
        return []
    try:
        facts = json.loads(m.group(0)).get("facts", [])
    except Exception:
        return []
    return [f.strip() for f in facts if isinstance(f, str) and 5 < len(f.strip()) < 240][:6]


def end_of_session(server, mem, sid: str, use_model=True) -> list[str]:
    """Called when a session ends. Stores extracted facts. Returns what was saved."""
    saved = []
    if use_model and server is not None:
        for f in extract_facts(server, mem.turns(sid)):
            if mem.remember(f, "learned"):
                saved.append(f)
    return saved


def export_dataset(mem, out: Path, include_unrated=False) -> int:
    """Write chat-format JSONL ({"messages":[...]}) for LoRA training elsewhere."""
    from .memory import _read_jsonl
    rows = 0
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    prefs = [p["text"] for p in mem.profile(100)]
    sys_txt = "You are litecode, a concise local coding assistant."
    if prefs:
        sys_txt += " User preferences: " + "; ".join(prefs)
    with out.open("w", encoding="utf-8") as f:
        for e in _read_jsonl(mem.examples_path):
            if e.get("ok") is False or (e.get("ok") is None and not include_unrated):
                continue
            f.write(json.dumps({"messages": [
                {"role": "system", "content": sys_txt},
                {"role": "user", "content": e["task"]},
                {"role": "assistant", "content": e["answer"]}]}, ensure_ascii=False) + "\n")
            rows += 1
    return rows
