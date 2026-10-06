# Memory and learning

litecode saves every session to disk. It gets better with use in three ways. None of them change the model weights.

## What is saved, and where

| Data | File | Scope |
|---|---|---|
| Every turn of every session | `<project>/.litecode/sessions/<id>.jsonl` | project |
| Full history before compaction | `sessions/<id>.full.jsonl.bak` | project |
| Summary of older turns | `summaries/<id>.md` | project |
| Project facts | `memory.jsonl` | project |
| File snapshots for undo | `checkpoints/` | project |
| Security review reports | `reviews/` | project |
| Your preferences | `<data_dir>/profile.jsonl` | all projects |
| Finished tasks + ratings | `<data_dir>/learn/examples.jsonl` | all projects |

If `project_memory = "central"`, the project files go to `<data_dir>/projects/<name>-<id>/` instead of the project folder.

All files are plain JSON lines or Markdown. You can read, edit or delete them.

## How litecode learns

1. Preferences. A message line that starts with "always", "never", "don't", "prefer", "from now on", "make sure to" or "avoid" becomes a preference. No model call is needed. Preferences go into every prompt, in all projects. Add one by hand: `/prefer use pathlib, not os.path`.
2. Facts. A test command that passes is saved at once. When a session ends (`/exit`), the model reads the session and saves up to 6 durable facts. To turn off the model step: `litecode config auto_learn false`.
3. Examples. Each finished task is saved with the files it changed. For a new task, litecode finds similar past tasks by keyword overlap. It adds the best one to the prompt. Rate answers with `/good` and `/bad`. A bad answer is never reused. A good answer ranks higher.

Context limits: small models have small context windows. litecode keeps the last 8 turns raw. It folds older turns into a summary.

## Fine-tuning (optional, on other hardware)

Constraint: training a 2B+ model on a 4-core CPU takes days. Do it on a GPU machine. A free Google Colab GPU is enough for a LoRA on a 2B-4B model.

1. Rate answers with `/good` while you work.
2. Export: `litecode learn export my_data.jsonl` (add `--all` to include unrated tasks).
3. Train a LoRA on the same base model you use (for example with Unsloth or PEFT). The file is chat format: `{"messages": [...]}` per line.
4. Convert the adapter to GGUF with llama.cpp: `python convert_lora_to_gguf.py --base <base model dir> <adapter dir>`.
5. Copy the `.gguf` adapter to your PC.
6. Set it: `litecode config lora D:/llm/adapters/my-lora.gguf`.
7. Restart litecode. The server loads the adapter.

Warning: an adapter works only with the base model it was trained on.

## Privacy

Nothing leaves your PC. litecode makes no network calls except `litecode setup` downloads, and MCP servers that you add yourself.
