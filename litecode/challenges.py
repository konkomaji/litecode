"""Challenge sets for `litecode eval`: 30 real tasks in 3 levels and 9 kinds.

Each challenge has starting files, a task, and a check. The check is Python code
run inside the project folder; exit code 0 = pass. The model's final answer is in
the ANSWER environment variable. `fix` is a reference solution used only by the
test suite to prove every check passes on a correct result and fails on the start.
"""
from __future__ import annotations
from dataclasses import dataclass, field

LEVELS = ("basic", "medium", "hard")
KINDS = ("fix", "feature", "refactor", "security", "testfix", "qa", "data", "shell", "writing")

WORDS = "import os,re; A=os.environ.get('ANSWER',''); W=lambda t: len(re.findall(r\"[\\w'$:.,-]+\", t)); "


@dataclass
class Challenge:
    name: str
    level: str
    kind: str
    files: dict
    task: str
    check: str
    fix: dict = field(default_factory=dict)   # reference solution files
    answer: str = ""                          # reference final answer


C = Challenge
CHALLENGES: list[Challenge] = [
    # ------------------------------------------------------------------ BASIC
    C("fix-one-line", "basic", "fix",
      {"calc.py": "def add(a, b):\n    return a - b\n",
       "test_calc.py": "from calc import add\nassert add(2, 3) == 5\nprint('ok')\n"},
      "Fix the bug so that `python test_calc.py` prints ok. Run it to check.",
      "import calc; assert calc.add(2,3)==5 and calc.add(-1,1)==0",
      {"calc.py": "def add(a, b):\n    return a + b\n"}),
    C("read-config-value", "basic", "qa",
      {"config.py": "TIMEOUT = 30\nRETRIES = 4\nHOST = 'db.local'\n"},
      "How many retries does config.py set? Answer with the number only.",
      WORDS + "assert '4' in A and W(A) <= 12, A", answer="4"),
    C("add-docstrings", "basic", "refactor",
      {"util.py": "def clamp(x, lo, hi):\n    return max(lo, min(x, hi))\n\n\ndef lerp(a, b, t):\n    return a + (b - a) * t\n"},
      "Add a one-line docstring to every function in util.py. Do not change behavior.",
      "import ast,util; t=ast.parse(open('util.py').read()); "
      "assert all(ast.get_docstring(f) for f in t.body if isinstance(f, ast.FunctionDef)); "
      "assert util.clamp(5,0,3)==3 and util.lerp(0,10,0.5)==5",
      {"util.py": "def clamp(x, lo, hi):\n    \"\"\"Limit x to [lo, hi].\"\"\"\n    return max(lo, min(x, hi))\n\n\n"
                  "def lerp(a, b, t):\n    \"\"\"Linear interpolation.\"\"\"\n    return a + (b - a) * t\n"}),
    C("explain-code", "basic", "writing",
      {"decode.py": "def decode(s):\n    out = []\n    for ch in s:\n        if ch.isalpha():\n"
                    "            base = ord('a') if ch.islower() else ord('A')\n"
                    "            out.append(chr((ord(ch) - base + 13) % 26 + base))\n        else:\n"
                    "            out.append(ch)\n    return ''.join(out)\n"},
      "Explain what decode.py does in at most 3 sentences. Name the cipher.",
      WORDS + "assert re.search(r'rot.?13|caesar', A, re.I), A; assert W(A) <= 80, W(A)",
      answer="decode() applies ROT13. It shifts each letter by 13 places and keeps case. Other characters stay the same."),
    C("edit-json-config", "basic", "data",
      {"settings.json": '{\n  "debug": true,\n  "name": "demo"\n}\n'},
      "In settings.json set debug to false and add the key port with the number 8080. Keep name.",
      "import json; d=json.load(open('settings.json')); assert d=={'debug':False,'name':'demo','port':8080}, d",
      {"settings.json": '{"debug": false, "name": "demo", "port": 8080}\n'}),
    C("write-email", "basic", "writing",
      {},
      "Write email.txt: tell the team the server update moves to Friday 18:00. The first line must start with "
      "'Subject:'. Max 80 words.",
      WORDS + "t=open('email.txt',encoding='utf-8').read(); assert t.lstrip().startswith('Subject:'); "
      "assert 'Friday' in t and '18:00' in t; assert W(t) <= 80, W(t)",
      {"email.txt": "Subject: Server update moved to Friday\n\nHi team,\nThe server update now happens on Friday at 18:00.\n"}),
    C("fix-javascript", "basic", "fix",
      {"sum.js": "function sum(xs) {\n  let t = 0;\n  for (let i = 1; i < xs.length; i++) t += xs[i];\n  return t;\n}\n"
                 "console.log(sum([1, 2, 3]));\n"},
      "Fix sum.js so that `node sum.js` prints 6.",
      "import subprocess,shutil; n=shutil.which('node'); "
      "assert n is None or subprocess.run([n,'sum.js'],capture_output=True,text=True).stdout.strip()=='6'; "
      "assert 'i = 0' in open('sum.js').read() or 'reduce' in open('sum.js').read() or 'of xs' in open('sum.js').read()",
      {"sum.js": "function sum(xs) {\n  let t = 0;\n  for (let i = 0; i < xs.length; i++) t += xs[i];\n  return t;\n}\n"
                 "console.log(sum([1, 2, 3]));\n"}),
    C("remove-hardcoded-secret", "basic", "security",
      {"client.py": "API_KEY = 'sk_live_9f8e7d6c5b4a'\n\ndef headers():\n    return {'Authorization': 'Bearer ' + API_KEY}\n"},
      "client.py has a hardcoded API key. Read it from the environment variable API_KEY instead.",
      "import os; t=open('client.py').read(); assert 'sk_live' not in t; os.environ['API_KEY']='abc'; "
      "import client; assert client.headers()=={'Authorization':'Bearer abc'}",
      {"client.py": "import os\n\ndef headers():\n    return {'Authorization': 'Bearer ' + os.environ['API_KEY']}\n"}),
    C("count-files", "basic", "shell",
      {"logs/a.log": "x\n", "logs/b.log": "y\n", "logs/c.log": "z\n", "logs/readme.txt": "n\n", "app.log": "q\n"},
      "How many .log files are inside the logs folder? Answer with the number only.",
      WORDS + "assert re.search(r'\\b3\\b', A) and W(A) <= 12, A", answer="3"),
    C("fizzbuzz", "basic", "feature",
      {},
      "Create fizz.py with a function fizzbuzz(n) that returns a list of strings for 1..n: 'Fizz' for multiples "
      "of 3, 'Buzz' for 5, 'FizzBuzz' for both, else the number as a string.",
      "from fizz import fizzbuzz as f; r=f(15); assert r[0]=='1' and r[2]=='Fizz' and r[4]=='Buzz' and r[14]=='FizzBuzz' and len(r)==15",
      {"fizz.py": "def fizzbuzz(n):\n    return ['FizzBuzz' if i % 15 == 0 else 'Fizz' if i % 3 == 0 else 'Buzz' if i % 5 == 0 "
                  "else str(i) for i in range(1, n + 1)]\n"}),

    # ----------------------------------------------------------------- MEDIUM
    C("fix-across-files", "medium", "fix",
      {"shop/__init__.py": "",
       "shop/price.py": "def with_tax(p, rate):\n    return p * rate\n",
       "shop/cart.py": "from shop.price import with_tax\n\ndef total(items, rate=0.2):\n"
                       "    return round(sum(with_tax(p, rate) for p in items), 2)\n",
       "test_cart.py": "from shop.cart import total\nassert total([10, 20]) == 36.0, total([10, 20])\nprint('ok')\n"},
      "test_cart.py fails. Find the root cause in the shop package and fix it. Do not change the test.",
      "from shop.cart import total; assert total([10,20])==36.0; assert total([100],0.1)==110.0; "
      "import pathlib; assert 'assert total([10, 20]) == 36.0' in pathlib.Path('test_cart.py').read_text()",
      {"shop/price.py": "def with_tax(p, rate):\n    return p * (1 + rate)\n"}),
    C("add-feature-with-test", "medium", "feature",
      {"textutil.py": "def words(s):\n    return s.split()\n"},
      "Add a function slugify(s) to textutil.py: lowercase, keep letters and digits, join words with '-'. "
      "Example: slugify('Hello, World 2!') == 'hello-world-2'. Then write test_textutil.py that tests it and run it.",
      "from textutil import slugify; assert slugify('Hello, World 2!')=='hello-world-2'; "
      "assert slugify('  A  b ')=='a-b'; import os; assert os.path.exists('test_textutil.py')",
      {"textutil.py": "import re\n\ndef words(s):\n    return s.split()\n\n"
                      "def slugify(s):\n    return '-'.join(re.findall(r'[a-z0-9]+', s.lower()))\n",
       "test_textutil.py": "from textutil import slugify\nassert slugify('Hello, World 2!') == 'hello-world-2'\n"}),
    C("rename-everywhere", "medium", "refactor",
      {"a.py": "def get_usr(i):\n    return {'id': i}\n",
       "b.py": "from a import get_usr\n\ndef show(i):\n    return get_usr(i)['id']\n",
       "c.py": "import a\n\nprint(a.get_usr(3))\n"},
      "Rename the function get_usr to get_user in every file. Keep behavior the same.",
      "import pathlib; t=''.join(p.read_text() for p in pathlib.Path('.').glob('*.py')); "
      "assert 'get_usr' not in t, 'old name left'; import b; assert b.show(5)==5",
      {"a.py": "def get_user(i):\n    return {'id': i}\n",
       "b.py": "from a import get_user\n\ndef show(i):\n    return get_user(i)['id']\n",
       "c.py": "import a\n\nprint(a.get_user(3))\n"}),
    C("fix-sql-injection", "medium", "security",
      {"db.py": "import sqlite3\n\ndef find(conn, name):\n"
                "    return conn.execute(f\"SELECT id FROM users WHERE name = '{name}'\").fetchall()\n"},
      "db.py has a SQL injection. Fix it with a parameterized query. Keep the function signature.",
      "import sqlite3, db; c=sqlite3.connect(':memory:'); c.execute('create table users(id, name)'); "
      "c.execute(\"insert into users values (1,'bob')\"); assert db.find(c,'bob')==[(1,)]; "
      "assert db.find(c,\"x' OR '1'='1\")==[]",
      {"db.py": "import sqlite3\n\ndef find(conn, name):\n"
                "    return conn.execute('SELECT id FROM users WHERE name = ?', (name,)).fetchall()\n"}),
    C("tests-red-to-green", "medium", "testfix",
      {"stats.py": "def median(xs):\n    xs = sorted(xs)\n    return xs[len(xs) // 2]\n",
       "test_stats.py": "from stats import median\nassert median([3, 1, 2]) == 2\n"
                        "assert median([4, 1, 3, 2]) == 2.5\nassert median([5]) == 5\nprint('ok')\n"},
      "Run `python test_stats.py`. Fix stats.py until it passes.",
      "from stats import median; assert median([4,1,3,2])==2.5 and median([3,1,2])==2 and median([1,2])==1.5",
      {"stats.py": "def median(xs):\n    xs = sorted(xs)\n    n = len(xs)\n    m = n // 2\n"
                   "    return xs[m] if n % 2 else (xs[m - 1] + xs[m]) / 2\n"}),
    C("summarize-notes", "medium", "writing",
      {"notes.txt": "Meeting 12 May. Present: Asha, Ravi, Lena.\nWe agreed the new budget is $4,000 for the pilot.\n"
                    "Ravi will set up the test server next week.\nThe deadline for the pilot report is June 30.\n"
                    "Lena raised a risk: the vendor API may change.\nCoffee machine is broken again.\n"},
      "Write summary.md with exactly 3 bullet points (lines starting with '- '). Each bullet max 15 words. "
      "Mention the budget and the deadline. Skip unimportant details.",
      WORDS + "L=[l for l in open('summary.md',encoding='utf-8').read().splitlines() if l.startswith('- ')]; "
      "assert len(L)==3, L; assert all(W(l) <= 16 for l in L), L; t=' '.join(L); "
      "assert '4,000' in t or '4000' in t; assert 'June 30' in t or '30 June' in t; assert 'offee' not in t",
      {"summary.md": "- Pilot budget agreed at $4,000.\n- Pilot report deadline is June 30.\n"
                     "- Risk: the vendor API may change.\n"}),
    C("csv-report", "medium", "data",
      {"sales.csv": "region,amount\nNorth,100\nSouth,50\nNorth,200\nEast,75\nSouth,25\n"},
      "Write report.py that reads sales.csv and prints the total amount per region, one line each, sorted by "
      "region name, in the form 'East: 75'.",
      "import subprocess,sys; o=subprocess.run([sys.executable,'report.py'],capture_output=True,text=True).stdout.split(); "
      "assert ' '.join(o)=='East: 75 North: 300 South: 75', o",
      {"report.py": "import csv\nt = {}\nfor r in csv.DictReader(open('sales.csv')):\n"
                    "    t[r['region']] = t.get(r['region'], 0) + int(r['amount'])\n"
                    "for k in sorted(t):\n    print(f'{k}: {t[k]}')\n"}),
    C("fix-xss", "medium", "security",
      {"render.py": "def comment_html(user, text):\n    return '<p><b>' + user + '</b>: ' + text + '</p>'\n"},
      "render.py builds HTML from user input and allows XSS. Escape user and text. Keep the same HTML shape.",
      "from render import comment_html as c; r=c('<i>a</i>','<script>x</script>'); assert '<script>' not in r and '<i>' not in r; "
      "assert c('bob','hi')=='<p><b>bob</b>: hi</p>'",
      {"render.py": "from html import escape\n\ndef comment_html(user, text):\n"
                    "    return '<p><b>' + escape(user) + '</b>: ' + escape(text) + '</p>'\n"}),
    C("add-cli-flag", "medium", "feature",
      {"app.py": "import argparse\n\np = argparse.ArgumentParser()\np.add_argument('nums', nargs='+', type=int)\n"
                 "a = p.parse_args()\nprint(sum(a.nums))\n"},
      "Add a --json flag to app.py. With --json it prints {\"sum\": N} as JSON. Without it, output stays the same.",
      "import subprocess,sys,json; r=lambda *a: subprocess.run([sys.executable,'app.py',*a],capture_output=True,text=True).stdout.strip(); "
      "assert r('1','2')=='3'; assert json.loads(r('--json','1','2'))=={'sum':3}",
      {"app.py": "import argparse, json\n\np = argparse.ArgumentParser()\np.add_argument('nums', nargs='+', type=int)\n"
                 "p.add_argument('--json', action='store_true')\na = p.parse_args()\n"
                 "print(json.dumps({'sum': sum(a.nums)}) if a.json else sum(a.nums))\n"}),
    C("fix-regex-validator", "medium", "fix",
      {"valid.py": "import re\n\ndef is_email(s):\n    return re.match(r'\\w+@\\w+', s) is not None\n"},
      "is_email in valid.py accepts bad input like 'a@b' and 'x@y.com junk', and rejects 'first.last@mail.co.uk'. "
      "Fix it so it needs a dot in the domain, allows dots in the name, and matches the whole string.",
      "from valid import is_email as e; assert e('first.last@mail.co.uk') and e('a@b.io'); "
      "assert not e('a@b') and not e('x@y.com junk') and not e('@b.com')",
      {"valid.py": "import re\n\ndef is_email(s):\n    return re.fullmatch(r'[\\w.+-]+@[\\w-]+(\\.[\\w-]+)+', s) is not None\n"}),

    # ------------------------------------------------------------------- HARD
    C("path-traversal", "hard", "security",
      {"files.py": "import os\n\nBASE = os.path.abspath('data')\n\ndef read(name):\n"
                   "    with open(os.path.join(BASE, name)) as f:\n        return f.read()\n",
       "data/hello.txt": "hi\n", "secret.txt": "TOP SECRET\n"},
      "files.read() allows path traversal (for example '../secret.txt'). Fix it: raise ValueError "
      "for any name that resolves outside BASE. Normal files must still work.",
      "import files; assert files.read('hello.txt')=='hi\\n'\n"
      "for bad in ('../secret.txt', '..\\\\secret.txt', 'a/../../secret.txt'):\n"
      "    try:\n        files.read(bad); raise SystemExit('traversal still works: '+bad)\n"
      "    except ValueError: pass\n    except (FileNotFoundError, OSError): pass",
      {"files.py": "import os\n\nBASE = os.path.abspath('data')\n\ndef read(name):\n"
                   "    p = os.path.abspath(os.path.join(BASE, name))\n"
                   "    if os.path.commonpath([p, BASE]) != BASE:\n        raise ValueError(name)\n"
                   "    with open(p) as f:\n        return f.read()\n"}),
    C("implement-lru", "hard", "feature",
      {"test_lru.py": "from lru import LRU\nc = LRU(2)\nc.put('a', 1); c.put('b', 2)\nassert c.get('a') == 1\n"
                      "c.put('c', 3)\nassert c.get('b') is None\nassert c.get('a') == 1 and c.get('c') == 3\n"
                      "c.put('a', 9)\nassert c.get('a') == 9 and len(c) == 2\nprint('ok')\n"},
      "Create lru.py with a class LRU(capacity): get(key) returns the value or None, put(key, value) stores it and "
      "evicts the least recently used key when full, len() returns the size. Make `python test_lru.py` pass.",
      "import subprocess,sys; r=subprocess.run([sys.executable,'test_lru.py'],capture_output=True,text=True); assert r.returncode==0, r.stderr[-300:]; "
      "from lru import LRU; c=LRU(1); c.put(1,1); c.put(2,2); assert c.get(1) is None and c.get(2)==2",
      {"lru.py": "from collections import OrderedDict\n\nclass LRU:\n    def __init__(self, capacity):\n"
                 "        self.cap = capacity\n        self.d = OrderedDict()\n\n    def get(self, k):\n"
                 "        if k not in self.d:\n            return None\n        self.d.move_to_end(k)\n        return self.d[k]\n\n"
                 "    def put(self, k, v):\n        self.d[k] = v\n        self.d.move_to_end(k)\n"
                 "        if len(self.d) > self.cap:\n            self.d.popitem(last=False)\n\n"
                 "    def __len__(self):\n        return len(self.d)\n"}),
    C("bank-invariant", "hard", "fix",
      {"bank.py": "class Account:\n    def __init__(self, balance=0):\n        self.balance = balance\n\n"
                  "    def withdraw(self, amount):\n        self.balance -= amount\n        return self.balance\n\n"
                  "    def deposit(self, amount):\n        self.balance += amount\n        return self.balance\n"},
      "bank.py lets the balance go negative and accepts negative amounts. Add an exception class InsufficientFunds. "
      "withdraw must raise it when amount > balance. Both methods must raise ValueError for amounts <= 0.",
      "import bank; a=bank.Account(10); assert a.withdraw(4)==6 and a.deposit(1)==7\n"
      "for f,arg,exc in ((a.withdraw,100,bank.InsufficientFunds),(a.withdraw,-1,ValueError),(a.deposit,0,ValueError)):\n"
      "    try:\n        f(arg); raise SystemExit('no error for %r' % arg)\n    except exc: pass\n"
      "assert a.balance==7",
      {"bank.py": "class InsufficientFunds(Exception):\n    pass\n\n\nclass Account:\n"
                  "    def __init__(self, balance=0):\n        self.balance = balance\n\n"
                  "    def withdraw(self, amount):\n        if amount <= 0:\n            raise ValueError(amount)\n"
                  "        if amount > self.balance:\n            raise InsufficientFunds(amount)\n"
                  "        self.balance -= amount\n        return self.balance\n\n"
                  "    def deposit(self, amount):\n        if amount <= 0:\n            raise ValueError(amount)\n"
                  "        self.balance += amount\n        return self.balance\n"}),
    C("command-injection", "hard", "security",
      {"net.py": "import os\n\ndef ping(host):\n    return os.system(f'ping -c 1 {host}')\n"},
      "net.py has a command injection. Rewrite ping(host) to validate host (only letters, digits, dots, hyphens; "
      "else raise ValueError) and call subprocess.run with a list of arguments, no shell. Return the exit code.",
      "import ast,net; t=open('net.py').read(); assert 'os.system' not in t and 'shell=True' not in t; "
      "assert 'subprocess' in t\nfor bad in ('8.8.8.8; rm -rf /','a&&b','$(id)','x y'):\n"
      "    try:\n        net.ping(bad); raise SystemExit('accepted '+bad)\n    except ValueError: pass",
      {"net.py": "import re, subprocess\n\ndef ping(host):\n    if not re.fullmatch(r'[A-Za-z0-9.-]+', host):\n"
                 "        raise ValueError(host)\n    return subprocess.run(['ping', '-c', '1', host]).returncode\n"}),
    C("multi-bug-testfix", "hard", "testfix",
      {"inventory.py": "class Inventory:\n    def __init__(self):\n        self.items = {}\n\n"
                       "    def add(self, name, qty):\n        self.items[name] = qty\n\n"
                       "    def remove(self, name, qty):\n        self.items[name] -= qty\n\n"
                       "    def total(self):\n        return len(self.items)\n",
       "test_inventory.py": "from inventory import Inventory\ni = Inventory()\ni.add('pen', 2)\ni.add('pen', 3)\n"
                            "assert i.items['pen'] == 5, i.items\ni.add('ink', 1)\nassert i.total() == 6\n"
                            "i.remove('ink', 1)\nassert 'ink' not in i.items\ntry:\n    i.remove('pen', 99)\n"
                            "    raise SystemExit('should fail')\nexcept ValueError:\n    pass\nassert i.items['pen'] == 5\nprint('ok')\n"},
      "Run `python test_inventory.py`. inventory.py has several bugs. Fix all of them until the test passes. "
      "Do not change the test.",
      "import subprocess,sys; r=subprocess.run([sys.executable,'test_inventory.py'],capture_output=True,text=True); "
      "assert r.returncode==0, r.stderr[-300:]; assert \"i.remove('pen', 99)\" in open('test_inventory.py').read()",
      {"inventory.py": "class Inventory:\n    def __init__(self):\n        self.items = {}\n\n"
                       "    def add(self, name, qty):\n        self.items[name] = self.items.get(name, 0) + qty\n\n"
                       "    def remove(self, name, qty):\n        if self.items.get(name, 0) < qty:\n"
                       "            raise ValueError(name)\n        self.items[name] -= qty\n"
                       "        if self.items[name] == 0:\n            del self.items[name]\n\n"
                       "    def total(self):\n        return sum(self.items.values())\n"}),
    C("parse-access-log", "hard", "data",
      {"access.log": '1.1.1.1 - - [10/Oct/2026:13:55:36] "GET /a HTTP/1.1" 200 512\n'
                     '2.2.2.2 - - [10/Oct/2026:13:55:37] "POST /login HTTP/1.1" 401 12\n'
                     '1.1.1.1 - - [10/Oct/2026:13:55:38] "GET /b HTTP/1.1" 200 100\n'
                     'garbage line\n'
                     '3.3.3.3 - - [10/Oct/2026:13:55:39] "GET /c HTTP/1.1" 500 0\n'},
      "Write logstats.py with a function stats(path) that returns a dict with: 'status' (dict of status code int -> "
      "count), 'top_ip' (the IP with the most requests), 'bytes' (sum of response sizes). Skip lines that do not parse.",
      "from logstats import stats; s=stats('access.log'); assert s['status']=={200:2,401:1,500:1}, s; "
      "assert s['top_ip']=='1.1.1.1' and s['bytes']==624, s",
      {"logstats.py": "import re\nfrom collections import Counter\n\nRX = re.compile(r'^(\\S+) .*\" (\\d{3}) (\\d+)$')\n\n"
                      "def stats(path):\n    st, ips, b = Counter(), Counter(), 0\n    for ln in open(path):\n"
                      "        m = RX.match(ln.strip())\n        if not m:\n            continue\n"
                      "        ips[m.group(1)] += 1\n        st[int(m.group(2))] += 1\n        b += int(m.group(3))\n"
                      "    return {'status': dict(st), 'top_ip': ips.most_common(1)[0][0], 'bytes': b}\n"}),
    C("recursion-to-iteration", "hard", "refactor",
      {"seq.py": "def total(n):\n    if n == 0:\n        return 0\n    return n + total(n - 1)\n"},
      "total(n) in seq.py fails with RecursionError for n = 100000. Rewrite it without recursion. Same results.",
      "import ast,seq; assert seq.total(0)==0 and seq.total(10)==55 and seq.total(100000)==5000050000; "
      "t=ast.parse(open('seq.py').read()); f=[x for x in ast.walk(t) if isinstance(x,ast.Call) and getattr(x.func,'id','')=='total']; assert not f, 'still recursive'",
      {"seq.py": "def total(n):\n    return n * (n + 1) // 2\n"}),
    C("unsafe-deserialization", "hard", "security",
      {"store.py": "import pickle\n\ndef save(path, data):\n    with open(path, 'wb') as f:\n        pickle.dump(data, f)\n\n"
                   "def load(path):\n    with open(path, 'rb') as f:\n        return pickle.load(f)\n"},
      "store.py uses pickle, which runs code from untrusted files. Switch save/load to JSON. Keep the same "
      "function names. A dict with strings, numbers and lists must round-trip.",
      "import store; d={'a':[1,2],'b':'x','c':1.5}; store.save('t.dat',d); assert store.load('t.dat')==d; "
      "assert 'pickle' not in open('store.py').read()",
      {"store.py": "import json\n\ndef save(path, data):\n    with open(path, 'w') as f:\n        json.dump(data, f)\n\n"
                   "def load(path):\n    with open(path) as f:\n        return json.load(f)\n"}),
    C("write-api-docs", "hard", "writing",
      {"lib.py": "def area(w, h):\n    return w * h\n\n\ndef perimeter(w, h):\n    return 2 * (w + h)\n\n\n"
                 "def _helper():\n    pass\n\n\ndef scale(w, h, k):\n    return w * k, h * k\n"},
      "Write API.md that documents every public function in lib.py (skip names that start with '_'). For each: "
      "a '## name' heading, one sentence, and one ```python example block.",
      "t=open('API.md',encoding='utf-8').read(); import re; H=re.findall(r'^## +`?(\\w+)', t, re.M); "
      "assert sorted(H)==['area','perimeter','scale'], H; assert t.count('```python')>=3; assert '_helper' not in t",
      {"API.md": "## area\nReturns w times h.\n```python\narea(2, 3)\n```\n## perimeter\nReturns the perimeter.\n"
                 "```python\nperimeter(2, 3)\n```\n## scale\nScales both sides by k.\n```python\nscale(2, 3, 2)\n```\n"}),
    C("find-dead-code", "hard", "qa",
      {"app/__init__.py": "",
       "app/main.py": "from app.util import load, save\nfrom app import fmt\n\ndef run():\n    save(load())\n"
                      "    print(fmt.pretty({}))\n",
       "app/util.py": "def load():\n    return {}\n\ndef save(d):\n    pass\n\ndef migrate_v1(d):\n    return d\n",
       "app/fmt.py": "def pretty(d):\n    return str(d)\n"},
      "Which function in the app package is defined but never called anywhere? Answer with its name only.",
      WORDS + "assert 'migrate_v1' in A and W(A) <= 12, A", answer="migrate_v1"),
]

BY_NAME = {c.name: c for c in CHALLENGES}
