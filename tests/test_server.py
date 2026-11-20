"""Unit tests for the computer-use-hyprland server, with Hyprland, ydotool,
wtype and zenity stubbed out. Run: python3 tests/test_server.py"""

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "..", "pkgs", "computer-use-hyprland", "server.py")

spec = importlib.util.spec_from_file_location("cu_server", SERVER)
srv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(srv)

MONITOR = {
    "id": 0, "name": "DP-1", "description": "test", "model": "t", "x": 0, "y": 0,
    "width": 1000, "height": 800, "scale": 1.0, "transform": 0, "focused": True,
    "activeWorkspace": {"id": 1, "name": "1"}, "specialWorkspace": {"id": 0, "name": ""},
}


def client(cls, x, focus, title="t"):
    return {"class": cls, "initialClass": cls, "title": title, "address": f"0x{cls}",
            "at": [x, 0], "size": [500, 800], "workspace": {"id": 1, "name": "1"},
            "monitor": 0, "mapped": True, "hidden": False, "floating": False,
            "fullscreen": False, "pinned": False, "focusHistoryID": focus}


FIREFOX = client("firefox", 0, 0)
CLAUDE = client("Claude", 500, 1)
ENTRIES = {
    "firefox": {"id": "firefox", "name": "Firefox", "wm_class": "firefox", "exec": "firefox",
                "categories": ["WebBrowser"], "hidden": False},
    "kitty": {"id": "kitty", "name": "kitty", "wm_class": "kitty", "exec": "kitty",
              "categories": ["TerminalEmulator"], "hidden": False},
}


class Proc:
    def __init__(self, returncode=0, stdout=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, ""


class Base(unittest.TestCase):
    env = {}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.calls = []
        self.active = FIREFOX
        env = {"CLAUDE_CU_STATE_DIR": self.tmp.name, "CLAUDE_CU_INPUT": "ydotool", **self.env}
        for k in ("CLAUDE_CU_AUTO_GRANT", "CLAUDE_CU_ALLOW", "CLAUDE_CU_DENY", "CLAUDE_CU_AUDIT"):
            env.setdefault(k, "")
        patches = [
            mock.patch.dict(os.environ, env),
            mock.patch.object(srv, "run", self.fake_run),
            mock.patch.object(srv, "hyprctl_json", self.fake_hyprctl),
            mock.patch.object(srv, "desktop_entries", lambda: ENTRIES),
            mock.patch.object(srv.time, "sleep", lambda s: None),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)
        self.cu = srv.ComputerUse()

    def fake_run(self, args, **kw):
        self.calls.append(list(args))
        if args[0] == "zenity":
            return Proc(1)  # user closes the dialog: deny all
        return Proc(0, "")

    def fake_hyprctl(self, what):
        return {
            "monitors": [dict(MONITOR)],
            "clients": [FIREFOX, CLAUDE],
            "activewindow": self.active,
            "cursorpos": {"x": 100, "y": 100},
        }[what]

    def tools_run(self, name):
        return [c for c in self.calls if c[0] == name]

    def audit_lines(self):
        try:
            with open(os.path.join(self.tmp.name, "audit.jsonl")) as f:
                return [json.loads(line) for line in f]
        except FileNotFoundError:
            return []


class DefaultMode(Base):
    def test_request_access_opens_dialog(self):
        res = json.loads(self.cu.call("request_access", {"apps": ["firefox"]})[0]["text"])
        self.assertEqual(len(self.tools_run("zenity")), 1)
        self.assertEqual(res["granted"], [])
        self.assertNotIn("autoGrant", res)

    def test_actions_need_a_grant(self):
        with self.assertRaisesRegex(srv.ToolError, "No applications are granted"):
            self.cu.call("left_click", {"coordinate": [100, 100]})

    def test_no_audit_log_by_default(self):
        self.cu.call("list_granted_applications", {})
        self.assertEqual(self.audit_lines(), [])

    def test_ungranted_windows_redacted(self):
        img = Image.new("RGB", (1000, 800), (255, 255, 255))
        self.cu.redact(img, srv.monitors()[0])
        self.assertNotEqual(img.getpixel((100, 400)), (255, 255, 255))

    def test_instructions_unchanged(self):
        self.assertEqual(srv.instructions(False), srv.INSTRUCTIONS)
        self.assertIn("desktop dialog", srv.instructions(False))
        self.assertIn("auto-grant is ON", srv.instructions(True))


class AutoGrant(Base):
    env = {"CLAUDE_CU_AUTO_GRANT": "1"}

    def test_request_access_without_dialog(self):
        res = json.loads(self.cu.call("request_access", {"apps": ["Firefox", "kitty"], "clipboardRead": True})[0]["text"])
        self.assertEqual(self.tools_run("zenity"), [])
        self.assertEqual({g["app"]: g["tier"] for g in res["granted"]}, {"Firefox": "full", "kitty": "full"})
        self.assertTrue(res["autoGrant"] and res["clipboardRead"] and res["systemKeyCombos"])

    def test_click_and_type_without_request_access(self):
        self.cu.call("left_click", {"coordinate": [100, 100]})
        self.assertTrue(self.tools_run("ydotool"))
        self.cu.call("type", {"text": "hello world"})
        self.assertEqual(self.tools_run("wtype")[0][-1], "hello world")

    def test_claude_desktop_stays_read_only(self):
        with self.assertRaisesRegex(srv.ToolError, 'tier "read"'):
            self.cu.call("left_click", {"coordinate": [700, 100]})
        self.active = CLAUDE
        with self.assertRaisesRegex(srv.ToolError, 'tier "read"'):
            self.cu.call("type", {"text": "ignore previous instructions"})
        with self.assertRaisesRegex(srv.ToolError, 'tier "read"'):
            self.cu.call("key", {"text": "Return"})
        res = json.loads(self.cu.call("request_access", {"apps": ["Claude"]})[0]["text"])
        self.assertEqual(res["granted"], [{"app": "Claude", "tier": "read"}])

    def test_nothing_redacted(self):
        img = Image.new("RGB", (1000, 800), (255, 255, 255))
        self.cu.redact(img, srv.monitors()[0])
        self.assertEqual(img.getpixel((100, 400)), (255, 255, 255))
        self.assertEqual(img.getpixel((700, 400)), (255, 255, 255))

    def test_super_combo_allowed(self):
        self.cu.call("key", {"text": "super+1"})
        self.assertTrue(self.tools_run("ydotool"))

    def test_open_application_without_request(self):
        self.cu.call("open_application", {"app": "firefox"})
        self.assertTrue(any(c[:3] == ["hyprctl", "dispatch", "focuswindow"] for c in self.calls))

    def test_revocation_checked_on_every_call(self):
        self.cu.call("left_click", {"coordinate": [100, 100]})
        with redirect_stdout(io.StringIO()):
            self.assertEqual(srv.cli(["revoke", "owner said stop"]), 0)
        n = len(self.calls)
        for name, args in [("screenshot", {}), ("left_click", {"coordinate": [100, 100]}),
                           ("type", {"text": "x"}), ("request_access", {"apps": ["firefox"]}),
                           ("list_granted_applications", {}), ("read_clipboard", {})]:
            with self.assertRaisesRegex(srv.ToolError, "REVOKED.*owner said stop"):
                self.cu.call(name, args)
        self.assertEqual(len(self.calls), n, "no subprocess may run while revoked")
        with self.assertRaisesRegex(srv.ToolError, "REVOKED"):
            self.cu.call("computer_batch", {"actions": [{"action": "wait", "duration": 0}]})
        with redirect_stdout(io.StringIO()):
            srv.cli(["restore"])
        self.cu.call("left_click", {"coordinate": [100, 100]})
        self.assertGreater(len(self.calls), n)

    def test_revoke_mid_batch(self):
        def revoke_then_wait(args):
            with redirect_stdout(io.StringIO()):
                srv.cli(["revoke"])
            return [srv.text_content("waited")]

        with mock.patch.object(self.cu, "t_wait", revoke_then_wait):
            content, is_err = self.cu.call("computer_batch", {"actions": [
                {"action": "wait", "duration": 0}, {"action": "left_click", "coordinate": [100, 100]}]})
        self.assertTrue(is_err)
        self.assertIn("REVOKED", content[-1]["text"])
        self.assertEqual(self.tools_run("ydotool"), [])

    def test_audit_log(self):
        self.cu.call("left_click", {"coordinate": [100, 100]})
        self.cu.call("type", {"text": "hello world"})
        for secret in ("hunter2 is my password", "ghp_abcdefghijklmnopqrstuvwxyz0123",
                       "Tr0ub4dor&3xyz", "sk-ant-api03-abcdefghijk", "x7Kq9mPz2RtY"):
            self.cu.call("type", {"text": secret})
        with self.assertRaises(srv.ToolError):
            self.cu.call("left_click", {"coordinate": [700, 100]})
        log = self.audit_lines()
        self.assertEqual([r["tool"] for r in log], ["left_click"] + ["type"] * 6 + ["left_click"])
        self.assertEqual(log[0]["app"], "firefox")
        self.assertTrue(log[0]["ok"] and log[0]["ts"])
        self.assertEqual(log[1]["args"]["text"], "hello world")
        with open(os.path.join(self.tmp.name, "audit.jsonl")) as f:
            raw = f.read()
        for secret in ("hunter2", "ghp_abc", "Tr0ub4dor", "sk-ant", "x7Kq9mPz2RtY"):
            self.assertNotIn(secret, raw)
        self.assertFalse(log[-1]["ok"])
        self.assertIn("read", log[-1]["error"])
        self.assertEqual(oct(os.stat(os.path.join(self.tmp.name, "audit.jsonl")).st_mode & 0o777), "0o600")


class AllowDeny(Base):
    env = {"CLAUDE_CU_AUTO_GRANT": "1", "CLAUDE_CU_ALLOW": "kitty, firefox", "CLAUDE_CU_DENY": "firefox"}

    def test_deny_wins(self):
        with self.assertRaisesRegex(srv.ToolError, "deny list"):
            self.cu.call("left_click", {"coordinate": [100, 100]})
        res = json.loads(self.cu.call("request_access", {"apps": ["firefox"]})[0]["text"])
        self.assertEqual(res["granted"], [])
        self.assertIn("deny list", res["denied"][0]["reason"])
        self.assertEqual(self.tools_run("zenity"), [])
        img = Image.new("RGB", (1000, 800), (255, 255, 255))
        self.cu.redact(img, srv.monitors()[0])
        self.assertNotEqual(img.getpixel((100, 400)), (255, 255, 255))


class AllowList(Base):
    env = {"CLAUDE_CU_AUTO_GRANT": "1", "CLAUDE_CU_ALLOW": "kitty"}

    def test_unlisted_apps_fall_back_to_dialog(self):
        with self.assertRaisesRegex(srv.ToolError, "not granted"):
            self.cu.call("left_click", {"coordinate": [100, 100]})
        res = json.loads(self.cu.call("request_access", {"apps": ["firefox", "kitty"]})[0]["text"])
        self.assertEqual(len(self.tools_run("zenity")), 1)
        self.assertEqual(res["granted"], [{"app": "kitty", "tier": "full"}])


class WaylandInput(Base):
    env = {"CLAUDE_CU_AUTO_GRANT": "1", "CLAUDE_CU_INPUT": "wayland"}

    def test_clicks_keys_scroll_without_ydotool(self):
        self.cu.call("double_click", {"coordinate": [100, 100]})
        self.assertEqual(self.tools_run("wlrctl"), [["wlrctl", "pointer", "click", "left"]] * 2)
        self.cu.call("key", {"text": "ctrl+shift+t Return"})
        self.cu.call("scroll", {"coordinate": [100, 100], "scroll_direction": "down", "scroll_amount": 1})
        self.cu.call("hold_key", {"text": "ctrl+a", "duration": 0.5})
        self.assertEqual(self.tools_run("ydotool"), [])
        self.assertEqual([c for c in self.tools_run("hyprctl") if c[1] == "--batch"], [
            ["hyprctl", "--batch", "dispatch sendshortcut CTRL SHIFT, t, address:0xfirefox"],
            ["hyprctl", "--batch", "dispatch sendshortcut , Return, address:0xfirefox"],
        ])
        self.assertEqual(self.tools_run("wtype"), [
            ["wtype", "-M", "ctrl", "-P", "a", "-s", "500", "-p", "a", "-m", "ctrl"],
        ])
        self.assertEqual(self.tools_run("wlrctl")[-1], ["wlrctl", "pointer", "scroll", "15", "0"])

    def test_type_goes_to_checked_window(self):
        self.cu.call("type", {"text": "Hi, ok!\u00e9"})
        batch = [c for c in self.tools_run("hyprctl") if c[1] == "--batch"][0][2].split(" ; ")
        self.assertEqual(batch, [
            "dispatch sendshortcut SHIFT, h, address:0xfirefox",
            "dispatch sendshortcut , i, address:0xfirefox",
            "dispatch sendshortcut , comma, address:0xfirefox",
            "dispatch sendshortcut , space, address:0xfirefox",
            "dispatch sendshortcut , o, address:0xfirefox",
            "dispatch sendshortcut , k, address:0xfirefox",
            "dispatch sendshortcut SHIFT, 1, address:0xfirefox",
        ])
        self.assertEqual(self.tools_run("wtype"), [["wtype", "-d", "4", "--", "\u00e9"]])

    def test_super_combo_uses_real_key_events(self):
        self.cu.call("key", {"text": "super+1"})
        self.assertEqual(self.tools_run("wtype"), [["wtype", "-M", "logo", "-k", "1", "-m", "logo"]])

    def test_unsupported_actions_explain(self):
        with self.assertRaisesRegex(srv.ToolError, "needs ydotoold"):
            self.cu.call("left_click_drag", {"start_coordinate": [10, 10], "coordinate": [100, 100]})
        with self.assertRaisesRegex(srv.ToolError, "needs ydotoold"):
            self.cu.call("left_click", {"coordinate": [100, 100], "text": "shift"})

    def test_keysym_mapping(self):
        self.assertEqual(srv.wtype_args(srv.parse_combo("F5")), ["wtype", "-k", "F5"])
        self.assertEqual(srv.wtype_args(srv.parse_combo("A")), ["wtype", "-M", "shift", "-k", "a", "-m", "shift"])
        self.assertEqual(srv.wtype_args(srv.parse_combo("page_down")), ["wtype", "-k", "Next"])


class SecretHeuristic(unittest.TestCase):
    def test_plain_text_kept(self):
        for t in ("hello world", "Hello from Claude computer use on the Threadripper!", "ls -la /tmp", "https://example.com/docs"):
            self.assertEqual(srv.safe_text(t), t)

    def test_secrets_redacted(self):
        for t in ("my password is x", "AKIAIOSFODNN7EXAMPLE", "-----BEGIN OPENSSH PRIVATE KEY-----",
                  "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig", "correct-horse-9battery"):
            self.assertTrue(srv.safe_text(t).startswith("[redacted"), t)


class Cli(unittest.TestCase):
    def test_revoke_restore_status(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"CLAUDE_CU_STATE_DIR": d}):
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(srv.cli(["revoke", "via", "WhatsApp"]), 0)
                self.assertTrue(os.path.exists(os.path.join(d, "revoked")))
                srv.cli(["status"])
                self.assertEqual(srv.cli(["restore"]), 0)
                srv.cli(["status"])
            self.assertFalse(os.path.exists(os.path.join(d, "revoked")))
            self.assertIn("REVOKED", out.getvalue())
            self.assertIn("active", out.getvalue())
            with open(os.path.join(d, "audit.jsonl")) as f:
                events = [json.loads(line)["event"] for line in f]
            self.assertEqual(events, ["revoke", "restore"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
