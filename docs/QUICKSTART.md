# Quickstart

This page takes you from zero to your first task in about 10 minutes, plus model download time.

## 1. Check the requirements

- Python 3.10 or newer: `python --version`. On Windows the installer offers to install it.
- Free disk space: 3 GB for a small PC, 15 GB or more for bigger models

You do not need a GPU. If you have one, litecode uses it.

## 2. Install

Windows (PowerShell):

```
irm https://raw.githubusercontent.com/konkomaji/litecode/main/install.ps1 | iex
```

Linux or macOS:

```
curl -fsSL https://raw.githubusercontent.com/konkomaji/litecode/main/install.sh | sh
```

The installer adds the `litecode` and `lite` commands to your PATH and starts the setup wizard. If the command is not found afterwards, open a new terminal.

## 3. Answer the setup wizard

The wizard asks 4 things:

1. Where to keep data (cache, memory, skills). Press Enter for the default.
2. Where to keep models. Pick the disk with the most free space.
3. Whether to download the engine. Answer yes. If you have an NVIDIA GPU, answer yes to the CUDA build.
4. Whether to download the recommended models. It shows the size first.

## 4. Tune for your machine

```
litecode tune
```

This takes about 5 minutes. It finds the fastest thread count and decoding mode for your CPU or GPU.

## 5. Run your first task

```
cd path/to/your/project
litecode
```

Type a question or a task:

```
> what is a list comprehension
> explain what @main.py does
> add input validation to the signup function and run the tests
> /review src/
```

Questions get a direct answer. Tasks run the agent. litecode asks before it changes a file or runs a command: pick `1` (yes), `2` (yes for the rest of the session), or `3` (no, and tell it what to do instead). Shift+Tab switches to auto-accept or plan mode.

## 6. Next steps

- Learn the interface and daily commands: [User guide](GUIDE.md)
- See every command: [Commands](COMMANDS.md)
- Pick models for your hardware: [Hardware and models](HARDWARE.md)
- Check how well models do on real tasks: [Benchmarks](BENCHMARKS.md)
