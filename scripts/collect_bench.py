"""Collect benchmark results into docs/data/benchmarks.json for the website.

  python scripts/collect_bench.py [--speed results.csv] [--evals evals.jsonl]

Defaults read the reference machine's files. Keeps the newest eval run per model.
"""
from __future__ import annotations
import csv, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data" / "benchmarks.json"


def arg(name, default):
    return Path(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else Path(default)


def main():
    speed_p = arg("--speed", "D:/llm/bench/results.csv")
    evals_p = arg("--evals", "D:/llm/data/bench/evals.jsonl")
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    speed = {}
    if speed_p.exists():
        for r in csv.DictReader(speed_p.open(encoding="utf-8")):
            name = r["model"].replace("-fixed", "")
            row = {"model": name, "pp": r["pp_tok_s"], "tg": r["tg_tok_s"],
                   "coding": r["coding"], "security": r["security"], "tools": r["tools"]}
            if not row["tg"] and name in speed:
                continue          # keep an earlier row that has speed numbers
            speed[name] = row
    evals = {}
    if evals_p.exists():
        for ln in evals_p.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(ln)
            except Exception:
                continue
            if e.get("total", 0) >= 30:
                evals[e["model"]] = e          # newest full run wins
    data = {
        "machine": old.get("machine") or {
            "CPU": "AMD Ryzen 3 3200G, 4 cores / 4 threads (2019)",
            "RAM": "16 GB DDR4-2133, dual channel",
            "GPU": "none used (GT 710 is too old)",
            "Disk": "7200 rpm hard drive",
            "Engine": "llama.cpp CPU build, 4 threads, Q4_K_M models",
        },
        "speed": sorted(speed.values(), key=lambda r: -float(r["tg"] or 0)),
        "evals": [{k: v for k, v in e.items() if k != "results"} | {"results": e.get("results", [])}
                  for e in evals.values()],
        "notes": old.get("notes", []),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"wrote {OUT}: {len(data['speed'])} speed rows, {len(data['evals'])} eval runs")


if __name__ == "__main__":
    main()
