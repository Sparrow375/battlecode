from __future__ import annotations
import unittest
import threading
import time
import urllib.request
import json
from web.serve import PORT, NodeWarRequestHandler
import socketserver

class TestWebServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_port = 8092
        socketserver.TCPServer.allow_reuse_address = True
        cls.httpd = socketserver.TCPServer(("127.0.0.1", cls.test_port), NodeWarRequestHandler)
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def test_get_index(self):
        url = f"http://127.0.0.1:{self.test_port}/"
        with urllib.request.urlopen(url) as response:
            self.assertEqual(response.status, 200)
            content = response.read().decode("utf-8")
            self.assertIn("Node War", content)

    def test_get_replays_list(self):
        url = f"http://127.0.0.1:{self.test_port}/api/replays"
        with urllib.request.urlopen(url) as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))
            self.assertIn("replays", data)

    def test_post_run_match(self):
        url = f"http://127.0.0.1:{self.test_port}/api/run-match"
        payload = json.dumps({"p1": "rusher", "p2": "turtle", "turns": 20}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))
            self.assertIn("metadata", data)
            self.assertIn("frames", data)

    def test_post_run_tournament(self):
        url = f"http://127.0.0.1:{self.test_port}/api/run-tournament"
        payload = json.dumps({"rounds": 2, "turns": 20}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))
            self.assertIn("tournament", data)

if __name__ == "__main__":
    unittest.main()
