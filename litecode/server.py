"""Manage a resident llama-server: start on demand, reuse, hot-swap model by role.

Low-RAM choices: one slot (-np 1), quantized KV cache, small prompt cache.
Speed choices: optional n-gram speculative decoding (falls back if the model does
not support it), and KV cache save/restore per project so a long system prompt
is not reprocessed on every start. On a slow CPU, prompt processing of ~3k tokens
costs over a minute, so the restore matters.
"""
from __future__ import annotations
import atexit, json, subprocess, time, urllib.request, urllib.error
from pathlib import Path
from . import config

SPEC_TYPES = ("ngram-simple", "ngram-mod", "ngram-cache")


class Stats:
    def __init__(self):
        self.calls = 0
        self.prompt_tokens = 0
        self.gen_tokens = 0
        self.seconds = 0.0

    def add(self, prompt, gen, secs):
        self.calls += 1
        self.prompt_tokens += prompt
        self.gen_tokens += gen
        self.seconds += secs

    def line(self) -> str:
        tps = self.gen_tokens / self.seconds if self.seconds else 0
        return (f"{self.calls} calls, {self.prompt_tokens} prompt + {self.gen_tokens} generated tokens, "
                f"{self.seconds:.0f}s model time, {tps:.1f} tok/s overall. Cost: 0 (local).")


class Server:
    def __init__(self, cfg: dict, port: int | None = None, quiet=False):
        self.cfg = cfg
        self.port = port or cfg["port"]
        self.proc: subprocess.Popen | None = None
        self.role: str | None = None
        self.path: Path | None = None
        self.spec_active: str = "none"
        self.stats = Stats()
        self.quiet = quiet
        self.schema_ok = True           # engine accepts json_schema (grammar-locked tool steps)
        atexit.register(self.stop)

    @property
    def base(self) -> str:
        return f"http://{self.cfg['host']}:{self.port}"

    def _healthy(self) -> bool:
        try:
            with urllib.request.urlopen(self.base + "/health", timeout=2) as r:
                return b"ok" in r.read().lower()
        except Exception:
            return False

    def _log(self, msg):
        if not self.quiet:
            print(f"litecode: {msg}", flush=True)

    def _spec_choice(self, role: str) -> str:
        s = str(self.cfg.get("speculative", "auto"))
        if s in ("off", "none", "false"):
            return "none"
        if s == "auto":
            # tuned value per role, written by `litecode tune`; default: n-gram drafts help code edits
            tuned = self.cfg.get("spec_tuned", {}) if isinstance(self.cfg.get("spec_tuned"), dict) else {}
            return tuned.get(role, "ngram-simple" if role in ("code", "quality") else "none")
        return s

    def _cmd(self, path: Path, spec: str) -> list[str]:
        c = self.cfg
        cmd = [
            c["engine"], "-m", str(path),
            "-t", str(c["threads"]), "-c", str(c["ctx"]),
            "--host", c["host"], "--port", str(self.port),
            "-ctk", c["kv_type"], "-ctv", c["kv_type"], "-fa", "on",
            "--cache-ram", str(c["cache_ram_mb"]), "-np", "1",
        ]
        if int(c.get("gpu_layers", 0) or 0) > 0:
            cmd += ["-ngl", str(c["gpu_layers"])]
        else:
            cmd += ["-ngl", "0"]
        if c.get("kv_persist", True):
            slots = config.data_path(c, "slots")
            cmd += ["--slot-save-path", str(slots)]
        lora = c.get("lora", "")
        if lora and Path(lora).exists():
            cmd += ["--lora", str(lora)]
        if spec in SPEC_TYPES:
            cmd += ["--spec-type", spec]
        return cmd

    def _start(self, path: Path, spec: str) -> bool:
        self.proc = subprocess.Popen(self._cmd(path, spec), stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
        for _ in range(240):
            if self._healthy():
                return True
            if self.proc.poll() is not None:
                return False
            time.sleep(0.5)
        raise TimeoutError("llama-server did not become healthy in 120s")

    def ensure(self, role: str):
        """Make sure the server is up and serving `role`'s model."""
        path = config.model_path(self.cfg, role)
        if path is None:
            raise FileNotFoundError(f"no model for role '{role}' (check models_dir / downloads)")
        if not Path(self.cfg["engine"]).exists():
            raise FileNotFoundError(f"engine not found: {self.cfg['engine']} (run `litecode setup`)")
        if self.proc and self._healthy() and (self.role == role or self.path == path):
            self.role = role          # same model file under another role: no reload from disk
            return
        self.stop()
        spec = self._spec_choice(role)
        self._log(f"loading {path.name} (role={role}, speculative={spec}) ...")
        ok = self._start(path, spec)
        if not ok and spec != "none":
            self._log("model rejected speculative decoding, retrying without it")
            spec = "none"
            ok = self._start(path, spec)
        if not ok:
            raise RuntimeError("llama-server exited during startup (run `litecode doctor`)")
        self.role = role
        self.path = path
        self.spec_active = spec
        self._log("model ready.")

    # --- KV cache persistence (one slot, id 0) ---
    def _slot(self, action: str, name: str) -> bool:
        if not self.cfg.get("kv_persist", True) or not self.proc:
            return False
        body = json.dumps({"filename": name}).encode()
        req = urllib.request.Request(f"{self.base}/slots/0?action={action}", body,
                                     {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status == 200
        except Exception:
            return False

    def save_cache(self, name: str) -> bool:
        return self._slot("save", name)

    def restore_cache(self, name: str) -> bool:
        if not (config.data_path(self.cfg, "slots") / name).exists():
            return False
        return self._slot("restore", name)

    # --- generation ---
    def _post(self, route: str, body: dict, timeout=900):
        req = urllib.request.Request(self.base + route, json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        return urllib.request.urlopen(req, timeout=timeout)

    def chat(self, messages: list[dict], temperature=None, max_tokens=1024,
             grammar: str | None = None, stop: list[str] | None = None,
             thinking=False, on_token=None, json_schema: dict | None = None) -> str:
        body = {
            "messages": messages,
            "temperature": self.cfg["temperature"] if temperature is None else temperature,
            "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": thinking},
            "cache_prompt": True,
        }
        if grammar:
            body["grammar"] = grammar
        elif json_schema and self.schema_ok:
            body["json_schema"] = json_schema
        if stop:
            body["stop"] = stop
        try:
            return self._chat(body, on_token)
        except urllib.error.HTTPError as e:
            if "json_schema" not in body or e.code not in (400, 500):
                raise
            # older engine without schema support: fall back to lenient parsing
            self.schema_ok = False
            body.pop("json_schema")
            return self._chat(body, on_token)

    def _chat(self, body: dict, on_token) -> str:
        t0 = time.time()
        if on_token is None:
            with self._post("/v1/chat/completions", body) as r:
                data = json.load(r)
            u = data.get("usage", {})
            self.stats.add(u.get("prompt_tokens", 0), u.get("completion_tokens", 0), time.time() - t0)
            return data["choices"][0]["message"]["content"] or ""
        body["stream"] = True
        body["stream_options"] = {"include_usage": True}
        out, usage = [], {}
        with self._post("/v1/chat/completions", body) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    ev = json.loads(payload)
                except Exception:
                    continue
                if ev.get("usage"):
                    usage = ev["usage"]
                for ch in ev.get("choices", []):
                    tok = (ch.get("delta") or {}).get("content")
                    if tok:
                        out.append(tok)
                        on_token(tok)
        self.stats.add(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), time.time() - t0)
        return "".join(out)

    def infill(self, prefix: str, suffix: str, n_predict=64) -> str:
        body = {"input_prefix": prefix, "input_suffix": suffix, "n_predict": n_predict,
                "temperature": 0, "cache_prompt": True}
        with self._post("/infill", body, timeout=120) as r:
            return json.load(r).get("content", "")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()
        self.proc = None
        self.role = None
        self.path = None
