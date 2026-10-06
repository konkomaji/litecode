# MCP servers

litecode is an MCP client. It starts MCP servers over stdio and gives their tools to the model. It reads the same `mcpServers` format as Claude Code.

## Add a server

Command line:

```
litecode mcp add fs npx -y @modelcontextprotocol/server-filesystem .
litecode mcp add git uvx mcp-server-git
litecode mcp                 # list servers
litecode mcp --tools         # start them and list their tools
litecode mcp rm fs
```

Or edit a config file:

```json
{
  "mcpServers": {
    "fs": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]},
    "notes": {"command": "python", "args": ["notes_server.py"], "env": {"NOTES_DIR": "D:/notes"}},
    "off": {"command": "x", "disabled": true}
  }
}
```

Config files (later wins on a name clash):

1. `<data_dir>/mcp.json` (user, written by `litecode mcp add`)
2. `<project>/.mcp.json` (project, same file Claude Code uses)
3. `<project>/.litecode/mcp.json`

## How the model calls a tool

Tools appear as `mcp__<server>__<tool>`. The model uses the normal JSON format:

```
{"tool": "mcp__fs__read_file", "args": {"path": "README.md"}}
```

Each MCP call asks for approval in `ask` mode. In `readonly` mode MCP calls are refused.

## Limits

- Transport: stdio only. HTTP/SSE servers are not supported yet.
- Tools only. MCP resources and prompts are not used yet.
- litecode shows the model at most 20 MCP tools. Small models choose badly from long lists. Add only what you need.
- A server that fails to start is skipped. litecode prints the error and continues.
- Most MCP servers need Node.js (`npx`) or `uv` (`uvx`). Install those first. Offline use needs the server installed locally.
