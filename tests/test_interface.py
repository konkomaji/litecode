"""Chat routing, grammar schema, loop guard, approval feedback, and tool-line rendering."""
import json, unittest
from litecode import router, ui
from litecode.agent import Agent
from litecode.tools import Tools, action_schema, TOOL_ARGS
from tests.helpers import FakeServer, TempProject, yes


class TestChatRouting(unittest.TestCase):
    def test_chat_messages(self):
        for t in ("hey", "hi there", "thanks!", "what is a python decorator?",
                  "how does TCP handshake work", "who are you",
                  "what is a python list comprehension, in one sentence", "how do I write a for loop in go"):
            self.assertTrue(router.is_chat(t), t)

    def test_task_messages(self):
        for t in ("build a python calculator", "fix the bug in app.py", "explain @main.py",
                  "run the tests", "create calc.py", "review this code", "list files",
                  "what does src/app.js do", "refactor my project", "can you build me a todo app",
                  "why does this code crash", "what files are in this project"):
            self.assertFalse(router.is_chat(t), t)

    def test_code_block_is_task(self):
        self.assertFalse(router.is_chat("why does this fail\n```\nx = 1/0\n```"))


class TestSchema(unittest.TestCase):
    def test_one_branch_per_tool(self):
        s = action_schema()
        self.assertEqual(len(s["anyOf"]), len(TOOL_ARGS))
        consts = {b["properties"]["tool"]["const"] for b in s["anyOf"]}
        self.assertEqual(consts, set(TOOL_ARGS))

    def test_required_args(self):
        s = action_schema()
        wf = next(b for b in s["anyOf"] if b["properties"]["tool"]["const"] == "write_file")
        self.assertEqual(set(wf["properties"]["args"]["required"]), {"path", "content"})

    def test_mcp_branch(self):
        s = action_schema(["mcp__fs__read"])
        self.assertEqual(s["anyOf"][-1]["properties"]["tool"]["enum"], ["mcp__fs__read"])

    def test_schema_passed_to_server(self):
        with TempProject() as tp:
            seen = {}

            class S(FakeServer):
                def chat(self, messages, json_schema=None, **kw):
                    seen["schema"] = json_schema
                    return super().chat(messages, **kw)
            a = Agent(S([{"tool": "final", "args": {"message": "ok"}}]), tp.root, yes, cfg=tp.cfg)
            a.run("do it")
            self.assertIn("anyOf", seen["schema"])


class TestAgentGuards(unittest.TestCase):
    def test_repeat_loop_stops(self):
        with TempProject() as tp:
            step = {"tool": "list_dir", "args": {"path": "."}}
            srv = FakeServer([step] * 10)
            a = Agent(srv, tp.root, yes, cfg=tp.cfg)
            out = a.run("hey")
            self.assertIn("repeated the same step", out)
            self.assertLessEqual(len(srv.calls), 4)

    def test_broken_tool_json_never_shown(self):
        with TempProject() as tp:
            bad = '{"tool": "write_file", "args": {"path": "c.py", "content": "x = 1\n</param>'
            a = Agent(FakeServer([bad] * 5), tp.root, yes, cfg=tp.cfg)
            out = a.run("make c.py")
            self.assertNotIn('"tool"', out)
            self.assertIn("Stopped", out)

    def test_budget_message(self):
        with TempProject() as tp:
            steps = [{"tool": "read_file", "args": {"path": f"f{i}.txt"}} for i in range(5)]
            a = Agent(FakeServer(steps), tp.root, yes, cfg=tp.cfg, max_steps=3)
            out = a.run("look around")
            self.assertIn("Stopped after 3 steps", out)
            self.assertIn("continue", out)


class TestChatPath(unittest.TestCase):
    def test_chat_uses_short_prompt_and_history(self):
        with TempProject() as tp:
            srv = FakeServer(["Hello. What do you want to do?", "Python is a language."])
            a = Agent(srv, tp.root, yes, cfg=tp.cfg)
            self.assertEqual(a.chat("hey"), "Hello. What do you want to do?")
            a.chat("what is python")
            msgs = srv.calls[1]
            self.assertNotIn("write_file", msgs[0]["content"])        # no tool spec in chat
            self.assertEqual([m["role"] for m in msgs], ["system", "user", "assistant", "user"])
            self.assertEqual(msgs[1]["content"], "hey")

    def test_history_skips_tool_steps(self):
        with TempProject() as tp:
            srv = FakeServer([{"tool": "list_dir", "args": {}}, {"tool": "final", "args": {"message": "Empty."}},
                              "Sure."])
            a = Agent(srv, tp.root, yes, cfg=tp.cfg)
            a.run("list files")
            a.chat("thanks")
            contents = [m["content"] for m in srv.calls[-1]]
            self.assertFalse(any(c.startswith("OBSERVATION") or c.startswith("{") for c in contents[1:]))


class TestApprovalFeedback(unittest.TestCase):
    def test_no_with_instruction(self):
        with TempProject() as tp:
            t = Tools(tp.root, lambda *a: "use a.txt instead")
            out = t.call("write_file", {"path": "n.txt", "content": "x"})
            self.assertIn("use a.txt instead", out)
            self.assertFalse((tp.root / "n.txt").exists())

    def test_always(self):
        with TempProject() as tp:
            t = Tools(tp.root, lambda *a: "always")
            self.assertIn("wrote", t.call("write_file", {"path": "n.txt", "content": "x"}))


class TestToolLines(unittest.TestCase):
    def test_titles(self):
        self.assertIn("Bash", ui.tool_title("run", {"cmd": "pytest -q"}))
        self.assertIn("calc.py", ui.tool_title("write_file", {"path": "calc.py", "content": "x"}))
        self.assertIn('pattern: "**/*.py"', ui.tool_title("glob", {"pattern": "**/*.py"}))

    def test_results(self):
        self.assertIn("Read", ui.tool_result("read_file", "1\ta\n2\tb")[0])
        self.assertIn("2", ui.tool_result("read_file", "1\ta\n2\tb")[0])
        self.assertIn("Empty folder", ui.tool_result("list_dir", "(empty)")[0])
        r = ui.tool_result("run", "(exit 2)\nerr1\nerr2\nerr3\nerr4\nerr5\nerr6")
        self.assertIn("exit 2", r[0])
        self.assertIn("+2 lines", r[-1])
        self.assertIn("denied", ui.tool_result("write_file", "(denied by user)")[0])


if __name__ == "__main__":
    unittest.main()
