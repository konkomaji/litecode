# litecode

Run open-weight LLMs on any machine, from a 4GB laptop to a GPU workstation. litecode auto-detects your hardware, picks models that fit, and works fully offline from your terminal.

It is a local coding and security assistant that behaves like a command-line coding agent, but it runs entirely on your own computer with open-weight models. No cloud, no API keys, no data leaving your machine.

Built low-end first. The design target is a cheap PC with a slow CPU, little RAM, and a hard drive. On a stronger machine litecode simply scales up and loads larger, more capable models.

Built by Konko Maji.

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

Requires Python 3.11 or newer.

```
git clone https://github.com/konkomaji/litecode
cd litecode
pip install -e .
```

Then run the setup wizard:

```
litecode setup
```

The wizard detects your machine, recommends models, asks permission, and downloads everything. To run from any folder, add the `bin` directory to your PATH, or use the installed `litecode` command.

## Quickstart

```
litecode doctor           # show detected hardware and recommended models
litecode setup            # choose and download models
litecode init             # create a LITECODE.md brief for the current project
litecode "add a CLI flag --json to main.py and update the tests"
litecode                  # start an interactive session in the current folder
```

Use `--yes` to auto-approve file writes and commands. Use `--role security` to force the security model.

## Models

litecode ships a curated catalog and selects from it based on your hardware. The picks below were tested on the reference low-end machine (4 core CPU, 16GB RAM, no usable GPU, hard drive storage).

| Role | Default model | Size | On-device result |
|------|---------------|------|------------------|
| code and chat | MiniCPM5-2B | 1.6 GB | 8/8 coding tasks, 10/10 vulnerability classes identified, about 14 tokens/sec |
| autocomplete | Qwen2.5-Coder-1.5B | 1.1 GB | about 20 tokens/sec, stays resident |
| security (authorized) | Foundation-Sec-8B or WhiteRabbitNeo-V3-7B | about 4.9 GB | official security models, loaded on demand |
| general chat | Llama-3.2-3B | 2.0 GB | 10/10 vulnerability classes, broad knowledge |
| quality tier | Qwen3.5-9B | 5.7 GB | highest quality that fits 16GB, slower |

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

## License

MIT. See [LICENSE](LICENSE). Built by Konko Maji.
