"""litecode terminal interface.

Look: blue, light ("feather") style. A rising-bars mark, a single-line prompt
with a status line above it, braille spinner, one line per tool step, and a
one-line permission question.

Stdlib only. Colors turn off with NO_COLOR=1 or when output is not a terminal.
Unicode glyphs fall back to ASCII when the console cannot print them.
"""
from __future__ import annotations
import json, os, re, shutil, sys, threading, time

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


TTY = sys.stdout.isatty() and sys.stdin.isatty()
COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR") and _enable_vt()
try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass


def _can(s: str) -> bool:
    try:
        s.encode(sys.stdout.encoding or "ascii")
        return True
    except Exception:
        return False


UNI = _can("▁▂▃▸└◆▲›·…↵⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
G = ({"logo": "▁▂▃", "tool": "▸", "res": "└", "ans": "◆", "warn": "▲", "prompt": "›", "sep": "·",
      "ell": "…", "nl": "↵", "spin": "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"}
     if UNI else
     {"logo": "_-=", "tool": ">", "res": "`-", "ans": "*", "warn": "!", "prompt": ">", "sep": "|",
      "ell": "...", "nl": "\\n", "spin": "|/-\\"})

OUT = threading.Lock()   # one writer at a time (spinner thread vs main thread)


def c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if COLOR else text


dim = lambda t: c(t, "2")
bold = lambda t: c(t, "1")
italic = lambda t: c(t, "3")
cyan = lambda t: c(t, "36")
green = lambda t: c(t, "32")
yellow = lambda t: c(t, "33")
red = lambda t: c(t, "31")
magenta = lambda t: c(t, "35")
blue = lambda t: c(t, "38;5;33")          # litecode brand blue
sky = lambda t: c(t, "38;5;75")           # lighter blue for secondary marks
accent = blue
grey = lambda t: c(t, "38;5;245")


def width() -> int:
    return max(40, min(shutil.get_terminal_size((100, 24)).columns, 200))


def write(s: str):
    with OUT:
        sys.stdout.write(s)
        sys.stdout.flush()


_ANSI = re.compile(r"\033\[[0-9;]*[A-Za-z]")


def vlen(s: str) -> int:
    return len(_ANSI.sub("", s))


def clip(s: str, n: int) -> str:
    plain = _ANSI.sub("", s)
    return s if len(plain) <= n else plain[:max(0, n - 1)] + G["ell"][:1]


# ---------- header ----------
def welcome(version: str, cwd: str, model: str, mode: str, data_dir: str, engine: str = ""):
    w = width() - 10
    print()
    print("  " + blue(G["logo"]) + " " + bold("litecode") + " " + dim(version))
    print("  " + " " * len(G["logo"]) + " " + dim(CREDIT))
    print()
    print("  " + dim("dir   ") + clip(cwd, w))
    print("  " + dim("model ") + clip(model + (f" {G['sep']} {engine}" if engine else ""), w))
    print("  " + dim("data  ") + clip(data_dir, w))
    print()
    print("  " + dim("type a question or a task. /help lists commands. tab switches mode."))


def banner(version: str, project: str, roles: list[str], mode: str, data_dir: str):
    """Old name kept for callers."""
    welcome(version, project, ", ".join(roles), mode, data_dir)


def status(role: str, mode: str, stats, spec: str = "none"):
    print(dim(f"  {stats.gen_tokens} tok {G['sep']} {stats.seconds:.0f}s {G['sep']} {role}"))


def rule(label: str = ""):
    print(dim(("-- " + label + " ").ljust(60, "-") if label else "-" * 60))


# ---------- markdown ----------
def md_line(ln: str, in_code: bool) -> tuple[str, bool]:
    """Style one markdown line. Returns (styled, in_code_after)."""
    if ln.strip().startswith("```"):
        return dim(ln), not in_code
    if not COLOR:
        return ln, in_code
    if in_code:
        return sky(ln), True
    if re.match(r"^#{1,6} ", ln):
        return bold(blue(re.sub(r"^#{1,6} ", "", ln))), False
    ln = re.sub(r"\*\*([^*]+)\*\*", lambda m: bold(m.group(1)), ln)
    ln = re.sub(r"`([^`]+)`", lambda m: sky(m.group(1)), ln)
    ln = re.sub(r"^(\s*)([-*]|\d+\.) ", lambda m: m.group(1) + blue(m.group(2)) + " ", ln)
    return ln, False


def render_md(text: str) -> str:
    out, in_code = [], False
    for ln in text.splitlines():
        s, in_code = md_line(ln, in_code)
        out.append(s)
    return "\n".join(out)


class MdStream:
    """Print the streamed answer: a diamond mark, then indented lines. Each finished
    line is re-drawn with markdown styling when it fits on one terminal row."""

    def __init__(self):
        self.line = ""
        self.in_code = False
        self.started = False
        self.first = True

    def _mark(self):
        return blue(G["ans"]) + " "

    def feed(self, text: str):
        for ch in text:
            if not self.started:
                if ch in "\r\n" or (ch == " " and not self.line):
                    continue
                write(self._mark())
                self.started = True
            if ch == "\r":
                continue
            if ch == "\n":
                self._finish()
                write("\n  ")
                self.line = ""
            else:
                self.line += ch
                write(ch)

    def _finish(self):
        styled, self.in_code = md_line(self.line, self.in_code)
        if COLOR and styled != self.line and vlen(self.line) + 3 < width():
            write("\r\033[K" + (self._mark() if self.first else "  ") + styled)
        self.first = False

    def close(self):
        if self.started:
            self._finish()
            write("\n")


# ---------- spinner ----------
class Spinner:
    """⠹ reading 12s   (before the first token: the model reads the prompt)
       ⠹ writing 15s · 140 tok"""

    def __init__(self, label=""):
        self.label = label
        self.tokens = 0
        self._stop = threading.Event()
        self._t = None
        self.t0 = time.time()
        self.active = False

    def start(self, label=None):
        if label is not None:
            self.label = label
        if self.active:
            return self
        self.t0 = time.time()
        self.tokens = 0
        self._stop.clear()
        self.active = True
        if sys.stdout.isatty():
            self._t = threading.Thread(target=self._spin, daemon=True)
            self._t.start()
        return self

    __enter__ = start

    def _spin(self):
        i = 0
        frames = G["spin"]
        while not self._stop.is_set():
            el = time.time() - self.t0
            label = self.label or ("writing" if self.tokens else "reading")
            tok = f" {G['sep']} {self.tokens} tok" if self.tokens else ""
            line = blue(frames[i % len(frames)]) + " " + label + dim(f" {el:.0f}s{tok} {G['sep']} ctrl+c stops")
            with OUT:
                sys.stdout.write("\r\033[K" + line if COLOR else "\r" + _ANSI.sub("", line))
                sys.stdout.flush()
            i += 1
            self._stop.wait(0.09)

    def stop(self):
        if not self.active:
            return
        self._stop.set()
        if self._t:
            self._t.join(timeout=1)
            with OUT:
                sys.stdout.write("\r\033[K" if COLOR else "\r" + " " * 70 + "\r")
                sys.stdout.flush()
        self._t = None
        self.active = False

    def clear(self):
        self.stop()

    def __exit__(self, *a):
        self.stop()


# ---------- tool lines ----------
VERBS = {"read_file": "read", "write_file": "write", "edit_file": "edit", "run": "run", "list_dir": "list",
         "glob": "find", "grep": "search", "git_status": "git", "git_diff": "git", "scan": "scan",
         "remember": "note", "review": "review"}


def _short(s, n=80):
    s = str(s).replace("\n", " ")
    return s if len(s) <= n else s[:n - 1] + G["ell"][:1]


def tool_title(tool: str, args: dict) -> str:
    a = args or {}
    if tool == "read_file":
        target = a.get("path", "") + (f"  {a.get('start', 1)}-{a['end']}" if a.get("end") else "")
    elif tool in ("write_file", "edit_file"):
        target = a.get("path", "")
    elif tool == "run":
        target = _short(a.get("cmd", ""), 100)
    elif tool == "list_dir":
        target = a.get("path", ".")
    elif tool == "glob":
        target = a.get("pattern", "")
    elif tool == "grep":
        target = f'"{a.get("pattern", "")}"' + (f" in {a['glob']}" if a.get("glob") else "")
    elif tool == "git_status":
        target = "status"
    elif tool == "git_diff":
        target = ("diff " + a.get("path", "")).strip()
    elif tool == "scan":
        target = a.get("path", ".")
    elif tool == "remember":
        target = _short(a.get("text", ""), 60)
    elif tool == "review":
        target = a.get("finding", "")
    elif tool.startswith("mcp__"):
        parts = tool.split("__")
        return bold("mcp".ljust(6)) + " " + f"{parts[1]}.{'__'.join(parts[2:])} " + dim(_short(json.dumps(a), 60))
    else:
        target = _short(json.dumps(a, ensure_ascii=False), 80)
    return bold(VERBS.get(tool, tool).ljust(6)) + " " + target


def tool_result(tool: str, obs: str, max_lines: int = 4) -> list[str]:
    o = str(obs).rstrip()
    bad = o.startswith(("(denied", "(tool error", "(no such", "(missing arg", "(unknown tool",
                        "(find text", "(command timed out")) or "escapes project root" in o
    if bad:
        return [red(_short(o.splitlines()[0] if o else o, 160))]
    lines = o.splitlines()
    if tool == "read_file":
        n = sum(1 for ln in lines if re.match(r"^\d+\t", ln))
        return [f"{n} lines"]
    if tool == "list_dir":
        return ["empty folder"] if o == "(empty)" else [f"{len(lines)} entries"]
    if tool == "glob":
        return ["no files"] if o == "(no files)" else [f"{len(lines)} files"]
    if tool == "grep":
        return ["no matches"] if o == "(no matches)" else [f"{len(lines)} matches"]
    if tool in ("write_file", "edit_file"):
        return [o]
    if tool == "run":
        m = re.match(r"\(exit (\d+)", o)
        code = int(m.group(1)) if m else 0
        body = lines[1:] if m and len(lines) > 1 else ([] if m else lines)
        head = (green if code == 0 else red)(f"exit {code}")
        if body:
            head += dim(f" {G['sep']} ") + _short(body[0], 140)
        out = [head] + [dim(_short(ln, 160)) for ln in body[1:max_lines]]
        if len(body) > max_lines:
            out.append(dim(f"+{len(body) - max_lines} more lines"))
        return out
    first = [_short(ln, 160) for ln in lines[:max_lines]] or ["(no output)"]
    if len(lines) > max_lines:
        first.append(dim(f"+{len(lines) - max_lines} more lines"))
    return first


def print_tool(tool: str, args: dict):
    print(blue(G["tool"]) + " " + tool_title(tool, args))


def print_result(tool: str, obs: str):
    for i, ln in enumerate(tool_result(tool, obs)):
        print(("  " + dim(G["res"]) + " " if i == 0 else "    ") + ln)


# ---------- raw keys ----------
class Keys:
    """Read single keys. Returns a printable string or a key name."""

    def __init__(self):
        self.win = os.name == "nt"
        self._old = None

    def __enter__(self):
        if not self.win:
            import termios, codecs
            fd = sys.stdin.fileno()
            self._old = termios.tcgetattr(fd)
            new = termios.tcgetattr(fd)
            new[0] &= ~(termios.IXON | termios.ICRNL)
            new[3] &= ~(termios.ICANON | termios.ECHO | termios.ISIG | termios.IEXTEN)
            new[6][termios.VMIN] = 1
            new[6][termios.VTIME] = 0
            termios.tcsetattr(fd, termios.TCSADRAIN, new)
            self._dec = codecs.getincrementaldecoder("utf-8")("replace")
        return self

    def __exit__(self, *a):
        if self._old is not None:
            import termios
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._old)
            self._old = None

    def pending(self, wait=0.0) -> bool:
        if self.win:
            import msvcrt
            if msvcrt.kbhit():
                return True
            if wait:
                time.sleep(wait)
                return msvcrt.kbhit()
            return False
        import select
        return bool(select.select([sys.stdin.fileno()], [], [], wait)[0])

    CTRL = {"\r": "enter", "\n": "enter", "\x08": "backspace", "\x7f": "backspace", "\t": "tab",
            "\x1b": "esc", "\x03": "ctrl-c", "\x04": "ctrl-d", "\x0c": "ctrl-l", "\x15": "ctrl-u",
            "\x17": "ctrl-w", "\x01": "home", "\x05": "end", "\x0b": "ctrl-k"}

    def get(self) -> str:
        try:
            return self._get_win() if self.win else self._get_posix()
        except KeyboardInterrupt:
            return "ctrl-c"

    def _get_win(self) -> str:
        import msvcrt
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            code = msvcrt.getwch()
            return {"H": "up", "P": "down", "K": "left", "M": "right", "G": "home", "O": "end",
                    "S": "delete", "\x0f": "shift-tab", "s": "ctrl-left", "t": "ctrl-right"}.get(code, "")
        return self.CTRL.get(ch, ch)

    def _byte(self) -> str:
        while True:
            b = os.read(sys.stdin.fileno(), 1)
            if not b:
                return "\x04"
            s = self._dec.decode(b)
            if s:
                return s

    def _get_posix(self) -> str:
        ch = self._byte()
        if ch != "\x1b":
            return self.CTRL.get(ch, ch)
        if not self.pending(0.03):
            return "esc"
        nxt = self._byte()
        if nxt not in "[O":
            return "esc"
        seq = ""
        while True:
            x = self._byte()
            seq += x
            if x.isalpha() or x == "~" or len(seq) > 6:
                break
        return {"A": "up", "B": "down", "C": "right", "D": "left", "H": "home", "F": "end", "Z": "shift-tab",
                "3~": "delete", "1~": "home", "7~": "home", "4~": "end", "8~": "end",
                "1;5C": "ctrl-right", "1;5D": "ctrl-left"}.get(seq, "")


# ---------- prompt / line editor ----------
SHORTCUTS = (f"/ commands {G['sep']} @ file {G['sep']} ! shell {G['sep']} + remember {G['sep']} tab mode "
             f"{G['sep']} \\ then enter: new line {G['sep']} esc clear {G['sep']} ctrl+c quit")


class Prompt:
    """litecode input: a dim status line, then the prompt line.

          ask · MiniCPM5-2B · ? keys
        › your message

    History (up/down), left/right/home/end, Tab on an empty line switches mode,
    Tab after "/" completes a command, Esc clears, Ctrl+C twice quits, and lines
    pasted together stay one message.
    """

    PLACEHOLDER = "ask a question, or describe a task"

    def __init__(self, history_file=None, commands=()):
        self.history_file = history_file
        self.history: list[str] = []
        self.commands = sorted(commands)
        if history_file:
            try:
                with open(history_file, encoding="utf-8") as f:
                    self.history = [json.loads(x) for x in f if x.strip()][-500:]
            except Exception:
                self.history = []

    def _save(self, text):
        if not text.strip() or (self.history and self.history[-1] == text):
            return
        self.history.append(text)
        if self.history_file:
            try:
                with open(self.history_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(text) + "\n")
            except Exception:
                pass

    def read(self, status, on_mode=None) -> str | None:
        """status(): text for the line above the prompt. on_mode(): switch mode.
        Returns the message, or None to quit."""
        if not (TTY and COLOR):
            try:
                text = input("\n" + G["prompt"] + " ")
            except (EOFError, KeyboardInterrupt):
                return None
            text = text.lstrip("﻿")
            if not sys.stdin.isatty():
                print(text)          # piped input is not echoed by the terminal
            self._save(text)
            return text
        buf, cur = [], 0
        hist_i = len(self.history)
        showing_keys = False
        ctrl_c = 0
        w = width()
        write("\n" + clip(status(), w - 1) + "\n")

        def draw():
            text = "".join(buf).replace("\n", G["nl"])
            pos = len("".join(buf[:cur]).replace("\n", G["nl"]))
            avail = w - 4
            start = max(0, pos - avail + 1) if pos >= avail else 0
            if not buf:
                body, pos, start = dim(self.PLACEHOLDER[:avail]), 0, 0
            else:
                body = text[start:start + avail]
            write("\r\033[K" + blue(G["prompt"]) + " " + body + "\r\033[" + str(2 + pos - start) + "C")

        def set_status(txt):
            write("\r\033[1A\r\033[K" + clip(txt, w - 1) + "\n")
            draw()

        def finish(text):
            write("\r\033[K\033[1A\r\033[J")
            if text is not None:
                write(blue(G["prompt"]) + " " + bold(text.replace("\n", "\n  ")) + "\n")
        draw()
        with Keys() as keys:
            while True:
                k = keys.get()
                if k != "ctrl-c" and ctrl_c:
                    ctrl_c = 0
                    set_status(status())
                if k == "enter":
                    if keys.pending():          # pasted text: keep the newline in the message
                        buf.insert(cur, "\n")
                        cur += 1
                        continue
                    if cur > 0 and buf[cur - 1] == "\\":   # backslash + Enter = new line
                        buf[cur - 1] = "\n"
                        draw()
                        continue
                    text = "".join(buf)
                    finish(text)
                    self._save(text)
                    return text
                elif k == "ctrl-c":
                    if buf:
                        buf, cur = [], 0
                        draw()
                        continue
                    ctrl_c += 1
                    if ctrl_c >= 2:
                        finish(None)
                        return None
                    set_status(yellow("  press ctrl+c again to quit"))
                elif k == "ctrl-d":
                    if not buf:
                        finish(None)
                        return None
                elif k == "esc":
                    buf, cur = [], 0
                    draw()
                elif k == "backspace":
                    if cur:
                        del buf[cur - 1]
                        cur -= 1
                        draw()
                elif k == "delete":
                    if cur < len(buf):
                        del buf[cur]
                        draw()
                elif k == "left":
                    cur = max(0, cur - 1)
                    draw()
                elif k == "right":
                    cur = min(len(buf), cur + 1)
                    draw()
                elif k == "home":
                    cur = 0
                    draw()
                elif k == "end":
                    cur = len(buf)
                    draw()
                elif k == "ctrl-u":
                    del buf[:cur]
                    cur = 0
                    draw()
                elif k == "ctrl-k":
                    del buf[cur:]
                    draw()
                elif k == "ctrl-w":
                    j = cur
                    while j and buf[j - 1] == " ":
                        j -= 1
                    while j and buf[j - 1] != " ":
                        j -= 1
                    del buf[j:cur]
                    cur = j
                    draw()
                elif k in ("up", "down"):
                    if not self.history:
                        continue
                    hist_i = max(0, hist_i - 1) if k == "up" else min(len(self.history), hist_i + 1)
                    buf = list(self.history[hist_i]) if hist_i < len(self.history) else []
                    cur = len(buf)
                    draw()
                elif k in ("tab", "shift-tab"):
                    text = "".join(buf)
                    if not text and on_mode:
                        on_mode()
                        set_status(status())
                    elif text.startswith("/") and " " not in text:
                        hits = [x for x in self.commands if x.startswith(text)]
                        if len(hits) == 1:
                            buf = list(hits[0] + " ")
                            cur = len(buf)
                            set_status(status())
                        elif hits:
                            buf = list(os.path.commonprefix(hits))
                            cur = len(buf)
                            set_status(dim("  " + "  ".join(hits)))
                elif k == "?" and not buf:
                    showing_keys = not showing_keys
                    set_status(dim("  " + SHORTCUTS) if showing_keys else status())
                elif k == "ctrl-l":
                    write("\033[2J\033[H\n" + clip(status(), w - 1) + "\n")
                    draw()
                elif len(k) == 1 and k.isprintable():
                    buf.insert(cur, k)
                    cur += 1
                    if showing_keys:
                        showing_keys = False
                        set_status(status())
                    else:
                        draw()


# ---------- permission question ----------
def confirm(question: str, detail: str, choices: list[tuple[str, str]]) -> str:
    """One-line permission question:

        ▲ run a command?
          python calc.py
          [y] yes  [a] always  [n] no  [e] no, say why

    choices: [(key, label)]. Returns the chosen key. Esc or Ctrl+C returns "n".
    """
    print(yellow(G["warn"]) + " " + bold(question))
    for ln in detail.splitlines()[:40]:
        s = ln.lstrip()
        styled = red(ln) if s.startswith("- ") else green(ln) if s.startswith("+ ") else ln
        print("  " + clip(styled, width() - 3))
    keys = [k for k, _ in choices]
    if not (TTY and COLOR):
        a = ask("  " + "  ".join(f"[{k}] {lab}" for k, lab in choices) + ": ", "n").lower()[:1]
        return a if a in keys else "n"
    sel = 0

    def draw():
        parts = []
        for i, (k, lab) in enumerate(choices):
            item = f"[{k}] {lab}"
            parts.append(c(f" {item} ", "1;38;5;231;48;5;33") if i == sel else dim("[") + bold(k) + dim("]") + f" {lab}")
        write("\r\033[K  " + "  ".join(parts))
    draw()
    with Keys() as kb:
        while True:
            k = kb.get()
            if k in ("left", "shift-tab"):
                sel = (sel - 1) % len(choices)
            elif k in ("right", "tab"):
                sel = (sel + 1) % len(choices)
            elif k == "enter":
                pick = keys[sel]
                break
            elif k in ("esc", "ctrl-c"):
                pick = "n"
                break
            elif k.lower() in keys:
                pick = k.lower()
                break
            draw()
    label = dict(choices)[pick]
    write("\r\033[K  " + dim(G["res"]) + " " + (green(label) if pick in ("y", "a") else red(label)) + "\n")
    return pick


def select(title: str, detail: str, options: list[str]) -> int:
    """Index-based wrapper around confirm() for older callers."""
    keys = "123456789"[:len(options)]
    pick = confirm(title, detail, list(zip(keys, options)))
    return keys.index(pick) if pick in keys else -1


# ---------- JSON field streaming ----------
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


# ---------- simple input ----------
def ask(prompt: str, default: str = "") -> str:
    try:
        ans = input(prompt).strip()
    except EOFError:
        return default
    return ans or default


def choose_dir(label: str, default: str) -> str:
    ans = ask(f"  {label} [{default}]: ", default)
    return os.path.expanduser(ans)


def approve_prompt(action: str, detail: str):
    """Returns True, False, "always", or a string with the user's instruction ("no, do this")."""
    head, _, rest = detail.partition("\n")
    question = {"run": "run a command?", "write_file": "create a file?", "edit_file": "edit a file?",
                "mcp": "call an MCP tool?"}.get(action, f"allow {action}?")
    if action == "write_file" and "(overwrite" in head:
        question = "overwrite a file?"
    always = {"run": "always for commands", "write_file": "always for writes",
              "edit_file": "always for edits"}.get(action, "always")
    pick = confirm(question, "  " + head + ("\n" + rest if rest else ""),
                   [("y", "yes"), ("a", always), ("n", "no"), ("e", "no, say why")])
    if pick == "y":
        return True
    if pick == "a":
        return "always"
    if pick == "e":
        fb = ask("  " + blue(G["prompt"]) + " what should litecode do instead? ", "")
        return fb or False
    return False


def pretty_args(args: dict) -> str:
    s = json.dumps(args, ensure_ascii=False)
    return s if len(s) < 140 else s[:137] + "..."
