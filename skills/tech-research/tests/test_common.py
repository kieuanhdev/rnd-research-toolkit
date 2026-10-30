import http.server
import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import common  # noqa: E402

ROUTES = {
    "/ok": (200, b'{"a": 1}'),
    "/forbidden": (403, b"nope"),
    "/badjson": (200, b"not json"),
}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        code, body = ROUTES.get(self.path, (404, b""))
        self.send_response(code)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class GetJsonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_get_json_ok(self):
        self.assertEqual(common.get_json(self.base + "/ok"), ({"a": 1}, None))

    def test_get_json_returns_error_on_http_error(self):
        data, err = common.get_json(self.base + "/forbidden")
        self.assertIsNone(data)
        self.assertIn("403", err)

    def test_get_json_returns_error_on_bad_json(self):
        data, err = common.get_json(self.base + "/badjson")
        self.assertIsNone(data)
        self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
