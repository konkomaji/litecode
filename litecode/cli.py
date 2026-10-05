"""litecode command-line entry point.

  litecode setup          run the hardware-aware setup wizard
  litecode doctor         print detected hardware + recommended models
  litecode init           create a LITECODE.md project brief here
  litecode "task..."      run one task in the current folder
  litecode                start an interactive session in the current folder

Flags: --yes auto-approve file writes and commands; --role NAME force a model role.
"""
from __future__ import annotations
import sys
from pathlib import Path
from . import config, doctor, catalog


def _approver(auto: bool):
    def approve(action: str, detail: str) -> bool:
        if auto:
            print(f"  [auto] {action}: {detail}")
            return True
        try:
            ans = input(f"  allow {action}? {detail}\n  [y/N] ").strip().lower()
        except EOFError:
            return False
        return ans.startswith("y")
    return approve


def _events(kind, data):
    if kind == "thought":
        print(f"  . {data}")
    elif kind == "tool":
        print(f"  > {data['tool']} {data.get('args', {})}")
    elif kind == "observation":
        print(f"  < {str(data).splitlines()[0][:120]}")
    elif kind == "final":
        print(f"\n{data}\n")
    elif kind == "parse_retry":
        print("  (model broke protocol, retrying)")


def cmd_doctor():
    env = doctor.detect()
    print(env.summary())
    rec = catalog.recommend(env.ram_budget_gb, has_gpu=bool(env.gpus) and env.vulkan)
    print("\nRecommended models for this machine:")
    for role, m in rec.items():
        print(f"  {role:<10} {m.name} ({m.size_gb:.1f} GB)")


def _run_task(cfg, task, role_override, auto):
    from .server import Server
    from .agent import Agent
    from .router import route
    avail = set(config.available_roles(cfg))
    if not avail:
        print("No models installed. Run `litecode setup` first.")
        return
    prof = route(task, avail)
    role = role_override or prof["role"]
    srv = Server(cfg)
    srv.ensure(role)
    agent = Agent(srv, Path.cwd(), _approver(auto), max_steps=cfg["max_steps"], on_event=_events)
    agent.run(task)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    auto = False; role = None
    rest = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--yes", "-y"):
            auto = True
        elif a == "--role":
            role = argv[i + 1]; i += 1
        else:
            rest.append(a)
        i += 1

    cmd = rest[0] if rest else ""
    cfg = config.load()

    if cmd == "setup":
        from . import setup
        setup.run(); return
    if cmd == "doctor":
        cmd_doctor(); return
    if cmd == "init":
        from .memory import Memory
        p = Memory(Path.cwd()).ensure_brief()
        print(f"created {p}"); return
    if cmd == "help" or cmd == "--help" or cmd == "-h":
        print(__doc__); return

    if rest:  # one-shot task
        _run_task(cfg, " ".join(rest), role, auto); return

    # interactive
    avail = config.available_roles(cfg)
    if not avail:
        print("litecode: no models installed yet. Run `litecode setup`.")
        return
    print(f"litecode {__import__('litecode').__version__} in {Path.cwd()}")
    print("type a task, or /exit. roles available:", ", ".join(avail))
    while True:
        try:
            task = input("\nlitecode> ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); break
        if not task:
            continue
        if task in ("/exit", "/quit"):
            break
        _run_task(cfg, task, role, auto)


if __name__ == "__main__":
    main()
