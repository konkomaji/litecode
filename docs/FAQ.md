# FAQ

## What is litecode?

litecode is a free, open-source AI coding and security assistant that runs on your own computer. It works in the terminal like a cloud coding agent, but it uses open-weight models through llama.cpp. After setup it works fully offline.

## Can I run an AI coding assistant without a GPU?

Yes. litecode runs on CPU only. On a 2019 Ryzen 3 3200G with 16 GB RAM, the default 2B model writes about 15 tokens per second and passed 8 of 8 coding tasks in our tests.

## How much RAM do I need?

4 GB is the minimum. 8 GB is comfortable for daily coding. 16 GB runs 8B-class models. 32 GB or a GPU runs 30B-class models. See [Hardware and models](HARDWARE.md).

## Does litecode work on high-end machines too?

Yes. litecode scales up. With an NVIDIA GPU it installs the CUDA engine and moves the model to the GPU. With 32 GB or more it loads bigger models. Low-end support is the floor, not the limit.

## Is it really offline and private?

Yes. After setup, litecode makes no network calls. Your code, prompts, and memory stay on your disk as plain files. MCP servers that you add yourself can use the network.

## Which models does it use?

It picks from a tested catalog: MiniCPM5-2B, Qwen2.5-Coder, Qwen3.5, LFM2.5-8B-A1B, Llama 3.2, Gemma 4, Foundation-Sec-8B, WhiteRabbitNeo, Ministral, and bigger models for GPUs. Any GGUF model works.

## How is litecode different from Ollama or LM Studio?

Ollama and LM Studio run models. litecode is a coding agent: it reads and edits your files, runs your tests, reviews security, remembers your project, and tunes itself to your hardware. It uses llama.cpp directly with low-RAM settings.

## Does it learn from me?

Yes, without retraining. It saves your preferences, project facts, and rated past answers, and reuses them. You can also export a dataset and train a LoRA adapter on a GPU machine. See [Memory and learning](MEMORY.md).

## Can it do more than coding?

Yes. Coding and security are the main focus. It also writes emails, summaries, and documentation, answers study questions, and handles CSV, JSON, and log data. See [Use cases](USE-CASES.md).

## Does it support MCP and skills like Claude Code?

Yes. It reads the same `.mcp.json` format and supports `SKILL.md` skills with project, user, and built-in scopes. See [MCP servers](MCP.md) and [Skills](SKILLS.md).

## Why are the answers so short?

litecode follows ASD-STE100 Simplified Technical English: answer first, short sentences, exact values, no filler. Short answers cost fewer tokens, so they arrive faster on slow machines. You can change the rules in `SYSTEM.md`.

## Is it free?

Yes. litecode is MIT licensed. Models are open-weight; check each model's license before you redistribute it.

## Who built it?

Konko Maji. Contact: [work.konkomaji@gmail.com](mailto:work.konkomaji@gmail.com), [LinkedIn](https://www.linkedin.com/in/konkomaji/), [X](https://x.com/konkomaji).
