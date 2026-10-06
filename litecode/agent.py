"""Agent loop. Small models are unreliable with native tool-calling, so litecode
uses a strict one-JSON-action-per-step protocol with lenient parsing.

Context comes from memory.ContextBuilder: rules, user profile, project brief,
facts, active skills, similar past tasks, a summary of older turns, and the
recent turns, all inside a character budget.
"""
from __future__ import annotations
import json, re, time
from pathlib import Path
from . import config, learn
from .tools import Tools, SPEC
from .memory import Memory, ContextBuilder

SYSTEM_FILE = Path(__file__).parent / "SYSTEM.md"
JSON_RE = re.compile(r"\{.*\}", re.S)

# GBNF grammar: forces the exact 4-line verdict, so a small model cannot ramble
REVIEW_GRAMMAR = r'''root ::= "VERDICT: " v "\nSEVERITY: " s "\nWHY: " line "\nFIX: " line
v ::= "real" | "false-positive" | "needs-context"
s ::= "high" | "medium" | "low"
line ::= [^\n]{4,240}
'''
MENTION_RE = re.compile(r"(?<!\S)@([\w./\\-]+)")


def load_system(cfg: dict) -> str:
    """User override in <data_dir>/SYSTEM.md, else the shipped SYSTEM.md."""
    p = Path(cfg.get("data_dir") or config.HOME) / "SYSTEM.md"
    if not p.exists():
        p = SYSTEM_FILE
    return p.read_text(encoding="utf-8")


def _parse_action(text: str) -> dict | None:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = JSON_RE.search(text)
    if not m:
        return None
    blob = m.group(0)
    depth, end, in_str, esc = 0, None, False, False
    for i, ch in enumerate(blob):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end:
        blob = blob[:end]
    try:
        obj = json.loads(blob)
    except Exception:
        try:
            obj = json.loads(blob.replace("\n", "\\n"))
        except Exception:
            return None
    if not isinstance(obj, dict) or "tool" not in obj:
        return None
    if not isinstance(obj.get("args"), dict):
        obj["args"] = {}
    return obj


def expand_mentions(task: str, root: Path, max_files=3, max_chars=6000) -> tuple[str, list[str]]:
    """@path/to/file in a task attaches that file's content."""
    root = Path(root).resolve()
    added, blocks = [], []
    for m in MENTION_RE.finditer(task):
        rel = m.group(1).rstrip(".,;:")
        p = (root / rel).resolve()
        if (root in p.parents) and p.is_file() and rel not in added and len(added) < max_files:
            body = p.read_text(encoding="utf-8", errors="replace")
            blocks.append(f"File {rel}:\n```\n{body[:max_chars]}\n```" +
                          ("\n(truncated)" if len(body) > max_chars else ""))
            added.append(rel)
    return (task + "\n\n" + "\n\n".join(blocks)) if blocks else task, added


class Agent:
    def __init__(self, server, root: Path, approve, max_steps=24, on_event=None,
                 session=None, ctx_budget=16000, cfg=None, mode="ask", skills=None, mcp=None):
        self.cfg = cfg or config.load()
        self.server = server
        self.root = Path(root)
        self.mem = Memory(self.root, self.cfg)
        self.mcp = mcp
        self.tools = Tools(self.root, approve, memory=self.mem, mode=mode, mcp=mcp)
        self.skills = skills
        self.max_steps = max_steps
        self.on_event = on_event or (lambda kind, data: None)
        self.session = session or self.mem.new_session()
        self.ctx = ContextBuilder(self.mem, budget_chars=ctx_budget, summarize=self._model_summarize)

    def _model_summarize(self, turns):
        """Summarize old turns with the model so context survives compaction."""
        text = "\n".join(f"{t['role']}: {t['content'][:500]}" for t in turns)
        try:
            return self.server.chat(
                [{"role": "system", "content": "Summarize the key facts, decisions, file changes, "
                  "and open threads from this transcript in under 180 words. Be concrete."},
                 {"role": "user", "content": text[:12000]}],
                max_tokens=320, thinking=False)
        except Exception:
            return self.ctx._heuristic_summary(turns)

    def _spec(self) -> str:
        spec = SPEC
        if self.mcp is not None:
            extra = self.mcp.spec_text()
            if extra:
                spec += "\n" + extra
        return spec

    def _skills_text(self, task: str, skill=None) -> str:
        active = [skill] if skill else (self.skills.match(task) if self.skills else [])
        return "\n\n".join(s.prompt() for s in active if s)

    def run(self, task: str, profile: dict | None = None, skill=None, record=True) -> str:
        prof = profile or {}
        max_tokens = prof.get("max_tokens", 1200)
        thinking = prof.get("thinking", False)
        for pref in learn.capture_preferences(task):
            if self.mem.prefer(pref):
                self.on_event("learned", pref)
        full_task, attached = expand_mentions(task, self.root)
        if attached:
            self.on_event("attached", attached)
        if skill:
            self.on_event("skill", skill.name)
        base = load_system(self.cfg).replace("{spec}", self._spec())
        msgs = self.ctx.build(self.session, base, full_task, self._skills_text(task, skill))
        head = len(msgs)
        self.mem.append_turn(self.session, "user", task)
        self.tools.changed = []
        last_call, bad = None, 0
        for _ in range(self.max_steps):
            streamer = self._streamer()
            reply = self.server.chat(msgs, max_tokens=max_tokens, thinking=thinking,
                                     on_token=streamer.feed if streamer else None)
            act = _parse_action(reply)
            if act is None:
                bad += 1
                plain = re.sub(r"<think>.*?</think>", "", reply, flags=re.S).strip()
                if bad >= 2 and plain:
                    # small models sometimes answer in prose; accept it rather than loop
                    act = {"tool": "final", "args": {"message": plain}}
                else:
                    msgs.append({"role": "assistant", "content": reply})
                    msgs.append({"role": "user", "content": "Reply with ONE valid JSON tool object only."})
                    self.on_event("parse_retry", reply[:200])
                    continue
            tool, args = act["tool"], act.get("args", {})
            if act.get("thought"):
                self.on_event("thought", str(act["thought"]))
            if tool == "final":
                answer = str(args.get("message", "")).strip() or "(done)"
                self.on_event("final", {"text": answer, "streamed": bool(streamer and streamer.shown)})
                self.mem.append_turn(self.session, "assistant", answer)
                if record:
                    self.mem.add_example(task, answer, files=list(dict.fromkeys(self.tools.changed)),
                                         role=prof.get("role", ""))
                return answer
            call = (tool, json.dumps(args, sort_keys=True))
            if call == last_call:
                obs = "(you already ran this exact call; use its result or choose a different step)"
            else:
                self.on_event("tool", {"tool": tool, "args": args})
                obs = str(self.tools.call(tool, args))
                self.on_event("observation", obs[:400])
                self._learn_from_tool(tool, args, obs)
            last_call = call
            msgs.append({"role": "assistant", "content": json.dumps(act, ensure_ascii=False)})
            msgs.append({"role": "user", "content": f"OBSERVATION:\n{obs[:6000]}"})
            self.mem.append_turn(self.session, "assistant", json.dumps(act, ensure_ascii=False))
            self.mem.append_turn(self.session, "user", f"OBSERVATION: {obs[:500]}")
            if len(msgs) > head + 16:
                # keep system, summary, history and task; drop the oldest tool steps in pairs
                msgs = msgs[:head] + msgs[-14:]
        self.on_event("final", {"text": "(step budget exhausted)", "streamed": False})
        return "(step budget exhausted)"

    TEST_CMD = re.compile(r"\b(pytest|unittest|npm (run )?test|yarn test|go test|cargo test|mvn test|"
                          r"gradle test|phpunit|rspec|test_\w+\.py|\w+_test\.py)\b")

    def _learn_from_tool(self, tool, args, obs):
        """Zero-cost fact capture: a test command that passed is worth remembering."""
        if tool == "run" and obs.startswith("(exit 0") and self.TEST_CMD.search(str(args.get("cmd", ""))):
            if self.mem.remember(f"Test command that works: {args['cmd']}", "learned"):
                self.on_event("learned", f"test command: {args['cmd']}")

    def _streamer(self):
        from .ui import FieldStreamer
        emit = lambda s: self.on_event("stream", s)
        return FieldStreamer(emit)

    # --- workflows ---
    def plan(self, task: str, profile=None) -> str:
        old = self.tools.mode
        self.tools.mode = "readonly"
        try:
            return self.run("PLAN MODE. Do not change files. Inspect only what you need. Then reply with "
                            "final: a numbered plan of concrete steps (files, changes, how to test).\n\nTask: "
                            + task, profile, record=False)
        finally:
            self.tools.mode = old

    def review(self, path: str = ".", max_findings: int = 10, profile=None) -> str:
        from . import scan as sc
        fs = sc.scan(self.root, path)
        self.on_event("observation", f"scan: {len(fs)} findings")
        if not fs:
            return "No findings from static analysis. The scan does not prove the code is safe."
        lines = [f"# Security review: {path}", "", f"Static findings: {len(fs)}. Model checked the top {min(len(fs), max_findings)}.", ""]
        for f in fs[:max_findings]:
            code = sc.context_for(self.root, f)
            prompt = (f"Finding: {f.short()}\nCode:\n{code}\n\nIs this a real vulnerability in this code? "
                      "Reply in exactly 4 lines:\nVERDICT: real | false-positive | needs-context\n"
                      "SEVERITY: high | medium | low\nWHY: one sentence\nFIX: the smallest safe change")
            self.on_event("tool", {"tool": "review", "args": {"finding": f"{f.file}:{f.line}"}})
            try:
                ans = self.server.chat([{"role": "system", "content": "You are a precise security reviewer. "
                                         "Use simple words. No filler."},
                                        {"role": "user", "content": prompt}],
                                       max_tokens=200, thinking=False, temperature=0,
                                       grammar=REVIEW_GRAMMAR)
            except Exception as e:
                ans = f"(model error: {e})"
            lines += [f"## {f.file}:{f.line} {f.rule} ({f.cwe}, scanner: {f.severity})", "```", code, "```",
                      ans.strip(), ""]
        if len(fs) > max_findings:
            lines.append(f"Not checked by the model: {len(fs) - max_findings} more findings. Run `litecode scan`.")
        report = "\n".join(lines)
        out = self.mem.dir / "reviews" / (time.strftime("%Y%m%d-%H%M%S") + ".md")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        self.on_event("saved", str(out))
        return report

    def testfix(self, cmd: str, rounds: int = 3, profile=None) -> str:
        for i in range(rounds + 1):
            out = self.tools.run(cmd)
            self.on_event("observation", out[:400])
            if out.startswith("(exit 0"):
                return f"Tests pass after {i} fix round(s). Command: {cmd}"
            if out.startswith("(denied"):
                return out
            if i == rounds:
                break
            self.run(f"The test command `{cmd}` fails. Output (end):\n{out[-3000:]}\n\n"
                     f"Fix the code so the tests pass. Fix the code, not the tests, unless a test is wrong. "
                     f"Then reply final with what you changed.", profile)
        return f"Tests still fail after {rounds} rounds. Command: {cmd}"

    def commit_message(self) -> str:
        diff = self.tools.git_diff()
        if diff.startswith("(") and "no output" in diff:
            diff = self.tools._git("diff", "--cached")
        if not diff.strip() or "no output" in diff:
            return ""
        msg = self.server.chat([{"role": "system", "content": "Write a git commit message. Line 1: imperative "
                                 "subject, max 60 chars. Optional body after a blank line, max 3 short lines. "
                                 "Reply with the message only."},
                                {"role": "user", "content": diff[:8000]}], max_tokens=150, temperature=0)
        return msg.strip().strip("`").strip()
