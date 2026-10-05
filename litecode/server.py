"""Manage a resident llama-server: start on demand, reuse, hot-swap model by role."""
from __future__ import annotations
import atexit, json, subprocess, time, urllib.request, urllib.error
from pathlib import Path
from . import config


class Server:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.proc: subprocess.Popen | None = None
        self.role: str | None = None
        atexit.register(self.stop)

    @property
    def base(self) -> str:
        return f"http://{self.cfg['host']}:{self.cfg['port']}"

    def _healthy(self) -> bool:
        try:
            with urllib.request.urlopen(self.base + "/health", timeout=2) as r:
                return b"ok" in r.read().lower()
        except Exception:
            return False

    def ensure(self, role: str):
        """Make sure the server is up and serving `role`'s model."""
        path = config.model_path(self.cfg, role)
        if path is None:
            raise FileNotFoundError(f"no model for role '{role}' (check models_dir / downloads)")
        if self.proc and self.role == role and self._healthy():
            return
        self.stop()
        cmd = [
            self.cfg["engine"], "-m", str(path),
            "-t", str(self.cfg["threads"]), "-c", str(self.cfg["ctx"]),
            "--host", self.cfg["host"], "--port", str(self.cfg["port"]),
            "-ctk", self.cfg["kv_type"], "-ctv", self.cfg["kv_type"], "-fa", "on",
            "--cache-ram", str(self.cfg["cache_ram_mb"]),
        ]
        print(f"litecode: loading {path.name} (role={role}) ...", flush=True)
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.role = role
        for _ in range(120):
            if self._healthy():
                print("litecode: model ready.", flush=True)
                return
            if self.proc.poll() is not None:
                raise RuntimeError("llama-server exited during startup")
            time.sleep(1)
        raise TimeoutError("llama-server did not become healthy in 120s")

    def chat(self, messages: list[dict], temperature=None, max_tokens=1024,
             grammar: str | None = None, stop: list[str] | None = None,
             thinking=False) -> str:
        body = {
            "messages": messages,
            "temperature": self.cfg["temperature"] if temperature is None else temperature,
            "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": thinking},
        }
        if grammar:
            body["grammar"] = grammar
        if stop:
            body["stop"] = stop
        data = json.dumps(body).encode()
        req = urllib.request.Request(self.base + "/v1/chat/completions", data,
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=900) as r:
            return json.load(r)["choices"][0]["message"]["content"]

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()
        self.proc = None
        self.role = None
