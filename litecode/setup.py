"""First-run setup wizard.

1. Detect hardware.
2. Ask where to keep data (cache, KV slots, scratchpad, memory, skills) and models.
3. Get the llama.cpp engine (existing path, or download the official release build).
4. Recommend a model set that fits, ask permission, download with resume.
5. Write ~/.litecode/config.toml.
"""
from __future__ import annotations
import json, os, platform, shutil, sys, tarfile, time, urllib.request, zipfile
from pathlib import Path
from . import doctor, catalog, config, ui

RELEASES = "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest"


def _fmt(m: catalog.Model) -> str:
    tag = "  [security-permissive, official]" if m.official_permissive else ""
    return f"{m.name:<26} {m.size_gb:4.1f} GB dl / ~{m.ram_gb:3.1f} GB RAM   {m.note}{tag}"


def _ask(prompt: str, default: str = "y") -> bool:
    ans = ui.ask(f"{prompt} [{'Y/n' if default == 'y' else 'y/N'}] ", default).lower()
    return ans.startswith("y")


def _download(url: str, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    have = tmp.stat().st_size if tmp.exists() else 0
    req = urllib.request.Request(url, headers={"User-Agent": "litecode"})
    if have:
        req.add_header("Range", f"bytes={have}-")
    with urllib.request.urlopen(req, timeout=60) as r:
        if have and r.status != 206:
            have = 0   # server ignored the range; start over
        total = int(r.headers.get("Content-Length", 0)) + have
        done = have
        t0 = time.time()
        last = 0
        with open(tmp, "ab" if have else "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if time.time() - last > 0.5:
                    spd = (done - have) / max(1e-6, time.time() - t0) / 1e6
                    pct = f"{done / total * 100:4.1f}%" if total else f"{done / 1e6:.0f}MB"
                    sys.stdout.write(f"\r    {dest.name}: {pct}  {spd:5.1f} MB/s   ")
                    sys.stdout.flush()
                    last = time.time()
    if dest.exists():
        dest.unlink()
    tmp.rename(dest)
    sys.stdout.write(f"\r    {dest.name}: done ({dest.stat().st_size / 1e9:.2f} GB)        \n")


def pick_engine_asset(assets: list[dict], system: str, machine: str, gpu: str = "cpu") -> dict | None:
    """Choose the llama.cpp release archive for this OS/CPU. gpu: cpu | vulkan."""
    names = {a["name"].lower(): a for a in assets}
    arm = machine.lower() in ("arm64", "aarch64")
    if system == "Windows":
        prefs = [f"bin-win-{gpu}-{'arm64' if arm else 'x64'}", "bin-win-cpu-x64"]
    elif system == "Darwin":
        prefs = ["bin-macos-arm64" if arm else "bin-macos-x64"]
    else:
        prefs = ([f"bin-ubuntu-{gpu}-{'arm64' if arm else 'x64'}"] if gpu != "cpu" else []) + \
                [f"bin-ubuntu-{'arm64' if arm else 'x64'}"]
    for pref in prefs:
        for n, a in names.items():
            if pref in n and n.endswith((".zip", ".tar.gz")) and "cudart" not in n:
                return a
    return None


def _find_server(root: Path) -> Path | None:
    exe = "llama-server.exe" if os.name == "nt" else "llama-server"
    hits = sorted(root.rglob(exe), key=lambda p: len(p.parts))
    return hits[0] if hits else None


def install_engine(dest_dir: Path, gpu: str = "cpu") -> Path:
    req = urllib.request.Request(RELEASES, headers={"User-Agent": "litecode",
                                                    "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        rel = json.load(r)
    asset = pick_engine_asset(rel.get("assets", []), platform.system(), platform.machine(), gpu)
    if not asset:
        raise RuntimeError("no prebuilt llama.cpp for this OS; build it and set engine in config.toml")
    dest_dir.mkdir(parents=True, exist_ok=True)
    arch = dest_dir / asset["name"]
    print(f"  downloading engine {rel.get('tag_name', '')} ({asset['name']}) ...")
    _download(asset["browser_download_url"], arch)
    if arch.name.endswith(".zip"):
        with zipfile.ZipFile(arch) as z:
            z.extractall(dest_dir)
    else:
        with tarfile.open(arch) as t:
            t.extractall(dest_dir)
    arch.unlink()
    srv = _find_server(dest_dir)
    if not srv:
        raise RuntimeError("engine archive had no llama-server")
    if os.name != "nt":
        for p in srv.parent.glob("llama-*"):
            p.chmod(0o755)
    return srv


def run():
    cfg = config.load()
    print(ui.bold("litecode setup") + "  " + ui.magenta(ui.CREDIT))
    print("=" * 60)
    env = doctor.detect()
    print(env.summary())
    print("=" * 60)

    # 1. locations
    print("\nWhere should litecode keep its files? Press Enter to accept.")
    print(ui.dim("  data = cache, KV slots, scratchpad, memory, skills. Pick a disk with free space."))
    data_dir = ui.choose_dir("data folder", cfg["data_dir"])
    models_dir = ui.choose_dir("models folder (several GB)", cfg["models_dir"])
    central = _ask("Keep project memory in the data folder instead of each project's .litecode/?", "n")
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    Path(models_dir).mkdir(parents=True, exist_ok=True)
    updates = {"data_dir": data_dir, "models_dir": models_dir,
               "project_memory": "central" if central else "project"}

    # 2. engine
    engine = Path(cfg["engine"])
    if engine.exists():
        print(f"\n  engine: {engine}")
    else:
        found = shutil.which("llama-server")
        if found:
            engine = Path(found)
            print(f"\n  engine found on PATH: {engine}")
        elif _ask("\nDownload the llama.cpp engine (about 30-80 MB)?", "y"):
            gpu = "vulkan" if env.vulkan and _ask("  Vulkan GPU found. Use the Vulkan build?", "n") else "cpu"
            try:
                engine = install_engine(Path(data_dir) / "engine", gpu)
            except Exception as e:
                print(ui.red(f"  engine download failed: {e}"))
        else:
            p = ui.ask("  path to llama-server: ", "")
            engine = Path(p) if p else engine
    updates["engine"] = str(engine)
    updates["threads"] = env.cores or cfg["threads"]

    # 3. models
    budget = env.ram_budget_gb
    want_sec = _ask("\nInstall a security-permissive model for authorized pentest / CTF work?", "y")
    rec = catalog.recommend(budget, want_security=want_sec, has_gpu=bool(env.gpus) and env.vulkan)
    print(f"\nRecommended model set for ~{budget:.0f} GB RAM budget:\n")
    seen: dict = {}
    for role, m in rec.items():
        seen.setdefault(m.key, []).append(role)
    for key, roles in seen.items():
        print(f"  [{','.join(roles):<14}] {_fmt(catalog.BY_KEY[key])}")
    need = [k for k in seen if not (Path(models_dir) / catalog.BY_KEY[k].file).exists()]
    total_dl = sum(catalog.BY_KEY[k].size_gb for k in need)
    print(f"\n  To download: ~{total_dl:.1f} GB into {models_dir}")
    free = shutil.disk_usage(models_dir).free / 1e9
    if free < total_dl + 2:
        print(ui.yellow(f"  WARNING: only {free:.0f} GB free on that disk."))

    chosen = {}
    if total_dl == 0 or _ask("\nProceed?", "y"):
        for key, roles in seen.items():
            m = catalog.BY_KEY[key]
            dest = Path(models_dir) / m.file
            if dest.exists():
                print(f"  have {m.file}")
            else:
                print(f"  downloading {m.name} ...")
                try:
                    _download(m.url, dest)
                except Exception as e:
                    print(ui.red(f"    FAILED: {e}  (re-run setup to resume)"))
                    continue
            for r in roles:
                chosen[r] = m.file
    if chosen:
        updates["roles"] = chosen
    p = config.save(updates)
    print(f"\nSetup complete. Config: {p}")
    print("Next: run `litecode tune` once (about 5 minutes) to tune speed for this PC.")
    print("Then run `litecode` in any project folder.")
