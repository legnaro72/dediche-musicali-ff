"""
Micro API locale per salvare feedback nei JSON.

Endpoint:
  POST /save_vote
  POST /save_reaction

Impostare DDGFF_FEEDBACK_TOKEN per richiedere header:
  Authorization: Bearer <token>
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.dedication_feedback import load_all_feedback, load_feedback, update_reaction, update_vote

HOST = os.environ.get("DDGFF_FEEDBACK_HOST", "127.0.0.1")
PORT = int(os.environ.get("DDGFF_FEEDBACK_PORT") or os.environ.get("PORT") or "8787")
TOKEN = os.environ.get("DDGFF_FEEDBACK_TOKEN", "").strip()
ALLOWED_ORIGIN = os.environ.get("DDGFF_FEEDBACK_ORIGIN", "*")


class FeedbackHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self._send_json(200, {"ok": True})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path in ("", "/"):
                self._send_json(200, {
                    "ok": True,
                    "service": "DDG FF feedback API",
                    "endpoints": ["/feedback/all", "/feedback?id=<dedication_id>", "/save_vote", "/save_reaction"],
                })
                return

            if parsed.path == "/feedback/all":
                self._send_json(200, {"ok": True, "feedback": load_all_feedback()})
                return

            if parsed.path == "/feedback":
                params = parse_qs(parsed.query)
                dedication_id = (params.get("id") or params.get("dedicationId") or [""])[0]
                self._send_json(200, {"ok": True, "feedback": load_feedback(dedication_id)})
                return

            self._send_json(404, {"ok": False, "error": "Endpoint non trovato."})
        except Exception as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})

    def do_POST(self) -> None:
        if TOKEN and self.headers.get("Authorization") != f"Bearer {TOKEN}":
            self._send_json(401, {"ok": False, "error": "Non autorizzato."})
            return

        length = int(self.headers.get("Content-Length") or "0")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            dedication_id = str(payload.get("id") or payload.get("dedicationId") or "").strip()

            if self.path == "/save_vote":
                updated = update_vote(
                    dedication_id,
                    payload.get("votoPilly"),
                    payload.get("pensieroPilly", ""),
                    user_id=payload.get("userId", ""),
                    user_name=payload.get("userName") or payload.get("displayName") or "",
                    nome=payload.get("nome", ""),
                    cognome=payload.get("cognome", ""),
                )
            elif self.path == "/save_reaction":
                updated = update_reaction(
                    dedication_id,
                    str(payload.get("reaction") or ""),
                    payload.get("previousReaction"),
                    user_id=payload.get("userId", ""),
                    user_name=payload.get("userName") or payload.get("displayName") or "",
                    nome=payload.get("nome", ""),
                    cognome=payload.get("cognome", ""),
                )
            else:
                self._send_json(404, {"ok": False, "error": "Endpoint non trovato."})
                return
        except Exception as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
            return

        self._send_json(200, {
            "ok": True,
            "id": updated.get("id"),
            "votoPilly": updated.get("votoPilly"),
            "pensieroPilly": updated.get("pensieroPilly"),
            "reactions": updated.get("reactions"),
            "votes": updated.get("votes", []),
            "thoughts": updated.get("thoughts", []),
            "reactionEntries": updated.get("reactionEntries", []),
            "updated_at": updated.get("updated_at"),
        })

    def log_message(self, format: str, *args) -> None:
        print(f"{self.address_string()} - {format % args}")


def main() -> int:
    server = ThreadingHTTPServer((HOST, PORT), FeedbackHandler)
    print(f"DDG FF feedback API in ascolto su http://{HOST}:{PORT}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
