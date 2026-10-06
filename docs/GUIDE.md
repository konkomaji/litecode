# litecode guide

litecode is a local AI coding and security assistant. It runs open-weight models on your own PC. It works offline after setup. Built by Konko Maji.

Contents:
1. Requirements
2. Install
3. Setup
4. First run
5. The interface
6. Daily use
7. Memory and learning
8. Skills
9. MCP servers
10. Security work
11. Speed tuning
12. Files and folders
13. Customize the system prompt
14. Uninstall

Other pages: [Quickstart](QUICKSTART.md), [Commands](COMMANDS.md), [Hardware and models](HARDWARE.md), [Memory and learning](MEMORY.md), [Skills](SKILLS.md), [MCP servers](MCP.md), [Security review](SECURITY.md), [Editor autocomplete](EDITORS.md), [FAQ](FAQ.md), [Troubleshooting](TROUBLESHOOTING.md).

---

## 1. Requirements

| Item | Minimum | Better |
|---|---|---|
| RAM | 4 GB | 16 GB |
| CPU | any x86-64 or ARM64 | 4+ cores with AVX2 |
| Disk | 3 GB free | 15 GB free on an SSD |
| Python | 3.10 | 3.12 |
| GPU | not needed | Vulkan or CUDA GPU (optional) |

litecode has no Python dependencies. It uses only the standard library.

## 2. Install

Windows (PowerShell):

```
git clone https://github.com/konkomaji/litecode
cd litecode
.\install.ps1
```

Linux or macOS:

```
git clone https://github.com/konkomaji/litecode
cd litecode
./install.sh
```

Manual install: `pip install -e .` in the repo folder.

If the `litecode` command is not found after install, add the Python scripts folder to PATH, or run `python -m litecode.cli`.

## 3. Setup

Run:

```
litecode setup
```

The wizard does these steps:

1. It detects CPU, RAM, disks (SSD or HDD) and GPU.
2. It asks where to keep data. Data = cache, KV slots, scratchpad, memory, skills. Press Enter to use the default (`~/.litecode`).
3. It asks where to keep models. Models need several GB. Pick the disk with the most free space.
4. It asks if project memory goes in each project (`.litecode/` folder) or in the data folder.
5. It downloads the llama.cpp engine (30-80 MB) if no engine is found.
6. It recommends models that fit your RAM. It shows the download size and asks before it downloads.
7. It writes `~/.litecode/config.toml`.

Then run the tuner once (about 5 minutes):

```
litecode tune
```

The tuner measures thread counts and speculative decoding on your PC. It saves the fastest settings.

To change a location later: run `litecode setup` again, or `litecode config data_dir D:/litecode-data`.

## 4. First run

```
cd my-project
litecode init        # optional: creates LITECODE.md, a brief about the project
litecode
```

The first model load takes 10-60 seconds on a hard drive. Later tasks reuse the loaded model.

One task without the interactive screen:

```
litecode "add a --json flag to main.py and update the tests"
```

## 5. The interface

```
+----------------------------------------------------------+
| litecode 0.2.0  -  local AI coding assistant             |
| Built by Konko Maji                                      |
+----------------------------------------------------------+
  project  C:\code\my-project
  models   code, fim, chat, security, quality
  mode     ask   data D:/llm/data

litecode> fix the failing test in @tests/test_api.py
  . read the test first
  > read_file {"path": "tests/test_api.py"}
  < 1	import pytest
  > edit_file {"path": "api.py", "find": "...", "replace": "..."}
  allow edit_file?
  - return a - b
  + return a + b
  [y]es / [n]o / [a]lways this session: y
  > run {"cmd": "python -m pytest -q"}
  < (exit 0)

The test failed because add() subtracted. I changed line 2 of api.py. All tests pass.
[code | ask | spec:ngram-simple | 412 tok | 38s]
```

Line types:

| Mark | Meaning |
|---|---|
| `.` | model's short reasoning |
| `>` | tool call |
| `<` | first line of the tool result |
| red `-` / green `+` | lines removed / added by an edit |
| last line | role, permission mode, speculative mode, tokens, seconds |

The final answer streams live while the model writes it.

Type `@path/to/file` in a message to attach that file. Press Ctrl+C to stop a task.

## 6. Daily use

| Goal | Type |
|---|---|
| Ask or change code | plain text |
| Plan first, no edits | `/plan add caching to the API` |
| Run tests and fix | `/test` or `/test npm test` |
| Security review | `/review src/` |
| Fast static scan only | `/scan` |
| Commit message | `/commit` |
| Undo an edit | `/undo path/file.py` (repeat to step back further) |
| See token use | `/cost` |
| Rate the last answer | `/good` or `/bad` |

Permission modes (`/mode`):

| Mode | Behavior |
|---|---|
| `ask` | litecode asks before each edit or command (default) |
| `auto` | no questions; same as `--yes` |
| `readonly` | edits and commands are refused |

All commands: [Commands](COMMANDS.md).

## 7. Memory and learning

litecode records every session to disk automatically. It learns without retraining the model:

1. Preferences: if you write "always use type hints" or "don't add comments", litecode saves it. It applies to all projects.
2. Facts: when a session ends, the model writes short project facts (commands, conventions). A test command that passes is saved at once.
3. Examples: each finished task is stored. A similar task later gets the best past answer as an example. `/good` and `/bad` rate answers. Bad answers are never reused.

You can see and edit all of it: `/memory`, `/forget`, and the files listed in [Memory and learning](MEMORY.md).

Real fine-tuning: `litecode learn export data.jsonl` writes your rated history as a training set. Train a LoRA on a GPU machine. Set `lora` in config. Details in [Memory and learning](MEMORY.md).

## 8. Skills

A skill is a saved instruction pack, like a Claude Code skill. Built-in skills: `review`, `test-fix`, `explain`, `commit`, `refactor`, `skill-builder`.

- Run one: `/review src/`, `/explain @utils.py`.
- Make one step by step: `/skill new my-skill`.
- Let the model draft one: `/skill make a skill that checks Django migrations`.
- List: `/skills`.

Details: [Skills](SKILLS.md).

## 9. MCP servers

litecode connects to Model Context Protocol servers over stdio. It reads the same `.mcp.json` format as Claude Code.

```
litecode mcp add fs npx -y @modelcontextprotocol/server-filesystem .
litecode mcp            # list servers
```

Inside a session, `/mcp` lists the tools. Details: [MCP servers](MCP.md).

Warning: small models handle few tools well. Add only the servers you need.

## 10. Security work

- `/scan` runs static rules with no model. If Semgrep or Bandit is installed, litecode uses them too.
- `/review` scans, then the model gives a verdict for each finding: real or false positive, severity, reason, fix.
- Reports are saved in `.litecode/reviews/`.
- The setup can install an official security model (Foundation-Sec-8B or WhiteRabbitNeo). Security tasks route to it.

Use security features only on code and systems you own or have permission to test.

## 11. Speed tuning

| Setting | Effect |
|---|---|
| `litecode tune` | picks threads and speculative mode by measurement |
| `kv_persist = true` | saves the prompt cache per project; next start skips reprocessing |
| `speculative = "auto"` | n-gram drafting for code roles; it speeds up edits that repeat text |
| `ctx = 8192` | smaller context = less RAM, faster |
| `gpu_layers = 99` | with a Vulkan or CUDA engine build, moves layers to the GPU |
| models on SSD | load time drops from about 30 s to about 5 s |

Generation speed depends mostly on RAM bandwidth. Two RAM sticks (dual channel) are about 2x faster than one.

## 12. Files and folders

| Path | Content |
|---|---|
| `~/.litecode/config.toml` | settings |
| `<data_dir>/profile.jsonl` | your preferences (all projects) |
| `<data_dir>/learn/examples.jsonl` | finished tasks with ratings |
| `<data_dir>/slots/` | saved prompt caches |
| `<data_dir>/scratch/` | scratchpad files |
| `<data_dir>/skills/` | your user skills |
| `<data_dir>/mcp.json` | your MCP servers |
| `<data_dir>/bench/` | tune reports |
| `<project>/LITECODE.md` | project brief (you edit it) |
| `<project>/.litecode/` | project facts, sessions, summaries, checkpoints, reviews, project skills |

## 13. Customize the system prompt

litecode ships `litecode/SYSTEM.md`. It holds the tool protocol and the answer style rules (ASD-STE100 Simplified Technical English: answer first, short sentences, exact values, no filler).

To change it, copy it to `<data_dir>/SYSTEM.md` and edit the copy. Keep the `{spec}` line: litecode puts the tool list there.

## 14. Uninstall

1. `pip uninstall litecode`
2. Delete `~/.litecode` and your data and models folders.
3. Delete `.litecode/` folders in your projects.
