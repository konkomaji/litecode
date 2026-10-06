# Commands

## Shell commands

| Command | What it does |
|---|---|
| `litecode` | interactive session in the current folder |
| `litecode "TASK"` | run one task, then exit |
| `litecode setup` | wizard: folders, engine, models |
| `litecode tune [ROLE...]` | measure speed, save best threads and speculative mode |
| `litecode doctor` | hardware, config, engine, installed models |
| `litecode init` | create `LITECODE.md` |
| `litecode scan [PATH] [--json]` | static security scan, no model |
| `litecode review [PATH]` | scan, then model verdict per finding |
| `litecode plan "TASK"` | read-only plan |
| `litecode skills` | list skills |
| `litecode skills new NAME` | create a skill step by step |
| `litecode skills rm NAME` | delete a user or project skill |
| `litecode mcp` | list MCP servers (`--tools` to list their tools) |
| `litecode mcp add NAME CMD [ARGS...]` | add an MCP server to the user config |
| `litecode mcp rm NAME` | remove it |
| `litecode learn export FILE [--all]` | write a fine-tune dataset (rated tasks; `--all` adds unrated) |
| `litecode config` | show all settings |
| `litecode config KEY VALUE` | set one setting (`roles.code NAME.gguf` for roles) |
| `litecode fim` | autocomplete server for editors |
| `litecode --version` | version |

Flags: `--yes` (approve all), `--readonly`, `--role NAME`, `--plan`.

## Slash commands (in a session)

| Command | What it does |
|---|---|
| `/help` | list commands |
| `/plan TASK` | plan with no edits, then ask to run it |
| `/review [PATH]` | security review |
| `/scan [PATH]` | static scan only |
| `/test [CMD]` | run tests; if they fail, fix and run again (max 3 rounds) |
| `/diff` | `git diff` |
| `/commit` | model writes a commit message; you confirm before commit |
| `/model [ROLE]` | show roles, or force one (`auto` = router decides) |
| `/mode [ask\|auto\|readonly]` | permission mode |
| `/remember TEXT` | save a project fact |
| `/prefer TEXT` | save a preference for all projects |
| `/memory` | show preferences and facts |
| `/forget [facts\|prefs]` | delete memory (both if no argument) |
| `/good`, `/bad` | rate the last answer |
| `/undo PATH` | restore the newest checkpoint of a file |
| `/sessions` | list sessions in this project |
| `/resume [ID]` | continue a session (latest if no ID) |
| `/clear` | start a new session |
| `/init` | create `LITECODE.md` |
| `/skills` | list skills |
| `/skill new NAME` | create a skill step by step |
| `/skill make DESCRIPTION` | model drafts a skill; you confirm |
| `/skill rm NAME` | delete a skill |
| `/NAME [TASK]` | run skill NAME |
| `/mcp` | list MCP tools |
| `/config [KEY VALUE]` | show or set config |
| `/cost` | tokens and model time this session |
| `/exit` | quit (saves cache, extracts facts) |

## Config keys

| Key | Default | Meaning |
|---|---|---|
| `engine` | `<home>/engine/llama-server` | llama.cpp server binary |
| `models_dir` | `<home>/models` | GGUF folder |
| `data_dir` | `~/.litecode` | cache, slots, scratch, memory, skills |
| `project_memory` | `project` | `project` or `central` |
| `threads` | 4 | CPU threads |
| `ctx` | 8192 | context tokens |
| `kv_type` | `q8_0` | KV cache type |
| `cache_ram_mb` | 1024 | server prompt cache RAM |
| `gpu_layers` | 0 | layers on GPU (GPU builds only) |
| `speculative` | `auto` | `auto`, `off`, `ngram-simple`, `ngram-mod` |
| `kv_persist` | true | save prompt cache per project |
| `permission` | `ask` | default permission mode |
| `auto_learn` | true | extract facts at session end |
| `lora` | empty | LoRA adapter path |
| `max_steps` | 24 | tool steps per task |
| `temperature` | 0.1 | sampling temperature |
| `port`, `fim_port` | 8080, 8081 | local ports |
| `roles.<role>` | see config | model file per role: code, chat, fim, security, quality |
