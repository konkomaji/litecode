"""Terminal interface: colors, banner, status line, spinner, live answer streaming.

Stdlib only. Colors turn off with NO_COLOR=1 or when output is not a terminal.
"""
from __future__ import annotations
import json, os, re, sys, threading, time

CREDIT = "Built by Konko Maji"


def _enable_vt():
    if os.name == "nt":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            h = k.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            if k.GetConsoleMode(h, ctypes.byref(mode)):
                k.SetConsoleMode(h, mode.value | 0x0004)
            return True
        except Exception:
            return False
    return True


COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR") and _enable_vt()
try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass


def c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if COLOR else text


dim = lambda t: c(t, "2")
bold = lambda t: c(t, "1")
cyan = lambda t: c(t, "36")
green = lambda t: c(t, "32")
yellow = lambda t: c(t, "33")
red = lambda t: c(t, "31")
magenta = lambda t: c(t, "35")


def banner(version: str, project: str, roles: list[str], mode: str, data_dir: str):
    w = 60
    print(cyan("+" + "-" * (w - 2) + "+"))
    title = f" litecode {version}  -  local AI coding assistant"
    print(cyan("|") + bold(title.ljust(w - 2)) + cyan("|"))
    print(cyan("|") + magenta(f" {CREDIT}".ljust(w - 2)) + cyan("|"))
    print(cyan("+" + "-" * (w - 2) + "+"))
    print(f"  {dim('project')}  {project}")
    print(f"  {dim('models ')}  {', '.join(roles)}")
    print(f"  {dim('mode   ')}  {mode}   {dim('data')} {data_dir}")
    print(dim("  /help for commands, /exit to quit, @file to attach a file"))


def status(role: str, mode: str, stats, spec: str = "none"):
    s = f"[{role} | {mode} | spec:{spec} | {stats.gen_tokens} tok | {stats.seconds:.0f}s]"
    print(dim(s))


def rule(label: str = ""):
    print(dim(("-- " + label + " ").ljust(60, "-") if label else "-" * 60))


def render_md(text: str) -> str:
    """Light markdown: color headings, code blocks, bullets. Keeps text otherwise."""
    if not COLOR:
        return text
    out, in_code = [], False
    for ln in text.splitlines():
        if ln.strip().startswith("```"):
            in_code = not in_code
            out.append(dim(ln))
        elif in_code:
            out.append(c(ln, "36"))
        elif re.match(r"^#{1,6} ", ln):
            out.append(bold(yellow(ln)))
        elif re.match(r"^\s*([-*]|\d+\.) ", ln):
            out.append(re.sub(r"^(\s*(?:[-*]|\d+\.))", lambda m: green(m.group(1)), ln))
        else:
            out.append(re.sub(r"`([^`]+)`", lambda m: c(m.group(1), "36"), ln))
    return "\n".join(out)


class Spinner:
    FRAMES = "|/-\\"

    def __init__(self, label="thinking"):
        self.label = label
        self.tokens = 0
        self._stop = threading.Event()
        self._t = None
        self.t0 = time.time()

    def __enter__(self):
        if sys.stdout.isatty():
            self._t = threading.Thread(target=self._spin, daemon=True)
            self._t.start()
        return self

    def _spin(self):
        i = 0
        while not self._stop.is_set():
            el = time.time() - self.t0
            sys.stdout.write(f"\r  {self.FRAMES[i % 4]} {self.label} {el:4.0f}s {self.tokens} tok ")
            sys.stdout.flush()
            i += 1
            self._stop.wait(0.15)

    def clear(self):
        if self._t:
            sys.stdout.write("\r" + " " * 50 + "\r")
            sys.stdout.flush()

    def __exit__(self, *a):
        self._stop.set()
        if self._t:
            self._t.join(timeout=1)
        self.clear()


class FieldStreamer:
    """Stream one string field (e.g. "message") out of a JSON object while the model
    is still writing it. Lets the final answer appear live although the protocol is JSON."""

    MARK = re.compile(r'"(message)"\s*:\s*"')

    def __init__(self, emit):
        self.buf = ""
        self.emit = emit
        self.pos = None
        self.done = False
        self.shown = 0
        self.is_final = False

    def feed(self, tok: str):
        self.buf += tok
        if self.done:
            return
        if self.pos is None:
            if re.search(r'"tool"\s*:\s*"final"', self.buf):
                self.is_final = True
            if not self.is_final:
                return
            m = self.MARK.search(self.buf)
            if not m:
                return
            self.pos = m.end()
        text, closed = self._decode(self.buf[self.pos:])
        if len(text) > self.shown:
            self.emit(text[self.shown:])
            self.shown = len(text)
        if closed:
            self.done = True

    @staticmethod
    def _decode(s: str):
        out, i = [], 0
        while i < len(s):
            ch = s[i]
            if ch == '"':
                return "".join(out), True
            if ch == "\\":
                if i + 1 >= len(s):
                    break
                n = s[i + 1]
                if n == "u":
                    if i + 6 > len(s):
                        break
                    try:
                        out.append(chr(int(s[i + 2:i + 6], 16)))
                    except ValueError:
                        pass
                    i += 6
                    continue
                out.append({"n": "\n", "t": "\t", "r": "", '"': '"', "\\": "\\", "/": "/"}.get(n, n))
                i += 2
                continue
            out.append(ch)
            i += 1
        return "".join(out), False


def ask(prompt: str, default: str = "") -> str:
    try:
        ans = input(prompt).strip()
    except EOFError:
        return default
    return ans or default


def choose_dir(label: str, default: str) -> str:
    ans = ask(f"  {label} [{default}]: ", default)
    return os.path.expanduser(ans)


def approve_prompt(action: str, detail: str) -> bool:
    print(yellow(f"  allow {action}?"))
    for ln in detail.splitlines()[:30]:
        if ln.lstrip().startswith("- "):
            print(red("  " + ln))
        elif ln.lstrip().startswith("+ "):
            print(green("  " + ln))
        else:
            print("  " + ln)
    a = ask("  [y]es / [n]o / [a]lways this session: ", "n").lower()
    if a.startswith("a"):
        return "always"
    return a.startswith("y")


def pretty_args(args: dict) -> str:
    s = json.dumps(args, ensure_ascii=False)
    return s if len(s) < 140 else s[:137] + "..."
