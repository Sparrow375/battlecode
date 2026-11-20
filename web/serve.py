from __future__ import annotations
import sys
import os

# Ensure project root is in sys.path regardless of how this script is invoked
WEB_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(WEB_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import http.server
import socketserver
import json
import glob
from typing import Dict, Any, Type

from runner.match import run_match, BOT_REGISTRY, discover_custom_bots, resolve_bot, load_bot_from_file
from runner.tournament import run_balance_matrix
from engine.models import GameConfig
from bots.base import BotBase

PORT = 8000

class CustomDynamicBot(BotBase):
    """Placeholder for dynamic user-uploaded bots."""
    pass

def compile_custom_bot(code_str: str) -> Type[BotBase]:
    """Compiles custom python code string and extracts the BotBase subclass."""
    namespace: Dict[str, Any] = {}
    exec(code_str, namespace)
    for obj in namespace.values():
        if isinstance(obj, type) and issubclass(obj, BotBase) and obj is not BotBase:
            return obj
    raise ValueError("No subclass of BotBase found in custom bot code.")

class NodeWarRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/replays":
            replays_dir = os.path.join(PROJECT_ROOT, "replays")
            files = sorted(glob.glob(os.path.join(replays_dir, "*.json")), key=os.path.getmtime, reverse=True)
            replay_list = []
            for f in files:
                fname = os.path.basename(f)
                try:
                    with open(f, "r", encoding="utf-8") as rf:
                        head = json.load(rf).get("metadata", {})
                        replay_list.append({
                            "filename": fname,
                            "p1_name": head.get("p1_name", "P1"),
                            "p2_name": head.get("p2_name", "P2"),
                            "winner": head.get("winner", 0),
                            "total_turns": head.get("total_turns", 0)
                        })
                except Exception:
                    replay_list.append({"filename": fname, "p1_name": fname, "p2_name": "", "winner": 0, "total_turns": 0})

            self._send_json({"replays": replay_list})
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

        elif self.path == "/api/bots":
            custom_map = discover_custom_bots(os.path.join(PROJECT_ROOT, "bots"))
            custom_list = []
            for fname, info in custom_map.items():
                custom_list.append({
                    "id": fname,
                    "filename": fname,
                    "class_name": info.get("class_name", ""),
                    "display_name": info.get("display_name", fname),
                    "error": info.get("error")
                })
            builtins = [
                {"id": "rusher", "name": "Rusher Bot", "class": "RusherBot"},
                {"id": "turtle", "name": "Turtle Bot", "class": "TurtleBot"},
                {"id": "balanced", "name": "Balanced (Scout) Bot", "class": "BalancedBot"},
                {"id": "starter", "name": "Starter Bot", "class": "StarterBot"}
            ]
            self._send_json({
                "builtins": builtins,
                "custom_files": custom_list,
                "lab": {"id": "custom", "name": "Custom Lab Bot (from Code Editor)"}
            })
            return

        elif self.path.startswith("/api/bot-source/"):
            filename = self.path[len("/api/bot-source/"):]
            filename = os.path.basename(filename)
            bot_file = os.path.join(PROJECT_ROOT, "bots", filename)
            if os.path.exists(bot_file):
                with open(bot_file, "r", encoding="utf-8") as f:
                    source = f.read()
                self._send_json({"filename": filename, "source": source})
            else:
                self.send_error(404, "Bot file not found")
            return

        # Serve static web files
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/run-match":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            params = json.loads(body.decode("utf-8")) if body else {}

            p1_key = params.get("p1", "rusher")
            p2_key = params.get("p2", "turtle")
            max_turns = int(params.get("turns", 120))
            initial_credits = int(params.get("initial_credits", 30))
            relic_spawn_turn = int(params.get("relic_spawn_turn")) if params.get("relic_spawn_turn") else None
            relic_points = int(params.get("relic_points", 10))
            custom_code = params.get("custom_code", "")

            # Resolve bot classes
            try:
                if p1_key == "custom":
                    p1_class = compile_custom_bot(custom_code)
                    p1_name = "CustomBot"
                else:
                    p1_class, p1_name = resolve_bot(p1_key, bots_dir=os.path.join(PROJECT_ROOT, "bots"))

                if p2_key == "custom":
                    p2_class = compile_custom_bot(custom_code)
                    p2_name = "CustomBot"
                else:
                    p2_class, p2_name = resolve_bot(p2_key, bots_dir=os.path.join(PROJECT_ROOT, "bots"))
            except Exception as e:
                self._send_json({"error": f"Failed to load or compile bot: {str(e)}"}, status=400)
                return

            if not p1_class or not p2_class:
                self._send_json({"error": "Invalid bot selection"}, status=400)
                return

            cfg = GameConfig(
                max_turns=max_turns,
                initial_credits=initial_credits,
                relic_spawn_turn=relic_spawn_turn,
                relic_points_per_turn=relic_points
            )

            res = run_match(
                p1_class=p1_class,
                p2_class=p2_class,
                p1_name=p1_name,
                p2_name=p2_name,
                config=cfg,
                save_replay=True,
                replay_dir=os.path.join(PROJECT_ROOT, "replays")
            )

            if res.replay_path and os.path.exists(res.replay_path):
                with open(res.replay_path, "r", encoding="utf-8") as f:
                    replay_data = json.load(f)
                replay_data["filename"] = os.path.basename(res.replay_path)
                self._send_json(replay_data)
            else:
                self._send_json({"error": "Failed to generate replay"}, status=500)
            return

        elif self.path == "/api/run-tournament":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            params = json.loads(body.decode("utf-8")) if body else {}

            rounds = int(params.get("rounds", 10))
            max_turns = int(params.get("turns", 120))

            matrix_results = run_balance_matrix(rounds_per_pair=rounds, max_turns=max_turns)
            self._send_json({"tournament": matrix_results})
            return

        self.send_error(404, "Unknown endpoint")

    def _send_json(self, data: Dict[str, Any], status: int = 200):
        response = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

def run_server(port: int = PORT):
    os.chdir(WEB_DIR)
    with ThreadedHTTPServer(("", port), NodeWarRequestHandler) as httpd:
        print(f"\n" + "=" * 60)
        print(f"  NODE WAR - ESPORTS SPECTATOR ARENA")
        print(f"=" * 60)
        print(f"  Server running live at: http://localhost:{port}")
        print(f"  Press Ctrl+C to stop.")
        print(f"=" * 60 + "\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")

if __name__ == "__main__":
    run_server()
