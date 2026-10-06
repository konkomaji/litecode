import json, sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import FakeServer, TempProject, yes, no
from litecode import agent, config, learn, mcp, router, scan, setup, skills, tools, ui
from litecode.memory import Memory, ContextBuilder


class TestParse(unittest.TestCase):
    def test_plain(self):
        a = agent._parse_action('{"tool":"read_file","args":{"path":"a.py"}}')
        self.assertEqual(a["tool"], "read_file")

    def test_prose_and_fence(self):
        a = agent._parse_action('Sure.\n```json\n{"tool":"final","args":{"message":"hi"}}\n```')
        self.assertEqual(a["args"]["message"], "hi")

    def test_brace_inside_string(self):
        a = agent._parse_action('{"tool":"write_file","args":{"path":"x","content":"def f(): return {1: \'}\'}"}} trailing')
        self.assertEqual(a["args"]["path"], "x")
        self.assertIn("}", a["args"]["content"])

    def test_think_block_removed(self):
        a = agent._parse_action('<think>{"tool":"bad"}</think>{"tool":"final","args":{}}')
        self.assertEqual(a["tool"], "final")

    def test_garbage(self):
        self.assertIsNone(agent._parse_action("no json here"))
        self.assertIsNone(agent._parse_action('{"x":1}'))


class TestTools(unittest.TestCase):
    def test_sandbox(self):
        with TempProject() as tp:
            t = tools.Tools(tp.root, yes)
            self.assertIn("escapes", t.call("read_file", {"path": "../../etc/passwd"}))

    def test_edit_and_checkpoint(self):
        with TempProject() as tp:
            (tp.root / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
            mem = Memory(tp.root, tp.cfg)
            t = tools.Tools(tp.root, yes, memory=mem)
            self.assertIn("edited", t.call("edit_file", {"path": "a.py", "find": "x = 1", "replace": "x = 10"}))
            self.assertEqual((tp.root / "a.py").read_text(), "x = 10\ny = 2\n")
            self.assertEqual(mem.pop_checkpoint("a.py"), "x = 1\ny = 2\n")
            self.assertIn("not found", t.call("edit_file", {"path": "a.py", "find": "zzz", "replace": ""}))

    def test_edit_ambiguous(self):
        with TempProject() as tp:
            (tp.root / "a.py").write_text("a\na\n", encoding="utf-8")
            t = tools.Tools(tp.root, yes)
            self.assertIn("2 places", t.call("edit_file", {"path": "a.py", "find": "a", "replace": "b"}))

    def test_readonly_and_denied(self):
        with TempProject() as tp:
            t = tools.Tools(tp.root, yes, mode="readonly")
            self.assertIn("read-only", t.call("write_file", {"path": "n.txt", "content": "x"}))
            self.assertFalse((tp.root / "n.txt").exists())
            t2 = tools.Tools(tp.root, no)
            self.assertIn("denied", t2.call("write_file", {"path": "n.txt", "content": "x"}))

    def test_read_range_glob_grep(self):
        with TempProject() as tp:
            (tp.root / "src").mkdir()
            (tp.root / "src" / "m.py").write_text("\n".join(f"line{i}" for i in range(1, 21)), encoding="utf-8")
            t = tools.Tools(tp.root, yes)
            out = t.call("read_file", {"path": "src/m.py", "start": 5, "end": 6})
            self.assertEqual(out, "5\tline5\n6\tline6")
            self.assertIn("src/m.py", t.call("glob", {"pattern": "**/*.py"}))
            self.assertIn("src/m.py:7:", t.call("grep", {"pattern": "line7$"}))
            self.assertIn("missing arg", t.call("read_file", {}))
            self.assertIn("unknown tool", t.call("nope", {}))

    def test_run(self):
        with TempProject() as tp:
            t = tools.Tools(tp.root, yes)
            out = t.call("run", {"cmd": f'"{sys.executable}" -c "print(42)"'})
            self.assertIn("(exit 0)", out)
            self.assertIn("42", out)


class TestScan(unittest.TestCase):
    def test_builtin_rules(self):
        with TempProject() as tp:
            (tp.root / "app.py").write_text(
                "import os, pickle, subprocess\n"
                "def q(c, u):\n    c.execute(f\"SELECT * FROM t WHERE u='{u}'\")\n"
                "def r(d):\n    return pickle.loads(d)\n"
                "subprocess.run(cmd, shell=True)\n"
                "API_KEY = 'sk_live_123456789'\n"
                "# eval(x) in a comment is ignored\n", encoding="utf-8")
            (tp.root / "ui.js").write_text("el.innerHTML = userInput;\n", encoding="utf-8")
            fs = scan.builtin_scan(tp.root, tp.root)
            rules = {f.rule for f in fs}
            for r in ("py-sql-format", "py-pickle", "py-shell-true", "any-hardcoded-secret", "js-innerhtml"):
                self.assertIn(r, rules)
            self.assertNotIn("py-eval", rules)
            self.assertEqual(scan.scan(tp.root)[0].severity, "high")
            self.assertIn("app.py", scan.context_for(tp.root, fs[0]) + fs[0].file)

    def test_clean(self):
        with TempProject() as tp:
            (tp.root / "ok.py").write_text("print('hi')\n", encoding="utf-8")
            self.assertEqual(scan.report(scan.builtin_scan(tp.root, tp.root)), "(no findings)")


class TestMemory(unittest.TestCase):
    def test_facts_profile_dedupe(self):
        with TempProject() as tp:
            m = Memory(tp.root, tp.cfg)
            self.assertTrue(m.remember("tests: pytest -q"))
            self.assertIsNone(m.remember("TESTS: pytest -q"))
            self.assertTrue(m.prefer("always use type hints"))
            self.assertIsNone(m.prefer("Always use type hints"))
            self.assertEqual(len(m.facts()), 1)
            # profile is global: visible from another project
            other = tp.tmp / "other"
            other.mkdir()
            self.assertEqual(Memory(other, tp.cfg).profile()[0]["text"], "always use type hints")

    def test_central_location(self):
        with TempProject() as tp:
            tp.cfg["project_memory"] = "central"
            m = Memory(tp.root, tp.cfg)
            self.assertFalse((tp.root / ".litecode").exists())
            self.assertIn("projects", str(m.dir))

    def test_examples_retrieval(self):
        with TempProject() as tp:
            m = Memory(tp.root, tp.cfg)
            m.add_example("add a json flag to the cli parser", "added --json in cli.py", ok=True)
            m.add_example("fix the login bug", "fixed auth", ok=False)
            got = m.similar_examples("add a --json flag to cli parser please")
            self.assertEqual(len(got), 1)
            self.assertEqual(m.similar_examples("fix the login bug"), [])   # rated bad: never reused
            self.assertTrue(m.rate_last_example(True))

    def test_compaction_keeps_history(self):
        with TempProject() as tp:
            m = Memory(tp.root, tp.cfg)
            sid = m.new_session()
            for i in range(30):
                m.append_turn(sid, "user" if i % 2 == 0 else "assistant", f"turn {i} " + "x" * 200)
            cb = ContextBuilder(m, budget_chars=1000, keep_recent=4)
            msgs = cb.build(sid, "SYS", "new task")
            self.assertTrue(m.summary(sid))
            self.assertEqual(len(m.turns(sid)), 4)
            self.assertTrue((m.dir / "sessions" / f"{sid}.full.jsonl.bak").exists())
            self.assertEqual(msgs[0]["role"], "system")
            self.assertIn("new task", msgs[-1]["content"])
            roles = [x["role"] for x in msgs[1:]]
            self.assertTrue(all(a != b for a, b in zip(roles, roles[1:])), roles)


class TestLearn(unittest.TestCase):
    def test_preferences(self):
        got = learn.capture_preferences("Always use type hints. Fix the bug in main.py. Don't add comments.")
        self.assertEqual(got, ["Always use type hints", "Don't add comments"])
        self.assertEqual(learn.capture_preferences("should I always use tabs?"), [])

    def test_extract_and_export(self):
        with TempProject() as tp:
            m = Memory(tp.root, tp.cfg)
            sid = m.new_session()
            m.append_turn(sid, "user", "run tests")
            srv = FakeServer(['{"facts": ["tests run with pytest -q", "x"]}'])
            self.assertEqual(learn.end_of_session(srv, m, sid), ["tests run with pytest -q"])
            m.add_example("t1", "a1", ok=True)
            m.add_example("t2", "a2")
            out = tp.tmp / "ds.jsonl"
            self.assertEqual(learn.export_dataset(m, out), 1)
            self.assertEqual(learn.export_dataset(m, out, include_unrated=True), 2)
            row = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(row["messages"][1]["content"], "t1")


class TestSkills(unittest.TestCase):
    def test_builtin_create_match_remove(self):
        with TempProject() as tp:
            sk = skills.Skills(tp.root, tp.cfg["data_dir"])
            self.assertIn("review", [s.name for s in sk.list()])
            p = sk.create("django-tests", "Run django tests", "1. run manage.py test",
                          ["django"], scope="project")
            self.assertTrue(p.exists())
            self.assertEqual(sk.match("my django app is broken")[0].name, "django-tests")
            self.assertIn("Follow these steps", sk.get("/django-tests").prompt())
            self.assertFalse(sk.remove("review"))
            self.assertTrue(sk.remove("django-tests"))
            with self.assertRaises(ValueError):
                sk.create("Bad Name!", "", "")

    def test_parse_and_draft(self):
        text = "---\nname: lint\ndescription: Lint code\ntriggers: lint, flake8\n---\n1. run flake8\n"
        s = skills.parse(text)
        self.assertEqual(s.triggers, ["lint", "flake8"])
        self.assertEqual(skills.parse(skills.render(s)).body.strip(), "1. run flake8")
        srv = FakeServer(["```\n" + text + "```"])
        self.assertEqual(skills.draft_with_model(srv, "a lint skill").name, "lint")


class TestMCP(unittest.TestCase):
    def test_stdio_roundtrip(self):
        with TempProject() as tp:
            fake = str(Path(__file__).with_name("fake_mcp_server.py"))
            mcp.save_server(tp.root / ".mcp.json", "calc", {"command": sys.executable, "args": [fake]})
            hub = mcp.Hub(tp.root, Path(tp.cfg["data_dir"]))
            hub.start()
            try:
                self.assertEqual(hub.tool_names(), ["mcp__calc__add"])
                self.assertIn("a, b", hub.spec_text())
                t = tools.Tools(tp.root, yes, mcp=hub)
                self.assertEqual(t.call("mcp__calc__add", {"a": 2, "b": 3}), "5")
            finally:
                hub.stop()

    def test_bad_server(self):
        with TempProject() as tp:
            mcp.save_server(tp.root / ".mcp.json", "bad", {"command": "definitely-not-a-cmd-xyz"})
            errs = []
            hub = mcp.Hub(tp.root, Path(tp.cfg["data_dir"]), on_error=errs.append)
            hub.start()
            self.assertEqual(hub.tool_names(), [])
            self.assertTrue(errs)


class TestAgent(unittest.TestCase):
    def test_edit_flow_with_stream(self):
        with TempProject() as tp:
            (tp.root / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
            srv = FakeServer([
                {"thought": "look", "tool": "read_file", "args": {"path": "calc.py"}},
                {"tool": "edit_file", "args": {"path": "calc.py", "find": "a - b", "replace": "a + b"}},
                {"tool": "final", "args": {"message": "Fixed add() in calc.py line 2."}},
            ])
            events = []
            a = agent.Agent(srv, tp.root, yes, cfg=tp.cfg, on_event=lambda k, d: events.append((k, d)))
            out = a.run("fix add in @calc.py. Always use type hints.")
            self.assertEqual(out, "Fixed add() in calc.py line 2.")
            self.assertIn("a + b", (tp.root / "calc.py").read_text())
            streamed = "".join(d for k, d in events if k == "stream")
            self.assertEqual(streamed, out)
            self.assertIn(("learned", "Always use type hints"), events)
            self.assertIn("def add", srv.calls[0][-1]["content"])          # @mention attached
            self.assertIn("ASD-STE100", srv.calls[0][0]["content"])         # answer rules loaded
            ex = a.mem.similar_examples("fix add in calc.py")
            self.assertEqual(ex[0]["files"], ["calc.py"])

    def test_repeat_guard_and_prose_fallback(self):
        with TempProject() as tp:
            srv = FakeServer([{"tool": "list_dir", "args": {}}, {"tool": "list_dir", "args": {}},
                              "just prose", "The answer is 4."])
            a = agent.Agent(srv, tp.root, yes, cfg=tp.cfg)
            self.assertEqual(a.run("what is 2+2"), "The answer is 4.")
            self.assertIn("already ran", srv.calls[2][-1]["content"])

    def test_trim_keeps_prefix(self):
        with TempProject() as tp:
            replies = [{"tool": "read_file", "args": {"path": f"f{i}"}} for i in range(20)]
            srv = FakeServer(replies)
            a = agent.Agent(srv, tp.root, yes, cfg=tp.cfg, max_steps=20)
            a.run("the original task")
            last = srv.calls[-1]
            self.assertEqual(last[0]["role"], "system")
            self.assertTrue(any("the original task" in m["content"] for m in last[:3]))
            self.assertLessEqual(len(last), 2 + 16)

    def test_plan_is_readonly(self):
        with TempProject() as tp:
            srv = FakeServer([{"tool": "write_file", "args": {"path": "x.txt", "content": "x"}},
                              {"tool": "final", "args": {"message": "1. step"}}])
            a = agent.Agent(srv, tp.root, yes, cfg=tp.cfg)
            self.assertEqual(a.plan("do it"), "1. step")
            self.assertFalse((tp.root / "x.txt").exists())
            self.assertEqual(a.tools.mode, "ask")

    def test_review(self):
        with TempProject() as tp:
            (tp.root / "a.py").write_text("import pickle\nx = pickle.loads(data)\n", encoding="utf-8")
            srv = FakeServer(["VERDICT: real\nSEVERITY: high\nWHY: untrusted pickle\nFIX: use json"])
            a = agent.Agent(srv, tp.root, yes, cfg=tp.cfg)
            rep = a.review(".")
            self.assertIn("VERDICT: real", rep)
            self.assertTrue(list((a.mem.dir / "reviews").glob("*.md")))

    def test_testfix(self):
        with TempProject() as tp:
            (tp.root / "t.py").write_text("assert 1 == 2\n", encoding="utf-8")
            srv = FakeServer([{"tool": "edit_file", "args": {"path": "t.py", "find": "1 == 2", "replace": "1 == 1"}},
                              {"tool": "final", "args": {"message": "fixed"}}])
            a = agent.Agent(srv, tp.root, yes, cfg=tp.cfg)
            out = a.testfix(f'"{sys.executable}" t.py')
            self.assertIn("pass after 1", out)


class TestAutoCapture(unittest.TestCase):
    def test_passing_test_command_is_remembered(self):
        with TempProject() as tp:
            (tp.root / "test_x.py").write_text("print('ok')\n", encoding="utf-8")
            cmd = f'"{sys.executable}" test_x.py'
            srv = FakeServer([{"tool": "run", "args": {"cmd": cmd}},
                              {"tool": "final", "args": {"message": "ok"}}])
            a = agent.Agent(srv, tp.root, yes, cfg=tp.cfg)
            a.run("run the tests")
            self.assertIn(cmd, a.mem.facts()[0]["text"])

    def test_bash_is_not_wsl_stub(self):
        b = tools.bash_path()
        if b:
            self.assertNotIn("system32", b.lower())


class TestUI(unittest.TestCase):
    def test_field_streamer(self):
        got = []
        fs = ui.FieldStreamer(got.append)
        text = '{"thought":"x","tool":"final","args":{"message":"line1\\nsaid \\"hi\\" \\u00e9"}}'
        for ch in text:
            fs.feed(ch)
        self.assertEqual("".join(got), 'line1\nsaid "hi" \u00e9')

    def test_streamer_ignores_non_final(self):
        got = []
        fs = ui.FieldStreamer(got.append)
        fs.feed('{"tool":"write_file","args":{"path":"a","message":"no"}}')
        self.assertEqual(got, [])


class TestConfigRouterSetup(unittest.TestCase):
    def test_config_save_roundtrip(self):
        import tempfile
        old = config.HOME
        try:
            config.HOME = Path(tempfile.mkdtemp())
            config.save({"threads": 3, "data_dir": "D:\\x\\y", "roles": {"code": "m.gguf"}, "kv_persist": False})
            config.save({"spec_tuned": {"code": "ngram-simple"}})
            c = config.load()
            self.assertEqual(c["threads"], 3)
            self.assertEqual(c["data_dir"], "D:/x/y")
            self.assertEqual(c["roles"]["code"], "m.gguf")
            self.assertEqual(c["roles"]["fim"], config.DEFAULTS["roles"]["fim"])  # defaults not mutated
            self.assertFalse(c["kv_persist"])
            self.assertEqual(c["spec_tuned"]["code"], "ngram-simple")
        finally:
            config.HOME = old

    def test_router(self):
        avail = {"code", "security", "quality"}
        self.assertEqual(router.route("find the sql injection vuln", avail)["role"], "security")
        self.assertEqual(router.route("rename a variable", avail)["role"], "code")
        self.assertEqual(router.route("find the xss", {"code"})["role"], "code")

    def test_engine_asset_pick(self):
        assets = [{"name": n} for n in ("llama-b1-bin-win-cpu-x64.zip", "llama-b1-bin-win-vulkan-x64.zip",
                                         "cudart-llama-bin-win-cuda-12.4-x64.zip", "llama-b1-bin-ubuntu-x64.tar.gz",
                                         "llama-b1-bin-macos-arm64.tar.gz")]
        self.assertEqual(setup.pick_engine_asset(assets, "Windows", "AMD64")["name"], "llama-b1-bin-win-cpu-x64.zip")
        self.assertEqual(setup.pick_engine_asset(assets, "Windows", "AMD64", "vulkan")["name"],
                         "llama-b1-bin-win-vulkan-x64.zip")
        self.assertEqual(setup.pick_engine_asset(assets, "Linux", "x86_64")["name"], "llama-b1-bin-ubuntu-x64.tar.gz")
        self.assertEqual(setup.pick_engine_asset(assets, "Darwin", "arm64")["name"], "llama-b1-bin-macos-arm64.tar.gz")
        assets.append({"name": "llama-b1-bin-win-cuda-12.4-x64.zip"})
        self.assertEqual(setup.pick_engine_asset(assets, "Windows", "AMD64", "cuda")["name"], "llama-b1-bin-win-cuda-12.4-x64.zip")
        self.assertEqual(setup.cuda_runtime_asset(assets)["name"], "cudart-llama-bin-win-cuda-12.4-x64.zip")


class TestCLI(unittest.TestCase):
    def test_undo_outside_project_refused(self):
        from litecode import cli
        import io, contextlib, os
        with TempProject() as tp:
            cwd = os.getcwd()
            os.chdir(tp.root)
            try:
                s = cli.Session(tp.cfg)
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    cli.slash("/undo ../../evil.txt", s)
                    cli.slash("/remember build with make", s)
                    cli.slash("/memory", s)
                self.assertIn("refused", buf.getvalue())
                self.assertIn("build with make", buf.getvalue())
                self.assertFalse(cli.slash("/exit", s))
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
