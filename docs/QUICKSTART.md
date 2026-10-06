# Quickstart

This page takes you from zero to your first task in about 10 minutes, plus model download time.

## 1. Check the requirements

- Python 3.10 or newer: `python --version`
- Git: `git --version`
- Free disk space: 3 GB for a small PC, 15 GB or more for bigger models

You do not need a GPU. If you have one, litecode uses it.

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

The installer starts the setup wizard.

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

Type a task:

```
litecode> explain what @main.py does
litecode> add input validation to the signup function and run the tests
litecode> /review src/
```

litecode asks before it changes a file or runs a command. Type `y` to allow, `a` to allow for the rest of the session.

## 6. Next steps

- Learn the interface and daily commands: [User guide](GUIDE.md)
- See every command: [Commands](COMMANDS.md)
- Pick models for your hardware: [Hardware and models](HARDWARE.md)
- Check how well models do on real tasks: [Benchmarks](BENCHMARKS.md)
