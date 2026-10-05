"""Agent loop. Small models are unreliable with native tool-calling, so litecode
uses a strict one-JSON-action-per-step protocol with lenient parsing.
"""
from __future__ import annotations
import json, re
from pathlib import Path
from .tools import Tools, SPEC
from .memory import Memory

SYSTEM = """You are litecode, a local coding and security assistant running on a low-end PC.
You work step by step. At each step reply with EXACTLY ONE JSON object and nothing else.
Think briefly inside the "thought" field, then pick one tool.

{spec}

Rules:
- One JSON object per reply. No prose outside it. No markdown fences.
- Read before you write. Inspect files/dirs before editing.
- Prefer small, correct edits. After writing code, run tests or the file to verify.
- When the task is done, use "final" with a short summary.
- Never invent file contents you have not read.

Project brief:
{brief}
"""

JSON_RE = re.compile(r"\{.*\}", re.S)


def _parse_action(text: str) -> dict | None:
    m = JSON_RE.search(text)
    if not m:
        return None
    blob = m.group(0)
    # take the first balanced object
    depth = 0; end = None
    for i, ch in enumerate(blob):
        if ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1; break
    if end:
        blob = blob[:end]
    try:
        obj = json.loads(blob)
    except Exception:
        try:
            obj = json.loads(blob.replace("\n", "\\n"))
        except Exception:
            return None
    if "tool" not in obj:
        return None
    obj.setdefault("args", {})
    return obj


class Agent:
    def __init__(self, server, root: Path, approve, max_steps=24, on_event=None):
        self.server = server
        self.root = Path(root)
        self.tools = Tools(self.root, approve)
        self.mem = Memory(self.root)
        self.max_steps = max_steps
        self.on_event = on_event or (lambda kind, data: None)

    def run(self, task: str) -> str:
        sys_prompt = SYSTEM.format(spec=SPEC, brief=self.mem.brief() or "(none)")
        msgs = [{"role": "system", "content": sys_prompt},
                {"role": "user", "content": task}]
        self.mem.log("user", task)
        last = ""
        for step in range(1, self.max_steps + 1):
            reply = self.server.chat(msgs, max_tokens=1200, stop=None)
            act = _parse_action(reply)
            if act is None:
                # nudge the model back to protocol once
                msgs.append({"role": "assistant", "content": reply})
                msgs.append({"role": "user", "content": "Reply with ONE valid JSON tool object only."})
                self.on_event("parse_retry", reply[:200])
                continue
            tool = act["tool"]; args = act.get("args", {})
            if act.get("thought"):
                self.on_event("thought", act["thought"])
            if tool == "final":
                last = args.get("message", "")
                self.on_event("final", last)
                self.mem.log("assistant", last)
                return last
            self.on_event("tool", {"tool": tool, "args": args})
            obs = self.tools.call(tool, args)
            self.on_event("observation", obs[:400])
            msgs.append({"role": "assistant", "content": json.dumps(act)})
            msgs.append({"role": "user", "content": f"OBSERVATION:\n{obs}"})
            # keep context bounded on a low-RAM box
            if len(msgs) > 24:
                msgs = [msgs[0]] + msgs[-20:]
        self.on_event("final", "(step budget exhausted)")
        return last or "(step budget exhausted)"
