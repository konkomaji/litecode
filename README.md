# litecode

**Local AI for coding and security, on any computer.** litecode is a free, open-source AI coding agent that runs on your own machine with open-weight models. It fixes bugs, adds features, runs your tests, and reviews code for security problems. It also writes, explains, and works with data. It works fully offline.

It adapts to the hardware: a 4 GB laptop with no GPU gets small, fast models; a 16 GB PC gets 8B-class models; a workstation with an NVIDIA GPU gets 30B-class models on the GPU. We test on a 2019 budget PC (Ryzen 3 3200G, 16 GB, no GPU) on purpose, so every machine above it runs litecode better.

Website and docs: [konkomaji.github.io/litecode](https://konkomaji.github.io/litecode/) · Built by Konko Maji.

## Why litecode

Most AI coding tools assume a fast internet connection, a paid API, or an expensive GPU. Many students, hobbyists, and developers do not have those. They have an old laptop or a budget desktop, and they still want to learn, build projects, and analyze code.

litecode is made for exactly that situation:

- Works offline. Once models are downloaded, you never need the internet again.
- Runs on weak hardware. It is tuned for CPU only machines with 4GB to 16GB of RAM.
- Costs nothing to run. Open-weight models, no subscription, no token bills.
- Private by default. Your code and prompts stay on your disk.
- Adapts to the machine. It measures your RAM, CPU, disk, and GPU, then chooses a model set that will actually run well.

## Use cases

- Coding help on an old or low-end PC: write functions, fix bugs, explain code, build small projects.
- Fill-in-the-middle autocomplete with a tiny fast model that stays resident.
- Security code review for authorized work: find common vulnerability classes, explain them, and suggest fixes.
- Learning and tutoring offline: ask questions, get explanations, study without data charges.
- Working in low-connectivity regions where cloud tools are slow or unreachable.
- Private work where code cannot be sent to a third-party service.

## How it works

1. Detect. litecode reads your CPU, cores, RAM, disk type and free space, and any GPU.
2. Recommend. It picks a model set that fits your RAM budget. Small machines get small, fast, on-device-tested models. Bigger machines unlock larger quality models.
3. Ask. It shows the plan and the download size, and asks your permission before downloading anything.
4. Download and configure. You choose, it downloads the models and the local engine, then writes your config.
5. Run. Type a task in any folder. litecode routes it to the right model, uses tools to read and edit files and run commands, and keeps your approval in the loop for anything that changes files.

litecode uses llama.cpp as the local inference engine. The value it adds is the layer around the engine: hardware detection, model selection, a task router, project memory, and sensible defaults for weak machines.

## Install

Requires Python 3.10 or newer. No other dependencies.

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

The installer runs `litecode setup`. The wizard detects your machine, asks where to keep data and models, downloads the llama.cpp engine and the models that fit (after asking), and writes your config. Then run `litecode tune` once to tune speed for your PC.

## Quickstart

```
litecode doctor           # hardware, engine, models
litecode init             # create a LITECODE.md brief for the current project
litecode "add a CLI flag --json to main.py and update the tests"
litecode                  # interactive session in the current folder
litecode review src/      # static scan + model verdict for each finding
```

Inside a session: `/help` lists commands. `@file` attaches a file. `/plan`, `/test`, `/review`, `/commit`, `/undo`, `/memory`, `/skills`, `/mcp`, `/cost`.

## Features

- Agent with tools: read, glob, grep, edit (exact replace with diff preview), write, run, git status/diff, static scan, remember. Permission modes: ask, auto, read-only.
- Automatic memory: every session is saved to disk. Preferences ("always use type hints") apply to all projects. Project facts and passing test commands are saved. Past tasks are reused as examples, rated with `/good` and `/bad`.
- Learning loop: `litecode learn export` writes a fine-tune dataset. A LoRA adapter trained elsewhere loads with one config line.
- Skills like Claude Code: `SKILL.md` files with steps, project/user/built-in scopes, run with `/name`, auto-match by trigger words, build with `/skill new` or let the model draft one with `/skill make`.
- MCP client: stdio MCP servers, same `.mcp.json` format as Claude Code.
- Security: built-in rules plus Semgrep/Bandit when installed. `/review` gives a forced 4-line verdict per finding (grammar-constrained, so small models stay on format).
- Speed for weak PCs: one server slot, quantized KV cache, prompt cache saved per project, n-gram speculative decoding, `litecode tune` picks threads and decoding mode by measurement.
- Clear answers: the system prompt uses ASD-STE100 Simplified Technical English rules. Answer first, short sentences, exact values, no filler. Edit `SYSTEM.md` to change it.
- Editor autocomplete: `litecode fim` plus a dependency-free VS Code extension in `editors/vscode`.
- You choose where data lives: cache, KV slots, scratchpad, memory and skills go to the folder you pick in setup.

Docs: [GUIDE](docs/GUIDE.md), [COMMANDS](docs/COMMANDS.md), [MEMORY](docs/MEMORY.md), [SKILLS](docs/SKILLS.md), [MCP](docs/MCP.md), [EDITORS](docs/EDITORS.md), [TROUBLESHOOTING](docs/TROUBLESHOOTING.md).

## Models

litecode ships a curated catalog and selects from it based on your hardware. The picks below were tested on the reference low-end machine (4 core CPU, 16GB RAM, no usable GPU, hard drive storage).

| Role | Default model | Size | On-device result |
|------|---------------|------|------------------|
| code and chat | MiniCPM5-2B | 1.6 GB | 8/8 coding tasks, 10/10 vulnerability classes identified, about 14 tokens/sec |
| autocomplete | Qwen2.5-Coder-1.5B | 1.1 GB | about 20 tokens/sec, stays resident |
| security (authorized) | Foundation-Sec-8B or WhiteRabbitNeo-V3-7B | about 4.9 GB | WhiteRabbitNeo: 10/10 vulnerability classes, about 5 tokens/sec, loaded on demand |
| general chat | Llama-3.2-3B | 2.0 GB | 10/10 vulnerability classes, broad knowledge |
| quality tier | Qwen3.5-9B | 5.7 GB | not measured yet |

On a 32GB machine or one with a capable GPU, litecode can select a larger mixture-of-experts model such as Qwen3.6-35B-A3B for stronger coding and reasoning.

## Hardware guide

- 4GB RAM: a small 2B class model for coding and chat, plus a tiny autocomplete model.
- 8GB RAM: a fast mixture-of-experts model for daily use.
- 16GB RAM: a fast model for daily use and a 9B quality model for hard tasks.
- 32GB RAM or a capable GPU: a 30B class mixture-of-experts model.

## Security work

litecode can install an official, security-permissive model for authorized penetration testing, capture-the-flag practice, and defensive work such as code review and detection rules. Use it only on systems you own or are authorized to test.

## Status

Early and active development. Benchmarks are from on-device testing on a single reference machine and will vary on other hardware. Model recommendations and defaults will keep improving as more machines report results.

## Contact

Built by Konko Maji.

- Email: [work.konkomaji@gmail.com](mailto:work.konkomaji@gmail.com)
- GitHub: [github.com/konkomaji/litecode](https://github.com/konkomaji/litecode)
- LinkedIn: [linkedin.com/in/konkomaji](https://www.linkedin.com/in/konkomaji/)
- X: [@konkomaji](https://x.com/konkomaji)
- Website: [konkomaji.github.io/litecode](https://konkomaji.github.io/litecode/)

## License

MIT. See [LICENSE](LICENSE). Built by Konko Maji.
