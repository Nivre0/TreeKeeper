"""Minimal MCP server (Streamable HTTP transport, JSON responses) inside the running app.

AI assistants connect to http://127.0.0.1:<port>/mcp. Requests are handled in
background threads; every tool call is executed in the Qt GUI thread so it
works on the open file exactly like an edit made by hand.

Only the parts of the protocol needed for tools are implemented: initialize,
ping, tools/list and tools/call (spec: modelcontextprotocol.io).
"""

import json
import threading
import uuid
from concurrent.futures import Future
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from PySide6.QtCore import QObject, QThread, Signal

from .ai_tools import ToolError

DEFAULT_PORT = 8427
SERVER_NAME = "treekeeper"
SERVER_VERSION = "1.0"
PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")
INSTRUCTIONS = (
    "Tools for the family tree that is currently open in the TreeKeeper desktop app. "
    "Every person has an id; look ids up with list_persons or get_person before changing "
    "relationships. Children are not stored: they follow from the children's parents. "
    "Partnerships are mirrored on both partners automatically. Changes appear in the app "
    "immediately but are only written to disk by save_file (or when the user saves)."
)


class GuiInvoker(QObject):
    """Runs callables in the thread this object lives in (the GUI thread) and waits for the result."""

    _request = Signal(object)

    def __init__(self):
        super().__init__()
        self._request.connect(self._execute)

    def _execute(self, job):
        fn, future = job
        if not future.set_running_or_notify_cancel():
            return
        try:
            future.set_result(fn())
        except BaseException as e:  # passed on to the waiting server thread
            future.set_exception(e)

    def call(self, fn, timeout=60):
        if QThread.currentThread() is self.thread():
            return fn()
        future = Future()
        self._request.emit((fn, future))
        return future.result(timeout)


def _error(msg_id, code, message):
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


class McpServer:
    def __init__(self, tools):
        self.tools = tools
        self.invoker = GuiInvoker()
        self._httpd = None
        self.port = None

    @property
    def running(self):
        return self._httpd is not None

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}/mcp" if self.port else ""

    def start(self, port):
        """Start listening on 127.0.0.1:port. Raises OSError if the port is unavailable."""
        if self.running:
            self.stop()
        httpd = _HttpServer(("127.0.0.1", port), _Handler)
        httpd.mcp = self
        threading.Thread(target=httpd.serve_forever, name="mcp-server", daemon=True).start()
        self._httpd = httpd
        self.port = port

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

    # --- JSON-RPC -------------------------------------------------------------------

    def handle(self, msg):
        """Answer one JSON-RPC message; None for notifications and responses."""
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
            return _error(msg.get("id") if isinstance(msg, dict) else None, -32600, "Invalid request")
        method = msg.get("method")
        msg_id = msg.get("id")
        if method is None or "id" not in msg:
            return None  # a notification, or a response to a request we never send
        params = msg.get("params") or {}
        if method == "initialize":
            requested = params.get("protocolVersion")
            result = {
                "protocolVersion": requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": INSTRUCTIONS,
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": self.tools.definitions()}
        elif method == "tools/call":
            name = params.get("name")
            if name not in self.tools.names():
                return _error(msg_id, -32602, f"Unknown tool: {name}")
            result = self._call_tool(name, params.get("arguments") or {})
        else:
            return _error(msg_id, -32601, f"Method not found: {method}")
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def _call_tool(self, name, arguments):
        try:
            value = self.invoker.call(lambda: self.tools.call(name, arguments))
        except ToolError as e:
            return {"content": [{"type": "text", "text": str(e)}], "isError": True}
        except Exception as e:  # keep the server alive whatever happens in a tool
            return {"content": [{"type": "text", "text": f"Internal error: {e!r}"}], "isError": True}
        text = json.dumps(value, ensure_ascii=False, indent=2)
        return {"content": [{"type": "text", "text": text}], "isError": False}


class _HttpServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False  # on Windows, reuse would let two servers share the port


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "TreeKeeperMCP/" + SERVER_VERSION

    def log_message(self, fmt, *args):
        pass

    def _send(self, status, body=None, headers=None):
        data = b"" if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        if body is not None:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def _check_request(self):
        """Only /mcp, and only from this computer (protects against DNS rebinding)."""
        if urlparse(self.path).path.rstrip("/") != "/mcp":
            self._send(404, {"error": "Not found. The MCP endpoint is /mcp"})
            return False
        origin = self.headers.get("Origin")
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        if (origin and urlparse(origin).hostname not in LOCAL_HOSTS) or (host and host not in LOCAL_HOSTS):
            self._send(403, {"error": "Forbidden"})
            return False
        return True

    def _read_body(self):
        """Always consume the request body, even for requests we reject: the connection is
        kept alive and unread bytes would be parsed as the start of the next request."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self.close_connection = True
            return b""
        return self.rfile.read(length) if length > 0 else b""

    def do_POST(self):
        body = self._read_body()
        if not self._check_request():
            return
        try:
            payload = json.loads(body or b"null")
        except (ValueError, UnicodeDecodeError):
            self._send(400, _error(None, -32700, "Parse error"))
            return
        messages = payload if isinstance(payload, list) else [payload]
        responses = [r for r in (self.server.mcp.handle(m) for m in messages) if r is not None]
        headers = {}
        if any(isinstance(m, dict) and m.get("method") == "initialize" for m in messages):
            headers["Mcp-Session-Id"] = uuid.uuid4().hex
        if not responses:
            self._send(202, headers=headers)
        else:
            self._send(200, responses if isinstance(payload, list) else responses[0], headers)

    def do_GET(self):
        # No server-initiated messages, so no event stream (allowed by the spec).
        self._read_body()
        if self._check_request():
            self._send(405, headers={"Allow": "POST"})

    def do_DELETE(self):
        self._read_body()
        if self._check_request():
            self._send(200)
