"""Minimal MCP stdio server for tests: one tool 'add' that sums two numbers."""
import json, sys

for line in sys.stdin:
    try:
        msg = json.loads(line)
    except Exception:
        continue
    if "id" not in msg:
        continue
    m = msg.get("method")
    if m == "initialize":
        res = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
               "serverInfo": {"name": "fake", "version": "1"}}
    elif m == "tools/list":
        res = {"tools": [{"name": "add", "description": "Add two numbers",
                          "inputSchema": {"type": "object", "properties": {"a": {"type": "number"},
                                          "b": {"type": "number"}}, "required": ["a", "b"]}}]}
    elif m == "tools/call":
        a = msg["params"]["arguments"]
        res = {"content": [{"type": "text", "text": str(a["a"] + a["b"])}]}
    else:
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"],
                                     "error": {"code": -32601, "message": "no method"}}) + "\n")
        sys.stdout.flush()
        continue
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": res}) + "\n")
    sys.stdout.flush()
