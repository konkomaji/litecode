"""Config: defaults + ~/.litecode/config.toml overrides + installed-model registry."""
from __future__ import annotations
import copy, os
from pathlib import Path

try:
    import tomllib  # Python 3.11+
    def _parse_toml(text: str) -> dict:
        return tomllib.loads(text)
except ModuleNotFoundError:
    def _parse_toml(text: str) -> dict:
        """Minimal TOML subset: flat key=value and [section] tables, string/int/bool.
        Enough for litecode's own generated config; keeps the tool dependency-free on 3.10."""
        out: dict = {}
        cur = out
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            if line.startswith("[") and line.endswith("]"):
                cur = out.setdefault(line[1:-1].strip(), {})
                continue
            if "=" not in line:
                continue
            k, v = (x.strip() for x in line.split("=", 1))
            if v and v[0] in "\"'" and v[-1] == v[0]:
                val = v[1:-1]
            elif v.lower() in ("true", "false"):
                val = v.lower() == "true"
            else:
                try:
                    val = int(v)
                except ValueError:
                    try:
                        val = float(v)
                    except ValueError:
                        val = v
            cur[k] = val
        return out

HOME = Path(os.path.expanduser("~")) / ".litecode"
_EXE = ".exe" if os.name == "nt" else ""
MODELS_DIR = Path(os.environ.get("LITECODE_MODELS", str(HOME / "models")))
ENGINE = Path(os.environ.get("LITECODE_ENGINE", str(HOME / "engine" / f"llama-server{_EXE}")))

# Model roles, resolved to files in MODELS_DIR. Chosen from Phase-0 on-device tests.
DEFAULTS = {
    "engine": str(ENGINE),
    "data_dir": str(HOME),      # cache, KV slots, scratchpad, global memory, skills (user picks in setup)
    "project_memory": "project",  # project = <project>/.litecode ; central = <data_dir>/projects/<id>
    "models_dir": str(MODELS_DIR),
    "host": "127.0.0.1",
    "port": 8080,
    "threads": 4,
    "ctx": 8192,
    "kv_type": "q8_0",          # halves KV RAM, ~no quality loss
    "cache_ram_mb": 1024,       # llama.cpp default 8192 is too big for 16 GB
    "keep_resident": True,      # do not idle-unload (avoids HDD reload lag)
    "fim_port": 8081,           # separate resident autocomplete server
    "gpu_layers": 0,            # >0 offloads layers (Vulkan/CUDA engine builds only)
    "speculative": "auto",      # auto | off | ngram-simple | ngram-mod | draft
    "kv_persist": True,         # save/restore the prompt KV cache per project
    "permission": "ask",        # ask | auto | readonly
    "auto_learn": True,         # extract project facts at session end (one short model call)
    "lora": "",                 # optional LoRA adapter (.gguf) trained from `litecode learn export`
    "roles": {
        # role -> gguf filename (relative to models_dir)
        "code":   "MiniCPM5-2B-Q4_K_M.gguf",             # coding leader on-device
        "fim":    "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
        "chat":   "MiniCPM5-2B-Q4_K_M.gguf",
        "security": "foundation-sec-8b-reasoning-q4_k_m.gguf",  # loads when present
        "quality": "Qwen3.5-9B-Q4_K_M.gguf",
    },
    "max_steps": 24,            # agent tool-call budget per task
    "temperature": 0.1,
}


def load() -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    p = HOME / "config.toml"
    if p.exists():
        try:
            user = _parse_toml(p.read_text(encoding="utf-8"))
            for k, v in user.items():
                if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
        except Exception as e:
            print(f"litecode: ignoring bad config.toml ({e})")
    return cfg


def model_path(cfg: dict, role: str) -> Path | None:
    fn = cfg["roles"].get(role)
    if not fn:
        return None
    p = Path(cfg["models_dir"]) / fn
    return p if p.exists() else None


def available_roles(cfg: dict) -> dict:
    """roles whose model file actually exists on disk right now."""
    return {r: model_path(cfg, r) for r in cfg["roles"] if model_path(cfg, r)}


def save(updates: dict) -> Path:
    """Merge `updates` into ~/.litecode/config.toml (flat keys and [roles])."""
    p = HOME / "config.toml"
    cur = _parse_toml(p.read_text(encoding="utf-8")) if p.exists() else {}
    for k, v in updates.items():
        if isinstance(v, dict):
            cur.setdefault(k, {}).update(v)
        else:
            cur[k] = v

    def fmt(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return str(v)
        return '"' + str(v).replace("\\", "/") + '"'

    lines = ["# litecode config"]
    lines += [f"{k} = {fmt(v)}" for k, v in cur.items() if not isinstance(v, dict)]
    for k, v in cur.items():
        if isinstance(v, dict):
            lines += ["", f"[{k}]"] + [f"{kk} = {fmt(vv)}" for kk, vv in v.items()]
    HOME.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def data_path(cfg: dict, *parts: str) -> Path:
    """A folder under the user-selected data_dir (created on demand)."""
    p = Path(cfg.get("data_dir") or HOME).joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p
