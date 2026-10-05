"""Curated, on-device-tested model catalog. The setup wizard recommends a set
that fits the detected RAM budget. Sizes/repos verified via the HF API (Phase 0).

ram_gb = approximate resident RAM at Q4 incl. a small KV cache.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Model:
    key: str
    name: str
    repo: str            # HF repo id
    file: str            # GGUF filename in repo
    size_gb: float       # download size
    ram_gb: float        # approx resident RAM
    roles: tuple         # which litecode roles it can serve
    note: str
    official_permissive: bool = False   # official low-safety release (for security work)

    @property
    def url(self) -> str:
        return f"https://huggingface.co/{self.repo}/resolve/main/{self.file}"


CATALOG = [
    # --- tiny side-cars ---
    Model("qwen-coder-0.5b", "Qwen2.5-Coder-0.5B", "Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF",
          "qwen2.5-coder-0.5b-instruct-q4_k_m.gguf", 0.5, 0.7, ("fim",), "fast autocomplete"),
    Model("qwen-coder-1.5b", "Qwen2.5-Coder-1.5B", "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF",
          "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf", 1.1, 1.5, ("fim", "code"), "autocomplete side-car (20 tok/s on-device)"),
    # --- small all-rounders ---
    Model("minicpm5-2b", "MiniCPM5-2B", "openbmb/MiniCPM5-2B-GGUF",
          "MiniCPM5-2B-Q4_K_M.gguf", 1.6, 2.3, ("code", "chat", "security"),
          "coding leader on-device: 8/8 coding, 10/10 vuln-ID, 14 tok/s"),
    Model("llama-3.2-3b", "Llama-3.2-3B", "unsloth/Llama-3.2-3B-Instruct-GGUF",
          "Llama-3.2-3B-Instruct-Q4_K_M.gguf", 2.0, 2.8, ("chat",), "general chat"),
    Model("qwen3.5-4b", "Qwen3.5-4B", "unsloth/Qwen3.5-4B-GGUF",
          "Qwen3.5-4B-Q4_K_M.gguf", 2.7, 3.6, ("chat", "code"), "vision-capable general"),
    # --- fast MoE general ---
    Model("lfm2.5-8b-a1b", "LFM2.5-8B-A1B", "LiquidAI/LFM2.5-8B-A1B-GGUF",
          "LFM2.5-8B-A1B-Q4_K_M.gguf", 5.2, 6.0, ("chat", "code"), "MoE, ~22 tok/s, fast general"),
    # --- translation / multilingual ---
    Model("gemma-4-e4b", "Gemma-4-E4B", "unsloth/gemma-4-E4B-it-GGUF",
          "gemma-4-E4B-it-Q4_K_M.gguf", 5.0, 5.8, ("chat", "translate"), "multilingual + audio in"),
    # --- security-permissive (authorized pentest) ---
    Model("whiterabbitneo-v3-7b", "WhiteRabbitNeo-V3-7B", "bartowski/WhiteRabbitNeo_WhiteRabbitNeo-V3-7B-GGUF",
          "WhiteRabbitNeo_WhiteRabbitNeo-V3-7B-Q4_K_M.gguf", 4.7, 5.5, ("security", "code"),
          "official offensive-security model, Qwen2.5-Coder base", official_permissive=True),
    Model("foundation-sec-8b", "Foundation-Sec-8B-Reasoning", "fdtn-ai/Foundation-Sec-8B-Reasoning-Q4_K_M-GGUF",
          "foundation-sec-8b-reasoning-q4_k_m.gguf", 4.9, 5.7, ("security",),
          "Cisco security analyst model", official_permissive=True),
    Model("ministral-8b", "Ministral-8B", "bartowski/Ministral-8B-Instruct-2410-GGUF",
          "Ministral-8B-Instruct-2410-Q4_K_M.gguf", 4.9, 5.7, ("chat", "security"),
          "officially light-moderation instruct", official_permissive=True),
    # --- quality tier (slow on CPU) ---
    Model("qwen3.5-9b", "Qwen3.5-9B", "unsloth/Qwen3.5-9B-GGUF",
          "Qwen3.5-9B-Q4_K_M.gguf", 5.7, 6.6, ("chat", "code", "security"),
          "highest quality that fits 16 GB; ~3.5 tok/s"),
    Model("qwen3.6-35b-a3b", "Qwen3.6-35B-A3B", "unsloth/Qwen3.6-35B-A3B-GGUF",
          "Qwen3.6-35B-A3B-Q4_K_M.gguf", 22.0, 23.5, ("code", "chat", "security"),
          "needs 32 GB RAM; MoE ~11 tok/s; SWE-bench 73"),
]

BY_KEY = {m.key: m for m in CATALOG}


def recommend(budget_gb: float, want_security=True, want_fim=True, has_gpu=False) -> dict:
    """Pick a role->Model set that scales to the machine. Low-end picks small, fast,
    on-device-tested models; a bigger RAM budget or a real GPU unlocks the quality tier.
    Returns {role: Model}."""
    pick = {}

    def fits(m, extra=0.0):
        return m.ram_gb <= budget_gb - extra

    # Core coder/chat model. Scale the ceiling with hardware instead of always picking small.
    # Keep ~1.5 GB headroom for a resident fim side-car.
    core_budget = max(1.5, budget_gb - 1.6)
    if budget_gb >= 22 or (has_gpu and budget_gb >= 12):
        order = ["qwen3.6-35b-a3b", "qwen3.5-9b", "lfm2.5-8b-a1b", "minicpm5-2b"]
    elif budget_gb >= 12:
        # 16 GB class: fast MoE for daily driving, 9B available as the quality model
        order = ["lfm2.5-8b-a1b", "qwen3.5-9b", "qwen3.5-4b", "minicpm5-2b"]
    elif budget_gb >= 6:
        order = ["lfm2.5-8b-a1b", "qwen3.5-4b", "minicpm5-2b"]
    elif budget_gb >= 3:
        order = ["qwen3.5-4b", "minicpm5-2b", "qwen-coder-1.5b"]
    else:
        order = ["minicpm5-2b", "qwen-coder-1.5b", "qwen-coder-0.5b"]
    core = next((BY_KEY[k] for k in order if BY_KEY[k].ram_gb <= core_budget), BY_KEY["minicpm5-2b"])
    pick["code"] = core
    pick["chat"] = core

    # A separate high-quality model when there is room, so the router can escalate hard tasks.
    if budget_gb >= 12 and core.key not in ("qwen3.5-9b", "qwen3.6-35b-a3b"):
        for k in ("qwen3.6-35b-a3b", "qwen3.5-9b"):
            if BY_KEY[k].ram_gb <= budget_gb and (k != "qwen3.6-35b-a3b" or budget_gb >= 22 or has_gpu):
                pick["quality"] = BY_KEY[k]
                break

    if want_fim:
        pick["fim"] = BY_KEY["qwen-coder-1.5b"] if budget_gb >= 3 else BY_KEY["qwen-coder-0.5b"]

    if want_security:
        secp = sorted([m for m in CATALOG if "security" in m.roles and m.official_permissive and fits(m)],
                      key=lambda m: m.ram_gb, reverse=True)
        anysec = sorted([m for m in CATALOG if "security" in m.roles and fits(m)],
                        key=lambda m: m.ram_gb, reverse=True)
        pick["security"] = secp[0] if secp else (anysec[0] if anysec else None)

    return {r: m for r, m in pick.items() if m}
