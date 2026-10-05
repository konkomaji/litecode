"""Config: defaults + ~/.litecode/config.toml overrides + installed-model registry."""
from __future__ import annotations
import os
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
MODELS_DIR = Path(os.environ.get("LITECODE_MODELS", "D:/llm/models"))
ENGINE = Path(os.environ.get("LITECODE_ENGINE", "D:/llm/engines/llamacpp-cpu/llama-server.exe"))

# Model roles, resolved to files in MODELS_DIR. Chosen from Phase-0 on-device tests.
DEFAULTS = {
    "engine": str(ENGINE),
    "models_dir": str(MODELS_DIR),
    "host": "127.0.0.1",
    "port": 8080,
    "threads": 4,
    "ctx": 8192,
    "kv_type": "q8_0",          # halves KV RAM, ~no quality loss
    "cache_ram_mb": 1024,       # llama.cpp default 8192 is too big for 16 GB
    "keep_resident": True,      # do not idle-unload (avoids HDD reload lag)
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
    cfg = {**DEFAULTS}
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
