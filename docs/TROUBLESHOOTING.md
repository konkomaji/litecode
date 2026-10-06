# Troubleshooting

Run `litecode doctor` first. It shows the engine, folders and models.

| Problem | Cause | Fix |
|---|---|---|
| `engine not found` | no llama-server | `litecode setup`, or `litecode config engine PATH` |
| `no model for role 'x'` | model file missing | `litecode setup`, or `litecode config roles.x FILE.gguf` |
| `llama-server exited during startup` | not enough RAM, or bad model file | close programs; use a smaller model; download the file again |
| First answer is slow | model loads from disk, prompt is processed | normal. Next tasks are faster. Keep models on an SSD if possible |
| Output is garbage (`GGGG...`) | broken model file or engine bug for that model | check the file hash against Hugging Face; try another quant or a newer engine |
| `(model broke protocol, retrying)` | small model wrote text, not JSON | normal now and then. If constant, use a bigger model with `/model quality` |
| `litecode` command not found | Python scripts folder not on PATH | use `python -m litecode.cli`, or add the folder to PATH |
| Commands fail on Windows with WSL errors | `bash` resolves to the WSL stub | litecode uses Git Bash or PowerShell. Install Git for Windows for bash |
| PC freezes, disk light on | RAM is full, Windows swaps | use a smaller model, lower `ctx`, close the browser |
| Port in use | another server on 8080 | `litecode config port 8090` |
| MCP server fails | missing `npx`/`uvx`, or bad args | run the server command by hand to see the error |
| Wrong answers repeat | a bad example is reused | `/bad` after a bad answer; `/forget` to clear facts |

Logs: run the engine by hand to see its errors:

```
<engine> -m <models_dir>/<model>.gguf -c 4096
```
