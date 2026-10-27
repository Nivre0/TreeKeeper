import json
import os
import socket
import sys
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from treekeeper.main_window import MainWindow, resource_path  # noqa: E402
from treekeeper.model import TreeKeeper  # noqa: E402


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class McpServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setOrganizationName("TreeKeeper-tests")  # keep the user's settings untouched

    def setUp(self):
        self.window = MainWindow()
        tree = TreeKeeper.load(resource_path("sample_family.json"))
        tree.path = None  # like File > Open sample data: never write to the bundled sample
        self.window._set_tree(tree)
        self.port = free_port()
        self.window.start_mcp_server(self.port)
        self.assertTrue(self.window.mcp_server.running, self.window.mcp_error)
        self.next_id = 0

    def tearDown(self):
        self.window.stop_mcp_server()
        self.window.tree.dirty = False
        self.window.close()

    def post(self, body, headers=None):
        """POST in a worker thread while this (GUI) thread keeps processing events."""
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/mcp", data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                     **(headers or {})})
        result = {}

        def run():
            try:
                with urllib.request.urlopen(request, timeout=10) as response:
                    result["status"] = response.status
                    result["headers"] = response.headers
                    raw = response.read()
                    result["body"] = json.loads(raw) if raw else None
            except urllib.error.HTTPError as e:
                result["status"] = e.code
                result["body"] = None

        thread = threading.Thread(target=run)
        thread.start()
        while thread.is_alive():
            self.app.processEvents()
            thread.join(0.01)
        return result

    def rpc(self, method, params=None):
        self.next_id += 1
        response = self.post({"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params or {}})
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"]["id"], self.next_id)
        return response["body"]

    def tool(self, name, **arguments):
        result = self.rpc("tools/call", {"name": name, "arguments": arguments})["result"]
        text = result["content"][0]["text"]
        return (json.loads(text) if not result["isError"] else text), result["isError"]

    def find(self, first_name):
        return next(p for p in self.window.tree.persons.values() if p.first_name == first_name)

    def test_handshake_and_tool_list(self):
        init = self.post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                          "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                     "clientInfo": {"name": "test", "version": "1"}}})
        self.assertEqual(init["body"]["result"]["protocolVersion"], "2025-06-18")
        self.assertIn("Mcp-Session-Id", init["headers"])
        self.assertEqual(self.post({"jsonrpc": "2.0", "method": "notifications/initialized"})["status"], 202)
        names = {t["name"] for t in self.rpc("tools/list")["result"]["tools"]}
        self.assertTrue({"list_persons", "get_person", "create_person", "update_person", "delete_person",
                         "set_partnership", "remove_partnership", "show_person", "save_file"} <= names)
        self.assertEqual(self.rpc("nonsense")["error"]["code"], -32601)

    def test_create_edit_delete_person_in_open_window(self):
        walter = self.find("Walter")
        created, error = self.tool("create_person", first_name="Fritz", last_name="Keller", gender="male",
                                   birth_date="ca. 1950", parents=[walter.id])
        self.assertFalse(error, created)
        new_id = created["id"]
        self.assertEqual(self.window.tree.get(new_id).parents, [walter.id])
        self.assertTrue(self.window.tree.dirty)
        self.assertEqual(self.window.focus_id, new_id)          # shown in the app right away
        self.assertIn("Fritz", self.window.statusBar().currentMessage())

        updated, error = self.tool("update_person", id=new_id, death_date="2020", notes="Added by AI")
        self.assertFalse(error, updated)
        self.assertEqual(updated["lifespan"], "c. 1950–2020")
        self.assertEqual(updated["father"]["id"], walter.id)

        hedwig = self.find("Hedwig")
        partner, error = self.tool("set_partnership", person_id=new_id, partner_id=hedwig.id,
                                   status="divorced", **{"from": "1975", "to": "1980"})
        self.assertFalse(error, partner)
        self.assertEqual(self.window.tree.get(hedwig.id).partnership_with(new_id).status, "divorced")
        self.tool("remove_partnership", person_id=hedwig.id, partner_id=new_id)
        self.assertIsNone(self.window.tree.get(new_id).partnership_with(hedwig.id))

        deleted, error = self.tool("delete_person", id=new_id)
        self.assertFalse(error, deleted)
        self.assertNotIn(new_id, self.window.tree.persons)

    def test_errors_are_reported_to_the_ai(self):
        text, error = self.tool("update_person", id="missing", first_name="X")
        self.assertTrue(error)
        self.assertIn("No person", text)
        text, error = self.tool("create_person", first_name="X", birth_date="sometime")
        self.assertTrue(error)
        self.assertIn("not a valid date", text)
        thomas, walter = self.find("Thomas"), self.find("Walter")
        text, error = self.tool("update_person", id=walter.id, parents=[thomas.id])
        self.assertTrue(error)
        self.assertIn("descendant", text)
        text, error = self.tool("save_file")
        self.assertTrue(error)                                   # sample was opened without a path
        self.assertIn("Save as", text)

    def test_list_get_and_show(self):
        persons, _ = self.tool("list_persons", query="keller")
        self.assertTrue(all(self.window.tree.get(p["id"]).matches("keller") for p in persons))
        self.assertEqual(len(persons), sum(p.matches("keller") for p in self.window.tree.persons.values()))
        walter = self.find("Walter")
        details, _ = self.tool("get_person", id=walter.id)
        self.assertEqual(len(details["children"]), 2)
        self.assertEqual({p["partner_name"] for p in details["partnerships"]},
                         {"Elisabeth Meier", "Hedwig Keller"})
        shown, _ = self.tool("show_person", id=walter.id, view="whole_family")
        self.assertEqual(self.window.focus_id, walter.id)
        self.assertEqual(shown["view"], "whole_family")

    def test_unknown_path_with_body_keeps_connection_usable(self):
        # Claude Code first probes OAuth endpoints (e.g. POST /register with a JSON body) and then
        # reuses the same keep-alive connection for /mcp. The unread body must not corrupt it.
        import http.client
        result = {}

        def run():
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
            body = json.dumps({"client_name": "probe", "redirect_uris": ["http://localhost:1/callback"]})
            conn.request("POST", "/register", body=body, headers={"Content-Type": "application/json"})
            response = conn.getresponse()
            result["register"] = response.status
            response.read()
            if response.will_close:
                conn.close()
                conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
            conn.request("POST", "/mcp", body=json.dumps({"jsonrpc": "2.0", "id": 7, "method": "ping"}),
                         headers={"Content-Type": "application/json"})
            response = conn.getresponse()
            result["mcp"] = (response.status, json.loads(response.read()))
            conn.close()

        thread = threading.Thread(target=run)
        thread.start()
        while thread.is_alive():
            self.app.processEvents()
            thread.join(0.01)
        self.assertEqual(result["register"], 404)
        self.assertEqual(result["mcp"], (200, {"jsonrpc": "2.0", "id": 7, "result": {}}))

    def test_rejects_foreign_origin_and_port_in_use(self):
        response = self.post({"jsonrpc": "2.0", "id": 1, "method": "ping"}, {"Origin": "http://evil.example"})
        self.assertEqual(response["status"], 403)
        other = MainWindow()
        other.start_mcp_server(self.port)
        self.assertFalse(other.mcp_server.running)
        self.assertIn(str(self.port), other.mcp_error)
        other.close()


if __name__ == "__main__":
    unittest.main()
