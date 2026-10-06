"""Install-time autotune and benchmark.

`litecode tune` measures this machine, then writes the best settings to config:
  1. threads: llama-bench generation speed at each thread count
  2. speculative decoding: real tok/s on a code-edit prompt with each n-gram mode,
     per role, so "auto" uses the measured winner
The report goes to <data_dir>/bench/<host>.json so users can share results.
"""
from __future__ import annotations
import json, platform, re, subprocess, time
from pathlib import Path
from . import config, doctor

EDIT_FILE = '''def parse(line):
    parts = line.strip().split(",")
    name = parts[0]
    age = int(parts[1])
    city = parts[2]
    return {"name": name, "age": age, "city": city}


def load(path):
    rows = []
    with open(path) as f:
        for line in f:
            rows.append(parse(line))
    return rows
'''
EDIT_TASK = ("Rewrite this file exactly, but rename the function `parse` to `parse_row` everywhere. "
             "Output only the full file.\n\n" + EDIT_FILE)


def bench_threads(cfg: dict, model: Path, candidates: list[int], log=print) -> dict:
    exe = Path(cfg["engine"]).with_name("llama-bench" + Path(cfg["engine"]).suffix)
    if not exe.exists():
        log("  llama-bench not found next to the engine; skipping thread sweep")
        return {}
    res = {}
    for t in candidates:
        try:
            r = subprocess.run([str(exe), "-m", str(model), "-p", "128", "-n", "32", "-t", str(t), "-r", "1",
                                "-o", "json"], capture_output=True, text=True, timeout=900)
            rows = json.loads(r.stdout or "[]")
        except Exception as e:
            log(f"  threads={t}: failed ({e})")
            continue
        pp = next((x["avg_ts"] for x in rows if x.get("n_prompt", 0) > 0 and x.get("n_gen", 0) == 0), 0)
        tg = next((x["avg_ts"] for x in rows if x.get("n_gen", 0) > 0), 0)
        res[t] = {"pp": round(pp, 2), "tg": round(tg, 2)}
        log(f"  threads={t}: prompt {pp:6.1f} tok/s, generate {tg:5.1f} tok/s")
    return res


def bench_spec(cfg: dict, role: str, modes=("none", "ngram-simple", "ngram-mod"), log=print) -> dict:
    from .server import Server
    res = {}
    for mode in modes:
        c = {**cfg, "speculative": mode, "kv_persist": False}
        srv = Server(c, port=cfg["port"] + 20, quiet=True)
        try:
            srv.ensure(role)
            if srv.spec_active != mode and mode != "none":
                log(f"  {role} spec={mode}: not supported by this model")
                continue
            msgs = [{"role": "user", "content": EDIT_TASK}]
            srv.chat(msgs, max_tokens=8, temperature=0)          # warm the prompt cache
            t0, g0 = srv.stats.seconds, srv.stats.gen_tokens
            srv.chat(msgs, max_tokens=220, temperature=0)
            secs = srv.stats.seconds - t0
            toks = srv.stats.gen_tokens - g0
            tps = toks / secs if secs else 0
            res[mode] = round(tps, 2)
            log(f"  {role} spec={mode}: {tps:5.1f} tok/s")
        except Exception as e:
            log(f"  {role} spec={mode}: failed ({e})")
        finally:
            srv.stop()
    return res


def run(roles=("code",), log=print) -> dict:
    cfg = config.load()
    env = doctor.detect()
    report = {"time": time.strftime("%Y-%m-%d %H:%M"), "host": platform.node(), "cpu": env.cpu,
              "cores": env.cores, "threads": env.threads, "ram_gb": round(env.ram_total_gb, 1),
              "os": env.os, "results": {}}
    avail = config.available_roles(cfg)
    if not avail:
        log("No models installed. Run `litecode setup` first.")
        return report
    first = next((r for r in roles if r in avail), next(iter(avail)))
    model = avail[first]
    log(f"Thread sweep on {model.name}:")
    cands = sorted({max(1, env.cores // 2), env.cores, env.threads})
    tr = bench_threads(cfg, model, cands, log)
    updates = {}
    if tr:
        best = max(tr, key=lambda t: tr[t]["tg"])
        updates["threads"] = best
        cfg["threads"] = best
        report["results"]["threads"] = tr
        log(f"  -> threads = {best}")
    spec_best = {}
    for role in roles:
        if role not in avail:
            continue
        log(f"Speculative decoding on role '{role}':")
        sr = bench_spec(cfg, role, log=log)
        if sr:
            win = max(sr, key=sr.get)
            # only enable drafting if it beats plain decoding by 5%
            if win != "none" and sr[win] < sr.get("none", 0) * 1.05:
                win = "none"
            spec_best[role] = win
            report["results"][f"spec_{role}"] = sr
            log(f"  -> {role}: {win}")
    if spec_best:
        updates["spec_tuned"] = spec_best
    if updates:
        config.save(updates)
        log(f"Saved to {config.HOME / 'config.toml'}")
    out = config.data_path(cfg, "bench") / (re.sub(r"\W+", "_", platform.node()) + ".json")
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"Report: {out}")
    return report
