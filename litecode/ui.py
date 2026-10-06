"""Terminal interface: welcome box, bordered prompt with a line editor, spinner,
tool lines, permission menu, and live markdown streaming.

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


UNI = _can("●⎿✻╭╮╰╯│─❯⏵⏸↓·✢✳✶✽…↵")
G = ({"dot": "●", "elbow": "⎿", "star": "✻", "tl": "╭", "tr": "╮", "bl": "╰", "br": "╯", "v": "│", "h": "─",
      "ptr": "❯", "play": "⏵⏵", "pause": "⏸", "down": "↓", "sep": "·", "ell": "…", "nl": "↵",
      "spin": "·✢✳✶✻✽✻✶✳✢"}
     if UNI else
     {"dot": "*", "elbow": "L", "star": "*", "tl": "+", "tr": "+", "bl": "+", "br": "+", "v": "|", "h": "-",
      "ptr": ">", "play": ">>", "pause": "||", "down": "v", "sep": "-", "ell": "...", "nl": "\\n",
      "spin": "|/-\\"})

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
accent = lambda t: c(t, "38;5;209")      # warm orange, used for the brand and spinner
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


# ---------- welcome ----------
def welcome(version: str, cwd: str, model: str, mode: str, data_dir: str, engine: str = ""):
    w = min(width() - 2, 72)
    inner = w - 4

    def row(text=""):
        pad = inner - vlen(text)
        return accent(G["v"]) + " " + text + " " * max(0, pad) + " " + accent(G["v"])
    lines = [accent(G["tl"] + G["h"] * (w - 2) + G["tr"]),
             row(accent(G["star"]) + " " + bold("Welcome to litecode") + dim(f"  v{version}")),
             row(),
             row(dim("/help for help, /status for your setup")),
             row(),
             row(dim("cwd:   ") + clip(cwd, inner - 7)),
             row(dim("model: ") + clip(model + (f" {G['sep']} {engine}" if engine else ""), inner - 7)),
             row(dim("data:  ") + clip(data_dir, inner - 7)),
             accent(G["bl"] + G["h"] * (w - 2) + G["br"])]
    print("\n".join(lines))
    print(" " + dim(CREDIT))
    print()
    print(dim(" Tips for getting started:"))
    print(dim(" 1. Ask a question, or ask litecode to create, fix, or explain code"))
    print(dim(" 2. Use @file to attach a file, !cmd to run a shell command, # to save a memory"))
    print(dim(" 3. Shift+Tab switches mode: ask " + G["sep"] + " auto-accept " + G["sep"] + " plan"))
    print()


def banner(version: str, project: str, roles: list[str], mode: str, data_dir: str):
    """Old name kept for callers; shows the welcome box."""
    welcome(version, project, ", ".join(roles), mode, data_dir)


def status(role: str, mode: str, stats, spec: str = "none"):
    tps = stats.gen_tokens / stats.seconds if stats.seconds else 0
    print(dim(f"  {stats.gen_tokens} tokens {G['sep']} {tps:.1f} tok/s {G['sep']} {stats.seconds:.0f}s "
              f"{G['sep']} {role}"))


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
        return c(ln, "36"), True
    if re.match(r"^#{1,6} ", ln):
        return bold(re.sub(r"^#{1,6} ", "", ln)), False
    ln = re.sub(r"\*\*([^*]+)\*\*", lambda m: bold(m.group(1)), ln)
    ln = re.sub(r"`([^`]+)`", lambda m: c(m.group(1), "36"), ln)
    ln = re.sub(r"^(\s*)([-*]|\d+\.) ", lambda m: m.group(1) + accent(m.group(2)) + " ", ln)
    return ln, False


def render_md(text: str) -> str:
    out, in_code = [], False
    for ln in text.splitlines():
        s, in_code = md_line(ln, in_code)
        out.append(s)
    return "\n".join(out)


class MdStream:
    """Print streamed answer text as Claude Code does: a dot, then indented lines.
    Each finished line is re-drawn with markdown styling (if it fits on one row)."""

    def __init__(self):
        self.line = ""
        self.in_code = False
        self.started = False
        self.first = True

    def feed(self, text: str):
        for ch in text:
            if not self.started:
                if ch in "\r\n" or (ch == " " and not self.line):
                    continue
                write(G["dot"] + " ")
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
            write("\r\033[K" + (G["dot"] + " " if self.first else "  ") + styled)
        self.first = False

    def close(self):
        if self.started:
            self._finish()
            write("\n")


# ---------- spinner ----------
class Spinner:
    """✻ Thinking… (12s · ↓ 340 tokens · ctrl+c to interrupt)"""

    def __init__(self, label="Thinking"):
        self.label = label
        self.tokens = 0
        self._stop = threading.Event()
        self._t = None
        self.t0 = time.time()
        self.active = False

    def start(self, label=None):
        if label:
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
            tok = f" {G['sep']} {G['down']} {self.tokens} tokens" if self.tokens else ""
            line = (accent(frames[i % len(frames)]) + " " + accent(self.label + G["ell"]) +
                    dim(f" ({el:.0f}s{tok} {G['sep']} ctrl+c to interrupt)"))
            with OUT:
                sys.stdout.write("\r\033[K" + line if COLOR else "\r" + _ANSI.sub("", line))
                sys.stdout.flush()
            i += 1
            self._stop.wait(0.12)

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
TOOL_TITLES = {"read_file": "Read", "write_file": "Write", "edit_file": "Update", "run": "Bash",
               "list_dir": "List", "glob": "Search", "grep": "Search", "git_status": "Git",
               "git_diff": "Git", "scan": "Scan", "remember": "Remember", "review": "Review"}


def _short(s, n=80):
    s = str(s).replace("\n", " ")
    return s if len(s) <= n else s[:n - 1] + G["ell"][:1]


def tool_title(tool: str, args: dict) -> str:
    a = args or {}
    if tool == "read_file":
        rng = f", lines {a.get('start', 1)}-{a['end']}" if a.get("end") else ""
        inner = f"{a.get('path', '')}{rng}"
    elif tool in ("write_file", "edit_file"):
        inner = a.get("path", "")
    elif tool == "run":
        inner = _short(a.get("cmd", ""), 100)
    elif tool == "list_dir":
        inner = a.get("path", ".")
    elif tool == "glob":
        inner = f'pattern: "{a.get("pattern", "")}"'
    elif tool == "grep":
        inner = f'pattern: "{a.get("pattern", "")}"' + (f', glob: "{a["glob"]}"' if a.get("glob") else "")
    elif tool == "git_status":
        inner = "status"
    elif tool == "git_diff":
        inner = ("diff " + a.get("path", "")).strip()
    elif tool == "scan":
        inner = a.get("path", ".")
    elif tool == "remember":
        inner = _short(a.get("text", ""), 60)
    elif tool == "review":
        inner = a.get("finding", "")
    elif tool.startswith("mcp__"):
        parts = tool.split("__")
        return bold(f"{parts[1]} - {'__'.join(parts[2:])}") + dim(" (MCP)") + f"({_short(json.dumps(a), 80)})"
    else:
        inner = _short(json.dumps(a, ensure_ascii=False), 80)
    return bold(TOOL_TITLES.get(tool, tool)) + f"({inner})"


def tool_result(tool: str, obs: str, max_lines: int = 4) -> list[str]:
    o = str(obs).rstrip()
    bad = o.startswith(("(denied", "(tool error", "(no such", "(missing arg", "(unknown tool",
                        "(find text", "(command timed out")) or "escapes project root" in o
    if bad:
        return [red(_short(o.splitlines()[0] if o else o, 160))]
    lines = o.splitlines()
    if tool == "read_file":
        n = sum(1 for ln in lines if re.match(r"^\d+\t", ln))
        return [f"Read {bold(str(n))} lines"]
    if tool == "list_dir":
        return ["Empty folder"] if o == "(empty)" else [f"Listed {bold(str(len(lines)))} paths"]
    if tool == "glob":
        return ["Found 0 files"] if o == "(no files)" else [f"Found {bold(str(len(lines)))} files"]
    if tool == "grep":
        return ["Found 0 matches"] if o == "(no matches)" else [f"Found {bold(str(len(lines)))} matches"]
    if tool == "write_file":
        return [o.replace("wrote ", "Wrote ")]
    if tool == "edit_file":
        return [o.replace("edited ", "Updated ")]
    if tool == "run":
        m = re.match(r"\(exit (\d+)", o)
        code = int(m.group(1)) if m else 0
        body = lines[1:] if m and len(lines) > 1 else ([] if m else lines)
        head = (green if code == 0 else red)(f"exit {code}")
        out = [head] + [dim(_short(ln, 160)) for ln in body[:max_lines]]
        if len(body) > max_lines:
            out.append(dim(f"{G['ell']} +{len(body) - max_lines} lines"))
        return out
    first = [_short(ln, 160) for ln in lines[:max_lines]] or ["(no output)"]
    if len(lines) > max_lines:
        first.append(dim(f"{G['ell']} +{len(lines) - max_lines} lines"))
    return first


def print_tool(tool: str, args: dict):
    color = green if tool not in ("run", "write_file", "edit_file") else accent
    print(color(G["dot"]) + " " + tool_title(tool, args))


def print_result(tool: str, obs: str):
    for i, ln in enumerate(tool_result(tool, obs)):
        print(("  " + dim(G["elbow"]) + "  " if i == 0 else "     ") + ln)


# ---------- raw keys ----------
class Keys:
    """Read single keys. Returns a printable string or a key name."""

    def __init__(self):
        self.win = os.name == "nt"
        self._old = None

    def __enter__(self):
        if not self.win:
            import termios
            fd = sys.stdin.fileno()
            self._old = termios.tcgetattr(fd)
            new = termios.tcgetattr(fd)
            new[0] &= ~(termios.IXON | termios.ICRNL)
            new[3] &= ~(termios.ICANON | termios.ECHO | termios.ISIG | termios.IEXTEN)
            new[6][termios.VMIN] = 1
            new[6][termios.VTIME] = 0
            termios.tcsetattr(fd, termios.TCSADRAIN, new)
            import codecs
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
class Prompt:
    """Bordered input like Claude Code:

        ────────────────────────────
        > your message
        ────────────────────────────
          ? for shortcuts

    Supports history (up/down), left/right/home/end, Tab completion for slash
    commands, Shift+Tab mode switch, Esc to clear, Ctrl+C twice to exit, and
    multi-line paste (lines that arrive together stay in one message).
    """

    PLACEHOLDER = 'Try "create calc.py that adds two numbers" or ask a question'

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

    def read(self, footer, on_shift_tab=None) -> str | None:
        """footer(): str for the line under the box. on_shift_tab(): called on Shift+Tab.
        Returns the message, or None to exit."""
        if not (TTY and COLOR):
            try:
                text = input("\n> ")
            except (EOFError, KeyboardInterrupt):
                return None
            text = text.lstrip("﻿")
            if not sys.stdin.isatty():
                print(text)          # piped input is not echoed by the terminal
            self._save(text)
            return text
        buf, cur = [], 0
        hist_i = len(self.history)
        note = ""
        ctrl_c = 0
        w = width()
        line = dim(G["h"] * (w - 1))
        write("\n" + line + "\n\n" + line + "\n" + clip(footer(), w - 1) + "\033[2A\r")

        def draw():
            nonlocal w
            text = "".join(buf).replace("\n", G["nl"])
            pos = len("".join(buf[:cur]).replace("\n", G["nl"]))
            avail = w - 4
            start = max(0, pos - avail + 1) if pos >= avail else 0
            shown = text[start:start + avail]
            if not buf:
                body = dim(self.PLACEHOLDER[:avail])
                pos, start = 0, 0
            else:
                body = shown
            write("\r\033[K" + bold("> ") + body + "\r\033[" + str(2 + pos - start) + "C")

        def set_footer(txt):
            write("\033[2B\r\033[K" + clip(txt, w - 1) + "\033[2A")
            draw()

        def finish(text):
            write("\033[1A\r\033[J")
            if text is not None:
                shown = text.replace("\n", "\n  ")
                write(grey("> " + shown) + "\n")
        draw()
        with Keys() as keys:
            while True:
                k = keys.get()
                if k != "ctrl-c" and ctrl_c:
                    ctrl_c = 0
                    set_footer(footer())
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
                    set_footer(yellow("  Press Ctrl+C again to exit"))
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
                elif k == "shift-tab":
                    if on_shift_tab:
                        on_shift_tab()
                    set_footer(footer())
                elif k == "tab":
                    text = "".join(buf)
                    if text.startswith("/") and " " not in text:
                        hits = [x for x in self.commands if x.startswith(text)]
                        if len(hits) == 1:
                            buf = list(hits[0] + " ")
                            cur = len(buf)
                            set_footer(footer())
                        elif hits:
                            pre = os.path.commonprefix(hits)
                            buf = list(pre)
                            cur = len(buf)
                            set_footer(dim("  " + "  ".join(hits)))
                elif k == "?" and not buf:
                    note = "" if note else SHORTCUTS
                    set_footer(dim(note) if note else footer())
                elif k == "ctrl-l":
                    write("\033[2J\033[H")
                    write("\n" + line + "\n\n" + line + "\n" + clip(footer(), w - 1) + "\033[2A\r")
                    draw()
                elif len(k) == 1 and k.isprintable():
                    buf.insert(cur, k)
                    cur += 1
                    if note:
                        note = ""
                        set_footer(footer())
                    else:
                        draw()


SHORTCUTS = ("  / commands  @ attach file  ! shell  # remember  shift+tab mode  "
             "\\+enter newline  esc clear  ctrl+c exit")


# ---------- permission menu ----------
def select(title: str, detail: str, options: list[str]) -> int:
    """Claude Code style choice box. Returns the chosen index, or -1 for Esc."""
    w = min(width() - 1, 100)
    v = accent(G["v"])
    print(accent(G["tl"] + G["h"] + " ") + bold(title) + " " + accent(G["h"] * max(2, w - vlen(title) - 4)))
    for ln in detail.splitlines()[:40]:
        s = ln.lstrip()
        styled = red(ln) if s.startswith("- ") else green(ln) if s.startswith("+ ") else ln
        print(v + " " + clip(styled, w - 3))
    print(v)
    print(v + " Do you want to proceed?")
    if not (TTY and COLOR):
        for i, o in enumerate(options):
            print(v + f" {i + 1}. {o}")
        print(accent(G["bl"] + G["h"] * (w - 1)))
        a = ask("  choice [1]: ", "1").lower()
        m = {"y": 0, "a": 1, "n": len(options) - 1}
        if a[:1] in m:
            return m[a[:1]]
        return int(a) - 1 if a.isdigit() and 0 < int(a) <= len(options) else len(options) - 1
    sel = 0

    def draw(first=False):
        if not first:
            write(f"\033[{len(options) + 1}A")
        for i, o in enumerate(options):
            mark = accent(G["ptr"]) if i == sel else " "
            txt = bold(f"{i + 1}. {o}") if i == sel else f"{i + 1}. {o}"
            write("\r\033[K" + v + f" {mark} " + txt + "\n")
        write("\r\033[K" + accent(G["bl"] + G["h"] * (w - 1)) + "\n")
    draw(True)
    with Keys() as keys:
        while True:
            k = keys.get()
            if k == "up":
                sel = (sel - 1) % len(options)
            elif k == "down":
                sel = (sel + 1) % len(options)
            elif k == "enter":
                return sel
            elif k in ("esc", "ctrl-c"):
                return -1
            elif k.isdigit() and 0 < int(k) <= len(options):
                sel = int(k) - 1
                draw()
                return sel
            elif k.lower() == "y":
                return 0
            elif k.lower() == "n":
                return len(options) - 1
            draw()


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
    """Returns True, False, "always", or a string with the user's instruction (a "no, do this")."""
    titles = {"run": "Bash command", "write_file": "Create file", "edit_file": "Edit file", "mcp": "MCP tool"}
    head, _, rest = detail.partition("\n")
    title = titles.get(action, action)
    if action == "write_file" and "(overwrite" in head:
        title = "Overwrite file"
    body = "  " + head + ("\n" + rest if rest else "")
    always = {"run": "Yes, and don't ask again for commands this session",
              "write_file": "Yes, and allow all file writes this session",
              "edit_file": "Yes, and allow all edits this session"}.get(action, "Yes, and don't ask again this session")
    i = select(title, body, ["Yes", always, "No, and tell litecode what to do differently (esc)"])
    if i == 0:
        return True
    if i == 1:
        return "always"
    fb = ask("  " + accent(G["ptr"]) + " what should litecode do instead? (Enter to just stop) ", "")
    return fb or False


def pretty_args(args: dict) -> str:
    s = json.dumps(args, ensure_ascii=False)
    return s if len(s) < 140 else s[:137] + "..."
