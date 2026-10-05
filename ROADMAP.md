# litecode roadmap

Goal: a local, offline coding agent with the features people expect from a modern
command-line coding assistant, running on open-weight models and tuned to the machine.

## Done (v0.1)

- Hardware detection: CPU, cores, SIMD, RAM, disks (SSD or HDD) with free space, GPU, Vulkan.
- Adaptive model selection that scales from a 4GB laptop to a 32GB or GPU machine.
- Setup wizard: detect, recommend, ask permission, download with resume, write config.
- Resident local model server with low-RAM defaults (quantized KV cache, small prompt cache, no idle unload).
- Agent loop with a strict one-action protocol that small models can follow.
- Tools: list_dir, read_file, grep, write_file, run (bash or powershell), sandboxed to the project with approvals.
- Task router: sends security work to the security model, hard tasks to the quality model.
- Project memory: a LITECODE.md brief and a per-project history log.
- Launch from anywhere with the `litecode` command.

## Planned (feature parity with mainstream coding agents)

### Editing and tools
- Precise multi-file edits with unified diffs and a review step before applying.
- Fill-in-the-middle autocomplete server with cursor-aware prompt caching.
- glob and semantic code search, tree-sitter symbol and call-graph retrieval.
- Static analysis first for code and security, so the model explains findings instead of hunting for them.
- Run tests and read results back, with an automatic fix loop.

### Workflow
- Slash commands (/init, /review, /test, /undo, /model, /cost, /clear).
- Plan mode: propose a step list, get approval, then execute.
- Undo and checkpoints for file changes.
- Permission modes: ask, auto-approve, and read-only.

### Context and memory
- Prompt and KV snapshot cache per project, saved to disk, so repeated context is not reprocessed.
- History compaction and summaries to stay inside a small RAM budget.
- @file and @folder mentions to pull context on demand.

### Models and performance
- Speculative decoding chosen automatically by measured acceptance (n-gram, draft model, or model MTP head).
- Optional integrated GPU use for prompt processing where available.
- A local benchmark on install that tunes threads, batch size, and defaults to the machine.
- Per-task model routing with a small classifier when rules are not enough.

### Integration
- Editor integration (VS Code) talking to the same local server.
- Optional MCP tool support for extra capabilities.
- Git awareness: read diffs, stage changes, write commit messages.

### Reach
- Verified model packs per hardware tier, with community-reported benchmarks.
- One-command install for Windows, Linux, and macOS.

Built by Konko Maji.
