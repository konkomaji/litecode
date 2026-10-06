"""Challenge suite: real agent tasks, scored by checks, on your machine.

  litecode eval [NAME...] [--level basic|medium|hard] [--kind KIND] [--role R] [--model FILE.gguf]

Each challenge builds a small project in a temp folder, gives the agent a task in
auto mode, then checks the result by running code. Per challenge litecode records:
pass, seconds, generated tokens, tool calls, protocol errors, and step-budget hits.
Results are appended to <data_dir>/bench/evals.jsonl.
"""
from __future__ import annotations
import json, os, platform, shutil, subprocess, sys, tempfile, time
from pathlib import Path
from .challenges import CHALLENGES, LEVELS, KINDS


def _run(root: Path, code: str, answer: str = "") -> tuple[bool, str]:
    env = {**os.environ, "ANSWER": answer, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        r = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True,
                           timeout=90, env=env)
    except subprocess.TimeoutExpired:
        return False, "check timed out"
    return r.returncode == 0, (r.stdout + r.stderr)[-300:]


def select(only=None, level=None, kind=None):
    return [c for c in CHALLENGES
            if (not only or c.name in only) and (not level or c.level == level) and (not kind or c.kind == kind)]


def _scores(results, key):
    agg = {}
    for r in results:
        a = agg.setdefault(r[key], [0, 0])
        a[0] += r["pass"]
        a[1] += 1
    return {k: f"{v[0]}/{v[1]}" for k, v in agg.items()}


def run(role: str | None = None, only=None, log=print, model_file: str | None = None,
        level: str | None = None, kind: str | None = None) -> dict:
    from . import config
    from .server import Server
    from .agent import Agent
    from .router import PROFILES
    cfg = config.load()
    if model_file:
        role = role or "code"
        cfg["roles"][role] = model_file
    avail = config.available_roles(cfg)
    if not avail:
        log("No models installed. Run `litecode setup` first.")
        return {}
    role = role or ("code" if "code" in avail else next(iter(avail)))
    if role not in avail:
        log(f"No model file for role '{role}'.")
        return {}
    model = avail[role].name
    chosen = select(only, level, kind)
    srv = Server(cfg)
    srv.ensure(role)
    prof = dict(PROFILES.get(role, PROFILES["code"]), role=role)
    steps = int(cfg.get("eval_max_steps", 12))
    results = []
    tmp_root = Path(tempfile.mkdtemp(prefix="litecode-eval-"))
    ecfg = {**cfg, "data_dir": str(tmp_root / "_data"), "project_memory": "project", "auto_learn": False}
    log(f"{model}: {len(chosen)} challenges, max {steps} steps each")
    try:
        for ch in chosen:
            root = tmp_root / ch.name
            root.mkdir(parents=True)
            for rel, body in ch.files.items():
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(body, encoding="utf-8")
            counts = {"tool": 0, "parse_retry": 0}

            def ev(k, d, counts=counts):
                if k in counts:
                    counts[k] += 1
            agent = Agent(srv, root, lambda *a: True, max_steps=steps, cfg=ecfg, mode="auto", on_event=ev)
            t0, g0 = time.time(), srv.stats.gen_tokens
            try:
                answer, err = agent.run(ch.task, prof, record=False), ""
            except Exception as e:
                answer, err = "", f"{type(e).__name__}: {e}"
            ok, out = (False, err) if err else _run(root, ch.check, answer)
            r = {"challenge": ch.name, "level": ch.level, "kind": ch.kind, "pass": ok,
                 "seconds": round(time.time() - t0, 1), "tokens": srv.stats.gen_tokens - g0,
                 "tools": counts["tool"], "protocol_errors": counts["parse_retry"],
                 "budget_hit": answer == "(step budget exhausted)",
                 "detail": "" if ok else out.strip()[-200:]}
            results.append(r)
            log(f"  {'PASS' if ok else 'FAIL'}  {ch.level:<6} {ch.kind:<9} {ch.name:<24} {r['seconds']:6.1f}s "
                f"{r['tokens']:5d} tok {r['tools']:2d} tools" + ("" if ok else f"   {r['detail'][:90]}"))
    finally:
        srv.stop()
        shutil.rmtree(tmp_root, ignore_errors=True)
    passed = sum(r["pass"] for r in results)
    summary = {"time": time.strftime("%Y-%m-%d %H:%M"), "host": platform.node(), "threads": cfg["threads"],
               "role": role, "model": model, "passed": passed, "total": len(results),
               "by_level": _scores(results, "level"), "by_kind": _scores(results, "kind"),
               "seconds": round(sum(r["seconds"] for r in results), 1),
               "tokens": sum(r["tokens"] for r in results),
               "protocol_errors": sum(r["protocol_errors"] for r in results), "results": results}
    log(f"{model}: {passed}/{len(results)} passed  levels {summary['by_level']}  in {summary['seconds']:.0f}s")
    out = config.data_path(cfg, "bench") / "evals.jsonl"
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(summary) + "\n")
    return summary
