"""litecode command-line entry point.

  litecode                 interactive session in the current folder
  litecode "task..."       run one task, then exit
  litecode setup           hardware-aware setup wizard (folders, engine, models)
  litecode tune            benchmark this PC and save the fastest settings
  litecode eval [--level L] run 30 challenge tasks (basic/medium/hard), auto-checked
  litecode doctor          show hardware, config, models, engine
  litecode init            create a LITECODE.md project brief
  litecode scan [PATH]     static security scan, no model needed
  litecode review [PATH]   scan + model verdict for each finding
  litecode plan "task"     read-only plan, no file changes
  litecode skills          list skills        (skills new NAME | skills rm NAME)
  litecode mcp             list MCP servers   (mcp add NAME CMD [ARGS] | mcp rm NAME)
  litecode learn export F  write rated history as a JSONL fine-tune dataset
  litecode config [K V]    show config, or set one key
  litecode fim             serve autocomplete (fill-in-the-middle) for editors
  litecode help            full guide location and command list

Flags: --yes (auto-approve), --readonly, --role NAME, --plan.
Built by Konko Maji.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
from . import config, doctor, catalog, ui, __version__

DOCS = Path(__file__).resolve().parent.parent / "docs"


# ---------- events from the agent ----------
class Printer:
    def __init__(self):
        self.streaming = False

    def __call__(self, kind, data):
        if kind == "stream":
            if not self.streaming:
                print()
                self.streaming = True
            sys.stdout.write(data)
            sys.stdout.flush()
            return
        if self.streaming and kind != "stream":
            print()
        if kind == "thought":
            print(ui.dim(f"  . {data}"))
        elif kind == "tool":
            print(ui.cyan(f"  > {data['tool']} ") + ui.dim(ui.pretty_args(data.get("args", {}))))
        elif kind == "observation":
            first = str(data).splitlines()[0][:120] if str(data).strip() else ""
            print(ui.dim(f"  < {first}"))
        elif kind == "final":
            if not data.get("streamed"):
                print("\n" + ui.render_md(data["text"]))
            print()
            self.streaming = False
        elif kind == "parse_retry":
            print(ui.yellow("  (model broke protocol, retrying)"))
        elif kind == "learned":
            print(ui.magenta(f"  + remembered preference: {data}"))
        elif kind == "attached":
            print(ui.dim(f"  attached: {', '.join(data)}"))
        elif kind == "skill":
            print(ui.magenta(f"  skill: {data}"))
        elif kind == "saved":
            print(ui.green(f"  saved: {data}"))


class Approver:
    def __init__(self, auto: bool):
        self.auto = auto
        self.always: set[str] = set()

    def __call__(self, action: str, detail: str) -> bool:
        if self.auto or action in self.always:
            print(ui.dim(f"  [auto] {action}: {detail.splitlines()[0]}"))
            return True
        ans = ui.approve_prompt(action, detail)
        if ans == "always":
            self.always.add(action)
            return True
        return bool(ans)


# ---------- session ----------
class Session:
    """Holds server, agent, skills and MCP for one interactive run."""

    def __init__(self, cfg, auto=False, mode=None, role=None):
        from .skills import Skills
        self.cfg = cfg
        self.root = Path.cwd()
        self.mode = mode or ("auto" if auto else cfg.get("permission", "ask"))
        self.role = role
        self.srv = None
        self.agent = None
        self.session_id = None
        self.approver = Approver(self.mode == "auto")
        self.printer = Printer()
        self.skills = Skills(self.root, Path(cfg["data_dir"]))
        self.mcp = None
        self._cache_role = None

    def _mcp(self):
        from . import mcp
        if self.mcp is None:
            self.mcp = mcp.Hub(self.root, Path(self.cfg["data_dir"]), on_error=lambda m: print(ui.red(m)))
            if self.mcp.config:
                print(ui.dim(f"  starting MCP: {', '.join(self.mcp.config)}"))
            self.mcp.start()
        return self.mcp

    def _cache_name(self, role):
        from .memory import project_id
        return f"{project_id(self.root)}-{role}.bin"

    def ensure(self, role):
        from .server import Server
        if self.srv is None:
            self.srv = Server(self.cfg)
        if self.srv.role != role:
            if self.srv.role and self._cache_role:
                self.srv.save_cache(self._cache_name(self._cache_role))
            self.srv.ensure(role)
            if self.srv.restore_cache(self._cache_name(role)):
                print(ui.dim("  restored prompt cache for this project"))
            self._cache_role = role
        return self.srv

    def get_agent(self):
        from .agent import Agent
        if self.agent is None:
            self.agent = Agent(self.srv, self.root, self.approver, max_steps=self.cfg["max_steps"],
                               on_event=self.printer, session=self.session_id, cfg=self.cfg,
                               mode=self.mode, skills=self.skills, mcp=self._mcp())
            self.session_id = self.agent.session
        self.agent.server = self.srv
        self.agent.tools.mode = self.mode
        return self.agent

    def pick(self, task):
        from .router import route, PROFILES
        avail = set(config.available_roles(self.cfg))
        if not avail:
            raise SystemExit("No models installed. Run `litecode setup` first.")
        prof = route(task, avail)
        if self.role:
            if self.role in avail:
                prof = dict(PROFILES.get(self.role, PROFILES["code"]), role=self.role)
            else:
                print(ui.yellow(f"  role '{self.role}' has no model; using {prof['role']}"))
        return prof

    def task(self, text, skill=None, plan=False):
        prof = self.pick(text)
        self.ensure(prof["role"])
        a = self.get_agent()
        try:
            return a.plan(text, prof) if plan else a.run(text, prof, skill=skill)
        except KeyboardInterrupt:
            print(ui.yellow("\n  interrupted"))
            return ""

    def close(self):
        from . import learn
        if self.agent and self.srv and self.cfg.get("auto_learn", True):
            saved = learn.end_of_session(self.srv, self.agent.mem, self.agent.session)
            for f in saved:
                print(ui.magenta(f"  + learned: {f}"))
        if self.srv and self._cache_role:
            self.srv.save_cache(self._cache_name(self._cache_role))
        if self.srv:
            self.srv.stop()
        if self.mcp:
            self.mcp.stop()


# ---------- slash commands ----------
HELP = """commands:
  /help                 this list            /cost        token and time use
  /plan TASK            plan only, no edits  /mode [ask|auto|readonly]
  /review [PATH]        security review      /scan [PATH] static scan only
  /test [CMD]           run tests, fix loop  /diff        git diff
  /commit               write commit msg     /model [ROLE] show or set model role
  /remember TEXT        save project fact    /prefer TEXT save a preference (all projects)
  /memory               facts + preferences  /forget [facts|prefs]
  /good  /bad           rate the last answer (used to learn)
  /undo PATH            restore last checkpoint of a file
  /sessions             list sessions        /resume [ID] continue a session
  /clear                new session          /init        create LITECODE.md
  /skills               list skills          /skill new NAME | /skill make DESCRIPTION | /skill rm NAME
  /NAME [TASK]          run skill NAME       /mcp         list MCP tools
  /config [KEY VALUE]   show or set config   /exit        quit
  @path/file            attach a file to the message"""


def _safe_rel(root: Path, rel: str) -> Path | None:
    p = (root / rel).resolve()
    r = root.resolve()
    return p if (r in p.parents) else None


def _mem(s):
    from .memory import Memory
    return s.agent.mem if s.agent else Memory(s.root, s.cfg)


def slash(cmd: str, s: Session) -> bool:
    """Handle one slash command. Returns False to exit."""
    parts = cmd.split(maxsplit=1)
    name, arg = parts[0].lower(), (parts[1].strip() if len(parts) > 1 else "")
    mem = _mem(s)
    if name in ("/exit", "/quit"):
        return False
    if name == "/help":
        print(HELP)
    elif name == "/remember" and arg:
        print("  remembered." if mem.remember(arg) else "  already known.")
    elif name == "/prefer" and arg:
        print("  saved preference." if mem.prefer(arg) else "  already saved.")
    elif name == "/memory":
        prefs, facts = mem.profile(), mem.facts()
        print(ui.bold("  preferences (all projects):"))
        print("\n".join(f"   - {p['text']}" for p in prefs) or "   (none)")
        print(ui.bold("  facts (this project):"))
        print("\n".join(f"   - ({f['kind']}) {f['text']}" for f in facts) or "   (none)")
    elif name == "/forget":
        if arg in ("", "facts"):
            mem.forget_all()
        if arg in ("", "prefs"):
            mem.forget_profile()
        print("  forgotten.")
    elif name in ("/good", "/bad"):
        print("  rated." if mem.rate_last_example(name == "/good") else "  nothing to rate yet.")
    elif name == "/undo" and arg:
        p = _safe_rel(s.root, arg)
        if p is None:
            print(ui.red("  refused: path is outside the project."))
        else:
            data = mem.pop_checkpoint(arg)
            if data is None:
                print(f"  no checkpoint for {arg}.")
            else:
                p.write_text(data, encoding="utf-8")
                print(f"  restored {arg}.")
    elif name == "/model":
        if arg:
            s.role = None if arg == "auto" else arg
            print(f"  role: {arg}")
        else:
            for r, p in config.available_roles(s.cfg).items():
                print(f"  {r:<9} {p.name}")
            print(f"  current: {s.role or 'auto (router)'}")
    elif name == "/mode":
        if arg in ("ask", "auto", "readonly"):
            s.mode = arg
            s.approver.auto = arg == "auto"
            print(f"  mode: {arg}")
        else:
            print(f"  mode: {s.mode}  (ask | auto | readonly)")
    elif name == "/plan" and arg:
        plan = s.task(arg, plan=True)
        if plan and ui.ask("  run this plan now? [y/N] ", "n").lower().startswith("y"):
            s.task("Carry out this plan step by step:\n" + plan + "\n\nOriginal task: " + arg)
    elif name == "/review":
        s.ensure(s.pick("security review")["role"])
        print(ui.render_md(s.get_agent().review(arg or ".")))
    elif name == "/scan":
        from . import scan as sc
        print(sc.report(sc.scan(s.root, arg or ".")))
    elif name == "/test":
        cmd = arg or _test_cmd(s.root, mem)
        if not cmd:
            print("  no test command found. Use /test CMD or add 'test:' to LITECODE.md.")
        else:
            s.ensure(s.pick("fix failing tests")["role"])
            print(s.get_agent().testfix(cmd))
    elif name == "/diff":
        from .tools import Tools
        print(Tools(s.root, lambda *a: False).git_diff(arg))
    elif name == "/commit":
        s.ensure(s.pick("commit")["role"])
        msg = s.get_agent().commit_message()
        if not msg:
            print("  no changes to commit.")
        else:
            print(ui.bold("  proposed message:\n") + msg)
            if ui.ask("  commit staged + tracked changes with this message? [y/N] ", "n").lower().startswith("y"):
                import subprocess
                subprocess.run(["git", "commit", "-a", "-m", msg], cwd=s.root)
    elif name == "/cost":
        print("  " + (s.srv.stats.line() if s.srv else "no model calls yet."))
    elif name == "/sessions":
        for sid in mem.sessions()[-15:]:
            n = len(mem.turns(sid))
            print(f"  {sid}  {n} turns" + ("  (current)" if sid == s.session_id else ""))
    elif name == "/resume":
        sid = arg or mem.latest_session()
        if sid and sid in mem.sessions():
            s.session_id = sid
            s.agent = None
            print(f"  resuming {sid}.")
        else:
            print("  no such session.")
    elif name == "/clear":
        s.session_id = None
        s.agent = None
        print("  new session.")
    elif name == "/init":
        print("  created", mem.ensure_brief())
    elif name == "/skills" or (name == "/skill" and not arg):
        for sk in s.skills.list():
            print(f"  /{sk.name:<16} {ui.dim(sk.scope):<8} {sk.description}")
    elif name == "/skill":
        _skill_cmd(arg, s)
    elif name == "/mcp":
        hub = s._mcp()
        names = hub.tool_names()
        print("\n".join("  " + n for n in names) or "  no MCP servers. Add one: litecode mcp add NAME COMMAND [ARGS]")
    elif name == "/config":
        _config_cmd(arg.split(maxsplit=1), s.cfg)
    elif s.skills.get(name):
        sk = s.skills.get(name)
        s.task(arg or sk.description, skill=sk)
    else:
        print("  unknown command. /help for list.")
    return True


def _test_cmd(root: Path, mem) -> str:
    for ln in mem.brief().splitlines():
        if ln.strip().lower().startswith("- test:") and ln.split(":", 1)[1].strip():
            return ln.split(":", 1)[1].strip()
    if (root / "package.json").exists():
        return "npm test"
    if (root / "go.mod").exists():
        return "go test ./..."
    if (root / "Cargo.toml").exists():
        return "cargo test"
    if (root / "tests").exists() or (root / "pytest.ini").exists() or (root / "pyproject.toml").exists():
        return "python -m pytest -q"
    return ""


def _skill_cmd(arg: str, s: Session):
    sub, _, rest = arg.partition(" ")
    rest = rest.strip()
    if sub == "new" and rest:
        desc = ui.ask("  description (one sentence): ", "")
        trig = ui.ask("  trigger words (comma separated, optional): ", "")
        print("  steps, one per line. Empty line to finish:")
        steps = []
        while True:
            ln = ui.ask(f"  {len(steps) + 1}. ", "")
            if not ln:
                break
            steps.append(f"{len(steps) + 1}. {ln}")
        scope = "user" if ui.ask("  scope [project/user] (project): ", "project").startswith("u") else "project"
        p = s.skills.create(rest, desc, "\n".join(steps) or "1. Do the task.", trig.split(","), scope=scope)
        print(ui.green(f"  created {p}. Run it with /{rest.lower()}"))
    elif sub == "make" and rest:
        from .skills import draft_with_model
        s.ensure(s.pick("write")["role"])
        sk = draft_with_model(s.srv, rest)
        if not sk:
            print(ui.red("  the model did not return a valid skill. Try /skill new NAME."))
            return
        from .skills import render
        print(render(sk))
        if ui.ask("  save this skill? [Y/n] ", "y").lower().startswith("y"):
            p = s.skills.create(sk.name, sk.description, sk.body, sk.triggers, sk.tools)
            print(ui.green(f"  saved {p}. Run it with /{sk.name}"))
    elif sub in ("rm", "remove") and rest:
        print("  removed." if s.skills.remove(rest) else "  not found (built-in skills cannot be removed).")
    else:
        print("  /skill new NAME | /skill make DESCRIPTION | /skill rm NAME")


def _config_cmd(kv: list[str], cfg: dict):
    if len(kv) == 2:
        k, v = kv
        val = {"true": True, "false": False}.get(v.lower(), v)
        if isinstance(val, str) and val.lstrip("-").isdigit():
            val = int(val)
        if k.startswith("roles."):
            config.save({"roles": {k[6:]: val}})
            cfg["roles"][k[6:]] = val
        else:
            config.save({k: val})
            cfg[k] = val
        print(f"  {k} = {val}")
    else:
        for k, v in cfg.items():
            if isinstance(v, dict):
                for kk, vv in v.items():
                    print(f"  {k}.{kk} = {vv}")
            else:
                print(f"  {k} = {v}")


# ---------- subcommands ----------
def cmd_doctor(cfg):
    env = doctor.detect()
    print(ui.bold("Hardware"))
    print(env.summary())
    print(ui.bold("\nlitecode"))
    print(f"  version  {__version__}   {ui.CREDIT}")
    eng = Path(cfg["engine"])
    print(f"  engine   {eng} " + (ui.green("[ok]") if eng.exists() else ui.red("[missing: run litecode setup]")))
    print(f"  data     {cfg['data_dir']}")
    print(f"  models   {cfg['models_dir']}")
    print(f"  config   {config.HOME / 'config.toml'}")
    print(ui.bold("\nInstalled roles"))
    av = config.available_roles(cfg)
    for r, fn in cfg["roles"].items():
        print(f"  {r:<9} {fn} " + (ui.green("[ok]") if r in av else ui.dim("[not downloaded]")))
    rec = catalog.recommend(env.model_budget_gb, has_gpu=env.vram_gb >= 6)
    print(ui.bold("\nRecommended for this machine"))
    for role, m in rec.items():
        print(f"  {role:<9} {m.name} ({m.size_gb:.1f} GB)")


def cmd_fim(cfg):
    from .server import Server
    srv = Server(cfg, port=cfg.get("fim_port", 8081))
    srv.ensure("fim")
    print(f"autocomplete server on {srv.base}/infill  (Ctrl+C to stop)")
    print("editor setup: see docs/EDITORS.md")
    try:
        srv.proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        srv.stop()


def cmd_mcp(args, cfg):
    from . import mcp
    target = Path(cfg["data_dir"]) / "mcp.json"
    if args and args[0] == "add" and len(args) >= 3:
        mcp.save_server(target, args[1], {"command": args[2], "args": args[3:]})
        print(f"added MCP server '{args[1]}' to {target}")
    elif args and args[0] in ("rm", "remove") and len(args) >= 2:
        mcp.save_server(target, args[1], None)
        print(f"removed '{args[1]}'")
    else:
        conf = mcp.load_config(Path.cwd(), Path(cfg["data_dir"]))
        if not conf:
            print("no MCP servers. Add: litecode mcp add NAME COMMAND [ARGS...]")
        for n, spec in conf.items():
            print(f"  {n:<14} {spec.get('command')} {' '.join(spec.get('args', []))}")
        if conf and "--tools" in args:
            hub = mcp.Hub(Path.cwd(), Path(cfg["data_dir"]))
            hub.start()
            print(hub.spec_text(200))
            hub.stop()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    auto, role, mode, plan = False, None, None, False
    rest = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--yes", "-y"):
            auto = True
        elif a == "--readonly":
            mode = "readonly"
        elif a == "--plan":
            plan = True
        elif a == "--role" and i + 1 < len(argv):
            role = argv[i + 1]
            i += 1
        elif a in ("--version", "-V"):
            print(f"litecode {__version__}. {ui.CREDIT}")
            return
        else:
            rest.append(a)
        i += 1

    cmd = rest[0] if rest else ""
    cfg = config.load()

    if cmd == "setup":
        from . import setup
        setup.run()
        return
    if cmd == "doctor":
        cmd_doctor(cfg)
        return
    if cmd == "tune":
        from . import tune
        tune.run(roles=tuple(rest[1:]) or ("code",))
        return
    if cmd == "eval":
        from . import evals
        args = rest[1:]
        opt = {}
        for flag in ("--model", "--level", "--kind"):
            if flag in argv and argv.index(flag) + 1 < len(argv):
                opt[flag] = argv[argv.index(flag) + 1]
                args = [a for a in args if a != opt[flag]]
        only = [x for x in args if not x.startswith("-")]
        evals.run(role=role, only=only or None, model_file=opt.get("--model"),
                  level=opt.get("--level"), kind=opt.get("--kind"))
        return
    if cmd == "init":
        from .memory import Memory
        print(f"created {Memory(Path.cwd(), cfg).ensure_brief()}")
        return
    if cmd in ("help", "--help", "-h"):
        print(__doc__)
        print(f"Full guide: {DOCS / 'GUIDE.md'}")
        return
    if cmd == "scan":
        from . import scan as sc
        fs = sc.scan(Path.cwd(), rest[1] if len(rest) > 1 else ".")
        print(sc.to_json(fs) if "--json" in rest else sc.report(fs))
        return
    if cmd == "skills":
        from .skills import Skills
        sk = Skills(Path.cwd(), Path(cfg["data_dir"]))
        if len(rest) >= 3 and rest[1] in ("rm", "remove"):
            print("removed." if sk.remove(rest[2]) else "not found.")
            return
        if len(rest) >= 3 and rest[1] == "new":
            s = Session(cfg, auto, mode, role)
            _skill_cmd("new " + rest[2], s)
            return
        for x in sk.list():
            print(f"  /{x.name:<16} {x.scope:<8} {x.description}")
        return
    if cmd == "mcp":
        cmd_mcp(rest[1:], cfg)
        return
    if cmd == "learn":
        from .memory import Memory
        from . import learn
        if len(rest) >= 3 and rest[1] == "export":
            n = learn.export_dataset(Memory(Path.cwd(), cfg), Path(rest[2]), "--all" in rest)
            print(f"wrote {n} examples to {rest[2]}. See docs/MEMORY.md for LoRA training.")
        else:
            print("usage: litecode learn export FILE.jsonl [--all]")
        return
    if cmd == "config":
        _config_cmd(rest[1:3], cfg)
        return
    if cmd == "fim":
        cmd_fim(cfg)
        return

    s = Session(cfg, auto, mode, role)
    try:
        if cmd in ("review", "plan"):
            if cmd == "review":
                s.ensure(s.pick("security review")["role"])
                print(ui.render_md(s.get_agent().review(rest[1] if len(rest) > 1 else ".")))
            else:
                s.task(" ".join(rest[1:]), plan=True)
            return
        if rest:  # one-shot task
            s.task(" ".join(rest), plan=plan)
            return
        avail = config.available_roles(cfg)
        if not avail:
            print("litecode: no models installed yet. Run `litecode setup`.")
            return
        ui.banner(__version__, str(s.root), list(avail), s.mode, cfg["data_dir"])
        while True:
            try:
                text = input("\n" + ui.cyan("litecode> ")).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not text:
                continue
            if text.startswith("/"):
                try:
                    if not slash(text, s):
                        break
                except Exception as e:
                    print(ui.red(f"  error: {type(e).__name__}: {e}"))
                continue
            try:
                s.task(text)
            except Exception as e:
                print(ui.red(f"  error: {type(e).__name__}: {e}"))
            if s.srv:
                ui.status(s.srv.role or "-", s.mode, s.srv.stats, s.srv.spec_active)
    finally:
        s.close()


if __name__ == "__main__":
    main()
