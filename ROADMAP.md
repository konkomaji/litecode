# litecode roadmap

Goal: a local, offline coding agent with the features people expect from a modern
command-line coding assistant, running on open-weight models and tuned to the machine.

## Done (v0.1)

- Hardware detection: CPU, cores, SIMD, RAM, disks (SSD or HDD) with free space, GPU, Vulkan.
- Adaptive model selection that scales from a 4GB laptop to a 32GB or GPU machine.
- Setup wizard, resident local model server with low-RAM defaults.
- Agent loop with a strict one-action protocol that small models can follow.
- Task router, project brief, launch from anywhere.

## Done (v0.2)

- Interface: welcome box, bordered prompt with history, Tab completion and Shift+Tab modes, spinner, one line per tool call, arrow-key permission menu with "no, do this instead", live markdown answer.
- Tools: glob, line-range reads, exact-replace edits, git status/diff, static scan, remember.
- Permission modes: ask, auto, read-only. Plan mode. Undo with stacked checkpoints.
- Slash commands: /plan /review /scan /test /diff /commit /model /mode /remember /prefer /memory /forget /good /bad /undo /sessions /resume /clear /init /skills /skill /mcp /config /cost.
- Context: @file mentions, history compaction with full archive, alternating-role message building.
- Memory and learning: automatic session capture, global preference profile, project facts (model extraction at session end, test commands at once), example retrieval with ratings, fine-tune dataset export, LoRA adapter loading.
- Skills: SKILL.md format, built-in/user/project scopes, trigger matching, step-by-step builder, model-drafted skills.
- MCP: stdio client, Claude Code compatible config, tools exposed as mcp__server__tool.
- Static analysis first: built-in rules, Semgrep/Bandit when installed, grammar-constrained verdicts.
- Test-fix loop.
- Performance: one slot, KV cache save/restore per project, n-gram speculative decoding with automatic fallback, `litecode tune` (threads + speculative mode by measurement, shareable report).
- Setup: user-selected data and model folders, automatic llama.cpp engine download, portable defaults.
- Editor: FIM server and a VS Code extension.
- ASD-STE100 answer rules in an editable SYSTEM.md.
- Docs and a stdlib unittest suite.

## Done (v0.3)

- Direct chat path: greetings and general questions skip the tool agent and use a short prompt. On the reference PC a reply starts in seconds instead of 60-90 s.
- Grammar-locked agent steps: a JSON schema per tool turns into a llama.cpp grammar, so small models cannot write broken JSON, unknown tools or missing arguments. Falls back to lenient parsing on old engines.
- Loop guard: a repeated identical step stops the task with the last result. Broken tool JSON is never shown as an answer.
- Claude Code style interface: welcome box, bordered prompt with history, Tab completion, Shift+Tab modes (ask, auto-accept, plan), spinner with time and tokens, one line per tool call, arrow-key permission menu with "no, do this instead", live markdown answer, `!command` and `#memory` prefixes, `/status`.
- One-line installers for Windows, Linux and macOS with a private Python environment, PATH setup, first-run setup, and `litecode update`.

## Next

- MCP over HTTP/SSE, MCP resources and prompts.
- tree-sitter symbol and call-graph retrieval.
- Multi-file diff edits with one review step.
- Draft-model speculative decoding and GPU prompt processing chosen by `tune`.

Built by Konko Maji.
