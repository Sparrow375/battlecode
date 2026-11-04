from __future__ import annotations
import http.server
import socketserver
import json
import os
import glob
from typing import Dict, Any
from runner.match import run_match, BOT_REGISTRY
from engine.models import GameConfig

PORT = 8000
WEB_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(WEB_DIR)

class NodeWarRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_GET(self):
        if self.path == "/api/replays":
            replays_dir = os.path.join(PROJECT_ROOT, "replays")
            files = sorted(glob.glob(os.path.join(replays_dir, "*.json")), key=os.path.getmtime, reverse=True)
            replay_names = [os.path.basename(f) for f in files]
            self._send_json({"replays": replay_names})
            return

        elif self.path.startswith("/api/replay/"):
            filename = self.path[len("/api/replay/"):]
            replay_file = os.path.join(PROJECT_ROOT, "replays", filename)
            if os.path.exists(replay_file):
                with open(replay_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._send_json(data)
            else:
                self.send_error(404, "Replay not found")
            return

        # Serve static web files
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/run-match":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            params = json.loads(body.decode("utf-8")) if body else {}

            p1_bot = params.get("p1", "rusher")
            p2_bot = params.get("p2", "turtle")
            max_turns = int(params.get("turns", 120))

            if p1_bot not in BOT_REGISTRY or p2_bot not in BOT_REGISTRY:
                self.send_error(400, "Invalid bot selection")
                return

            cfg = GameConfig(max_turns=max_turns)
            res = run_match(
                p1_class=BOT_REGISTRY[p1_bot],
                p2_class=BOT_REGISTRY[p2_bot],
                p1_name=p1_bot.capitalize(),
                p2_name=p2_bot.capitalize(),
                config=cfg,
                save_replay=True,
                replay_dir=os.path.join(PROJECT_ROOT, "replays")
            )

            # Read and return the saved replay
            if res.replay_path and os.path.exists(res.replay_path):
                with open(res.replay_path, "r", encoding="utf-8") as f:
                    replay_data = json.load(f)
                replay_data["filename"] = os.path.basename(res.replay_path)
                self._send_json(replay_data)
            else:
                self._send_json({"error": "Failed to generate replay"})
            return

        self.send_error(404, "Unknown endpoint")

    def _send_json(self, data: Dict[str, Any]):
        response = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(response)

def run_server():
    os.chdir(WEB_DIR)
    with socketserver.TCPServer(("", PORT), NodeWarRequestHandler) as httpd:
        print(f"\n" + "=" * 60)
        print(f"  NODE WAR - ESPORTS SPECTATOR WEB ARENA")
        print(f"=" * 60)
        print(f"  Server running live at: http://localhost:{PORT}")
        print(f"  Press Ctrl+C to stop.")
        print(f"=" * 60 + "\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")

if __name__ == "__main__":
    run_server()
