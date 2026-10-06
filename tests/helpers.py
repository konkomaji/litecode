import json, tempfile, shutil
from pathlib import Path
from litecode import config
from litecode.server import Stats


class FakeServer:
    """Replays scripted replies. Records every message list it receives."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.stats = Stats()
        self.role = "code"
        self.spec_active = "none"

    def chat(self, messages, temperature=None, max_tokens=1024, grammar=None, stop=None,
             thinking=False, on_token=None):
        self.calls.append([dict(m) for m in messages])
        r = self.replies.pop(0) if self.replies else '{"tool":"final","args":{"message":"done"}}'
        if not isinstance(r, str):
            r = json.dumps(r)
        if on_token:
            for i in range(0, len(r), 7):
                on_token(r[i:i + 7])
        self.stats.add(10, len(r) // 4, 0.1)
        return r


class TempProject:
    def __enter__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="litecode-test-"))
        self.root = self.tmp / "proj"
        self.root.mkdir()
        self.cfg = config.load()
        self.cfg["data_dir"] = str(self.tmp / "data")
        self.cfg["project_memory"] = "project"
        return self

    def __exit__(self, *a):
        shutil.rmtree(self.tmp, ignore_errors=True)


def yes(*a):
    return True


def no(*a):
    return False
