"""Edge cases: encodings, line endings, large files, bad config, resume, MCP refusal, compaction."""
import io, contextlib, json, os, sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import FakeServer, TempProject, yes
from litecode import agent, cli, config, mcp, tools, scan, skills
from litecode.memory import Memory, ContextBuilder


class TestFiles(unittest.TestCase):
    def test_unicode_and_crlf_edit(self):
        with TempProject() as tp:
            p = tp.root / "u.py"
            p.write_bytes("name = 'café'\r\nx = 1\r\n".encode("utf-8"))
            t = tools.Tools(tp.root, yes)
            self.assertIn("café", t.call("read_file", {"path": "u.py"}))
            out = t.call("edit_file", {"path": "u.py", "find": "x = 1", "replace": "x = 2"})
            self.assertIn("edited", out)
            self.assertIn("x = 2", p.read_text(encoding="utf-8"))

    def test_binary_and_large_file(self):
        with TempProject() as tp:
            (tp.root / "b.bin").write_bytes(bytes(range(256)) * 10)
            (tp.root / "big.txt").write_text("y" * 200 + "\n" * 1 + ("line\n" * 20000), encoding="utf-8")
            t = tools.Tools(tp.root, yes)
            self.assertIsInstance(t.call("read_file", {"path": "b.bin"}), str)
            out = t.call("read_file", {"path": "big.txt"})
            self.assertIn("truncated", out)
            self.assertLess(len(out), 41000)

    def test_write_creates_dirs_and_rejects_escape(self):
        with TempProject() as tp:
            t = tools.Tools(tp.root, yes)
            self.assertIn("wrote", t.call("write_file", {"path": "a/b/c.txt", "content": "hi"}))
            self.assertIn("escapes", t.call("write_file", {"path": "../out.txt", "content": "x"}))
            self.assertFalse((tp.tmp / "out.txt").exists())

    def test_bad_regex_falls_back_to_literal(self):
        with TempProject() as tp:
            (tp.root / "a.txt").write_text("call f(x\n", encoding="utf-8")
            t = tools.Tools(tp.root, yes)
            self.assertIn("a.txt:1", t.call("grep", {"pattern": "f(x"}))

    def test_args_not_dict(self):
        with TempProject() as tp:
            self.assertIn("JSON object", tools.Tools(tp.root, yes).call("read_file", ["x"]))


class TestAgentEdges(unittest.TestCase):
    def test_step_budget(self):
        with TempProject() as tp:
            srv = FakeServer([{"tool": "list_dir", "args": {"path": str(i)}} for i in range(5)])
            a = agent.Agent(srv, tp.root, yes, cfg=tp.cfg, max_steps=3)
            self.assertIn("budget", a.run("loop forever"))

    def test_mention_outside_root_ignored(self):
        with TempProject() as tp:
            (tp.tmp / "secret.txt").write_text("TOP", encoding="utf-8")
            text, added = agent.expand_mentions("read @../secret.txt", tp.root)
            self.assertEqual(added, [])
            self.assertNotIn("TOP", text)

    def test_resume_session_keeps_history(self):
        with TempProject() as tp:
            srv = FakeServer([{"tool": "final", "args": {"message": "first answer"}},
                              {"tool": "final", "args": {"message": "second"}}])
            a = agent.Agent(srv, tp.root, yes, cfg=tp.cfg)
            a.run("task one")
            b = agent.Agent(srv, tp.root, yes, cfg=tp.cfg, session=a.session)
            b.run("task two")
            joined = json.dumps(srv.calls[-1])
            self.assertIn("task one", joined)
            self.assertIn("first answer", joined)

    def test_model_summary_used_on_compaction(self):
        with TempProject() as tp:
            m = Memory(tp.root, tp.cfg)
            sid = m.new_session()
            for i in range(20):
                m.append_turn(sid, "user" if i % 2 == 0 else "assistant", "z" * 300)
            cb = ContextBuilder(m, budget_chars=500, keep_recent=2, summarize=lambda turns: "SUMMARY-X")
            msgs = cb.build(sid, "SYS", "t")
            self.assertIn("SUMMARY-X", json.dumps(msgs))

    def test_system_override(self):
        with TempProject() as tp:
            d = Path(tp.cfg["data_dir"])
            d.mkdir(parents=True, exist_ok=True)
            (d / "SYSTEM.md").write_text("CUSTOM RULES {spec}", encoding="utf-8")
            srv = FakeServer([{"tool": "final", "args": {"message": "ok"}}])
            agent.Agent(srv, tp.root, yes, cfg=tp.cfg).run("hi")
            self.assertTrue(srv.calls[0][0]["content"].startswith("CUSTOM RULES"))
            self.assertIn("read_file", srv.calls[0][0]["content"])


class TestMCPModes(unittest.TestCase):
    def test_readonly_refuses_mcp(self):
        class Hub:
            def has(self, n): return n == "mcp__x__y"
            def call(self, n, a): return "CALLED"
        with TempProject() as tp:
            t = tools.Tools(tp.root, yes, mode="readonly", mcp=Hub())
            self.assertEqual(t.call("mcp__x__y", {}), "(denied)")
            t.mode = "auto"
            self.assertEqual(t.call("mcp__x__y", {}), "CALLED")

    def test_disabled_server_skipped(self):
        with TempProject() as tp:
            mcp.save_server(tp.root / ".mcp.json", "off", {"command": "x", "disabled": True})
            self.assertEqual(mcp.load_config(tp.root, Path(tp.cfg["data_dir"])), {})


class TestConfigEdges(unittest.TestCase):
    def test_bad_toml_ignored(self):
        import tempfile
        old = config.HOME
        try:
            config.HOME = Path(tempfile.mkdtemp())
            (config.HOME / "config.toml").write_text("this is [[[ not toml", encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                c = config.load()
            self.assertEqual(c["port"], config.DEFAULTS["port"])
        finally:
            config.HOME = old


class TestCLIEdges(unittest.TestCase):
    def _run(self, tp, cmds):
        cwd = os.getcwd()
        os.chdir(tp.root)
        try:
            s = cli.Session(tp.cfg)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                for c in cmds:
                    cli.slash(c, s)
            return buf.getvalue(), s
        finally:
            os.chdir(cwd)

    def test_undo_stack(self):
        with TempProject() as tp:
            f = tp.root / "a.txt"
            f.write_text("v1", encoding="utf-8")
            m = Memory(tp.root, tp.cfg)
            t = tools.Tools(tp.root, yes, memory=m)
            t.write_file("a.txt", "v2")
            t.write_file("a.txt", "v3")
            out, _ = self._run(tp, ["/undo a.txt"])
            self.assertEqual(f.read_text(), "v2")
            self._run(tp, ["/undo a.txt"])
            self.assertEqual(f.read_text(), "v1")
            out, _ = self._run(tp, ["/undo a.txt"])
            self.assertIn("no checkpoint", out)

    def test_mode_and_config_and_skill_rm_builtin(self):
        with TempProject() as tp:
            out, s = self._run(tp, ["/mode readonly", "/skill rm review", "/sessions", "/cost"])
            self.assertEqual(s.mode, "readonly")
            self.assertIn("cannot be removed", out)
            self.assertIn("no model calls", out)

    def test_test_cmd_detection(self):
        with TempProject() as tp:
            m = Memory(tp.root, tp.cfg)
            self.assertEqual(cli._test_cmd(tp.root, m), "")
            (tp.root / "package.json").write_text("{}", encoding="utf-8")
            self.assertEqual(cli._test_cmd(tp.root, m), "npm test")
            (tp.root / "LITECODE.md").write_text("## Commands\n- test: make check\n", encoding="utf-8")
            self.assertEqual(cli._test_cmd(tp.root, m), "make check")


class TestHardwareTiers(unittest.TestCase):
    def test_vram_unlocks_big_models(self):
        from litecode import doctor, catalog
        e = doctor.Env("Linux", "cpu", 8, 16, ["avx2"], 16.0, 10.0, gpus=["NVIDIA GeForce RTX 3090, 24576 MiB"])
        self.assertAlmostEqual(e.vram_gb, 24.0)
        rec = catalog.recommend(e.model_budget_gb, has_gpu=e.vram_gb >= 6)
        self.assertEqual(rec["code"].key, "qwen3.6-35b-a3b")
        small = doctor.Env("Windows", "cpu", 4, 4, [], 4.0, 2.0)
        self.assertEqual(catalog.recommend(small.model_budget_gb)["code"].key, "qwen-coder-1.5b")


class TestScanEdges(unittest.TestCase):
    def test_skips_vendor_dirs(self):
        with TempProject() as tp:
            (tp.root / "node_modules").mkdir()
            (tp.root / "node_modules" / "x.js").write_text("eval(a)\n", encoding="utf-8")
            (tp.root / "app.js").write_text("eval(a)\n", encoding="utf-8")
            files = {f.file for f in scan.builtin_scan(tp.root, tp.root)}
            self.assertEqual(files, {"app.js"})

    def test_php_rules(self):
        with TempProject() as tp:
            (tp.root / "i.php").write_text("<?php include($_GET['p']); system($cmd); ?>\n", encoding="utf-8")
            rules = {f.rule for f in scan.builtin_scan(tp.root, tp.root)}
            self.assertTrue({"php-include", "php-exec"} <= rules)


class TestSkillEdges(unittest.TestCase):
    def test_project_overrides_builtin(self):
        with TempProject() as tp:
            sk = skills.Skills(tp.root, tp.cfg["data_dir"])
            sk.create("review", "my review", "1. custom", ["review"], scope="project")
            self.assertEqual(sk.get("review").scope, "project")
            self.assertTrue(sk.remove("review"))
            self.assertEqual(sk.get("review").scope, "builtin")

    def test_bad_frontmatter(self):
        self.assertIsNone(skills.parse("no frontmatter"))
        self.assertIsNone(skills.parse("---\nname: BAD NAME\n---\nx"))


if __name__ == "__main__":
    unittest.main()
