# Editor autocomplete

litecode can serve fill-in-the-middle (FIM) autocomplete with the small `fim` model (default Qwen2.5-Coder-1.5B, about 20 tokens/s on a 4-core CPU).

## 1. Start the server

```
litecode fim
```

It listens on `http://127.0.0.1:8081/infill`. Change the port with `litecode config fim_port 8082`.

RAM: the fim model uses about 1.5 GB. It can run next to the main model on a 16 GB PC.

## 2. VS Code

The extension is in `editors/vscode/`. It has no dependencies.

1. Copy the folder `editors/vscode` to `~/.vscode/extensions/litecode-complete` (Windows: `%USERPROFILE%\.vscode\extensions\litecode-complete`).
2. Restart VS Code.
3. Type code. A grey suggestion appears after you stop typing. Press Tab to accept.

Settings (`litecode.*`): `url`, `maxTokens` (48), `debounceMs` (350), `enabled`.

## 3. Other editors

Any editor plugin that supports the llama.cpp `/infill` API works. Example: `llama.vim` and `llama.vscode` by ggml-org. Point it at the URL above.

Test by hand:

```
curl -s http://127.0.0.1:8081/infill -d '{"input_prefix":"def add(a, b):\n    ","input_suffix":"\n","n_predict":16}'
```
