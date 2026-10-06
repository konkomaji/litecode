"""MCP client: connect litecode to Model Context Protocol servers over stdio.

Config file format is the same as Claude Code's .mcp.json:

    {"mcpServers": {
        "fs": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]},
        "notes": {"command": "python", "args": ["notes_server.py"], "env": {"KEY": "v"}}
    }}

Files read (project wins on name clash):
  <data_dir>/mcp.json         user servers
  <project>/.mcp.json         project servers (shared with Claude Code)
  <project>/.litecode/mcp.json

Tools appear to the model as mcp__<server>__<tool>. Servers start lazily on the
first session that needs them and stop when litecode exits. Small models get
confused by long tool lists, so only enabled servers load.
"""
from __future__ import annotations
import atexit, json, os, queue, shutil, subprocess, threading
from pathlib import Path

PROTOCOL = "2025-06-18"


def config_files(project: Path, data_dir: Path) -> list[Path]:
    return [Path(data_dir) / "mcp.json", Path(project) / ".mcp.json", Path(project) / ".litecode" / "mcp.json"]


def load_config(project: Path, data_dir: Path) -> dict:
    servers = {}
    for p in config_files(project, data_dir):
        if p.exists():
            try:
                servers.update(json.loads(p.read_text(encoding="utf-8")).get("mcpServers", {}))
            except Exception as e:
                print(f"litecode: bad MCP config {p}: {e}")
    return {k: v for k, v in servers.items() if not v.get("disabled")}


def save_server(path: Path, name: str, spec: dict | None):
    """Add (spec) or remove (None) a server in one config file."""
    data = {"mcpServers": {}}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
        data.setdefault("mcpServers", {})
    if spec is None:
        data["mcpServers"].pop(name, None)
    else:
        data["mcpServers"][name] = spec
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class MCPError(RuntimeError):
    pass


class Client:
    def __init__(self, name: str, spec: dict, timeout: float = 60):
        self.name = name
        self.spec = spec
        self.timeout = timeout
        self.proc = None
        self._id = 0
        self._pending: dict[int, queue.Queue] = {}
        self._lock = threading.Lock()
        self.tools: list[dict] = []

    def start(self):
        cmd = self.spec["command"]
        exe = shutil.which(cmd) or cmd
        env = {**os.environ, **{k: str(v) for k, v in self.spec.get("env", {}).items()}}
        self.proc = subprocess.Popen([exe, *self.spec.get("args", [])], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     env=env, cwd=self.spec.get("cwd"))
        threading.Thread(target=self._reader, daemon=True).start()
        self.request("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                    "clientInfo": {"name": "litecode", "version": "0.2"}})
        self.notify("notifications/initialized")
        self.tools = self.request("tools/list", {}).get("tools", [])

    def _reader(self):
        for raw in self.proc.stdout:
            try:
                msg = json.loads(raw.decode("utf-8", "replace"))
            except Exception:
                continue
            q = self._pending.get(msg.get("id")) if "id" in msg else None
            if q is not None and ("result" in msg or "error" in msg):
                q.put(msg)
        for q in list(self._pending.values()):
            q.put({"error": {"message": "server exited"}})

    def _send(self, obj: dict):
        if not self.proc or self.proc.poll() is not None:
            raise MCPError(f"MCP server '{self.name}' is not running")
        self.proc.stdin.write((json.dumps(obj) + "\n").encode())
        self.proc.stdin.flush()

    def notify(self, method: str, params: dict | None = None):
        self._send({"jsonrpc": "2.0", "method": method, **({"params": params} if params else {})})

    def request(self, method: str, params: dict) -> dict:
        with self._lock:
            self._id += 1
            rid = self._id
        q: queue.Queue = queue.Queue()
        self._pending[rid] = q
        try:
            self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
            try:
                msg = q.get(timeout=self.timeout)
            except queue.Empty:
                raise MCPError(f"MCP '{self.name}' timed out on {method}")
        finally:
            self._pending.pop(rid, None)
        if "error" in msg:
            raise MCPError(f"MCP '{self.name}' {method}: {msg['error'].get('message')}")
        return msg.get("result", {})

    def call(self, tool: str, args: dict) -> str:
        res = self.request("tools/call", {"name": tool, "arguments": args})
        parts = []
        for c in res.get("content", []):
            if c.get("type") == "text":
                parts.append(c.get("text", ""))
            else:
                parts.append(f"({c.get('type')} content)")
        out = "\n".join(parts) or json.dumps(res.get("structuredContent", {}))[:4000]
        return ("(tool reported error) " if res.get("isError") else "") + out[:8000]

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.close()
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()


class Hub:
    def __init__(self, project: Path, data_dir: Path, on_error=print):
        self.config = load_config(project, data_dir)
        self.clients: dict[str, Client] = {}
        self.on_error = on_error
        self.started = False
        atexit.register(self.stop)

    def start(self):
        if self.started:
            return
        self.started = True
        for name, spec in self.config.items():
            c = Client(name, spec)
            try:
                c.start()
                self.clients[name] = c
            except Exception as e:
                c.stop()
                self.on_error(f"litecode: MCP server '{name}' failed: {e}")

    def tool_names(self) -> list[str]:
        return [f"mcp__{n}__{t['name']}" for n, c in self.clients.items() for t in c.tools]

    def has(self, full: str) -> bool:
        return full in self.tool_names()

    def call(self, full: str, args: dict) -> str:
        _, server, tool = full.split("__", 2)
        return self.clients[server].call(tool, args)

    def spec_text(self, max_tools: int = 20) -> str:
        """Compact tool list for the system prompt: name, one line, arg names."""
        lines = []
        for n, c in self.clients.items():
            for t in c.tools:
                props = list((t.get("inputSchema") or {}).get("properties", {}).keys())
                req = set((t.get("inputSchema") or {}).get("required", []))
                args = ", ".join(a + ("" if a in req else "?") for a in props)
                desc = (t.get("description") or "").strip().split("\n")[0][:100]
                lines.append(f'- mcp__{n}__{t["name"]}  args: {{{args}}}  {desc}')
        if not lines:
            return ""
        more = f"\n...({len(lines) - max_tools} more)" if len(lines) > max_tools else ""
        return "MCP tools (same JSON format, args as listed, ? = optional):\n" + "\n".join(lines[:max_tools]) + more

    def stop(self):
        for c in self.clients.values():
            c.stop()
        self.clients = {}
