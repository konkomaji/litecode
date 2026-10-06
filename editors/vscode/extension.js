// litecode autocomplete for VS Code. No dependencies. Built by Konko Maji.
// Sends the text before and after the cursor to llama-server's /infill endpoint.
const vscode = require("vscode");
const http = require("http");

function infill(url, body, token) {
  return new Promise((resolve) => {
    const u = new URL(url + "/infill");
    const data = JSON.stringify(body);
    const req = http.request(
      { hostname: u.hostname, port: u.port, path: u.pathname, method: "POST",
        headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(data) } },
      (res) => {
        let buf = "";
        res.on("data", (c) => (buf += c));
        res.on("end", () => { try { resolve(JSON.parse(buf).content || ""); } catch { resolve(""); } });
      });
    req.on("error", () => resolve(""));
    token.onCancellationRequested(() => { req.destroy(); resolve(""); });
    req.write(data);
    req.end();
  });
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function activate(context) {
  const provider = {
    async provideInlineCompletionItems(doc, pos, _ctx, token) {
      const cfg = vscode.workspace.getConfiguration("litecode");
      if (!cfg.get("enabled")) return [];
      await sleep(cfg.get("debounceMs"));
      if (token.isCancellationRequested) return [];
      const off = doc.offsetAt(pos);
      const text = doc.getText();
      const prefix = text.slice(Math.max(0, off - 3000), off);
      const suffix = text.slice(off, off + 1000);
      const out = await infill(cfg.get("url"),
        { input_prefix: prefix, input_suffix: suffix, n_predict: cfg.get("maxTokens"), temperature: 0, cache_prompt: true },
        token);
      if (!out || token.isCancellationRequested) return [];
      return [new vscode.InlineCompletionItem(out, new vscode.Range(pos, pos))];
    },
  };
  context.subscriptions.push(
    vscode.languages.registerInlineCompletionItemProvider({ pattern: "**" }, provider));
}

function deactivate() {}
module.exports = { activate, deactivate };
