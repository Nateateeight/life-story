"""
Life Story Interviewer — HTTP Server

Wraps the Interviewer harness in a simple HTTP server.
Handles POST /api/interview requests from the web client.

Runs on the M4 Mini. Use a tunnel (Cloudflare/ngrok) for HTTPS access from phones.

Usage:
    python3 interview_server.py [--port 8080]
    
Then set the interview.html API_URL to point to this server.
"""

import json
import os
import sys
import time
import uuid
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

from interviewer_harness import Interviewer

# ── Configuration ────────────────────────────────────────────────────────

PORT = int(os.environ.get("PORT", 8080))
MODEL_ID = os.environ.get("MODEL_ID", "mlx-community/Qwen2.5-7B-Instruct-4bit")
PERSONA_PATH = Path(__file__).parent / "interviewer-soul.md"
LOG_DIR = Path(__file__).parent / "interviews"

# ── Session Store ────────────────────────────────────────────────────────

# Map of conversation_id -> Interviewer instance
# Each session keeps its own conversation with its own phase tracker
_sessions: dict[str, Interviewer] = {}

def get_or_create_session(conversation_id: str) -> Interviewer:
    """Get existing session or create new one."""
    if conversation_id not in _sessions:
        print(f"Creating new session: {conversation_id}")
        _sessions[conversation_id] = Interviewer(
            model_id=MODEL_ID,
            persona_path=PERSONA_PATH,
            log_dir=LOG_DIR,
        )
        # Add opening message
        opening = _sessions[conversation_id].start()
        print(f"Opening: {opening[:80]}...")
    return _sessions[conversation_id]


# ── HTTP Handler ─────────────────────────────────────────────────────────

class InterviewHandler(BaseHTTPRequestHandler):
    """Handle interview API requests."""

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def _send_json(self, data: dict, status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _handle_resume(self):
        """Handle POST /api/resume — restore a saved conversation."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)

            conversation_id = data.get("conversation_id")
            if not conversation_id:
                self._send_json({"error": "No conversation_id provided"}, 400)
                return

            # Check if we have this conversation in memory
            if conversation_id in _sessions:
                session = _sessions[conversation_id]
                self._send_json({
                    "status": "resumed",
                    "conversation_id": conversation_id,
                    "phase": session.current_phase,
                    "turns": session.turn_count,
                    "messages": session.get_conversation(),
                })
                return

            # Try to load from disk
            transcript_path = LOG_DIR / f"interview_{conversation_id}.json"
            if transcript_path.exists():
                saved = json.loads(transcript_path.read_text())
                # Recreate session
                session = Interviewer(
                    model_id=MODEL_ID,
                    persona_path=PERSONA_PATH,
                    log_dir=LOG_DIR,
                )
                # Restore conversation history
                for msg in saved.get("messages", []):
                    if msg["role"] != "system":
                        session.messages.append(msg)
                session.current_phase = saved.get("phase", "Roots")
                session.turn_count = saved.get("turns", 0)
                _sessions[conversation_id] = session

                self._send_json({
                    "status": "resumed",
                    "conversation_id": conversation_id,
                    "phase": session.current_phase,
                    "turns": session.turn_count,
                    "messages": session.get_conversation(),
                })
            else:
                self._send_json({"status": "not_found", "conversation_id": conversation_id})

        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, 400)
        except Exception as e:
            print(f"Resume error: {e}")
            self._send_json({"error": str(e)}, 500)

    def do_POST(self):
        """Handle POST /api/interview and /api/resume."""
        if self.path == "/api/resume":
            self._handle_resume()
            return

        if self.path != "/api/interview":
            self._send_json({"error": "Not found"}, 404)
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)

            message = data.get("message", "")
            conversation_id = data.get("conversation_id") or str(uuid.uuid4())

            if not message:
                self._send_json({"error": "No message provided"}, 400)
                return

            # Get or create session
            session = get_or_create_session(conversation_id)

            # Generate response
            start_time = time.time()
            response = session.respond(message)
            elapsed = time.time() - start_time

            print(f"[{conversation_id[:8]}] User: {message[:60]}...")
            print(f"[{conversation_id[:8]}] AI: {response[:60]}... ({elapsed:.1f}s)")

            # Save transcript periodically (every 5 turns) for resume support
            if session.turn_count % 5 == 0:
                session.save_transcript()

            # Send response
            self._send_json({
                "response": response,
                "conversation_id": conversation_id,
                "phase": session.current_phase,
                "turns": session.turn_count,
                "time_seconds": round(elapsed, 2),
            })

        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, 400)
        except Exception as e:
            print(f"Error: {e}")
            self._send_json({"error": str(e)}, 500)

    def do_DELETE(self):
        """Handle DELETE /api/interview — delete conversation data."""
        if self.path == "/api/interview":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
                conversation_id = data.get("conversation_id")
                if not conversation_id:
                    self._send_json({"error": "No conversation_id provided"}, 400)
                    return

                if conversation_id in _sessions:
                    # Save transcript before deleting (for their records)
                    _sessions[conversation_id].save_transcript()
                    del _sessions[conversation_id]
                    self._send_json({"status": "deleted", "conversation_id": conversation_id})
                else:
                    self._send_json({"status": "not_found", "conversation_id": conversation_id})
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON"}, 400)
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_GET(self):
        """Handle GET /api/health."""
        if self.path == "/api/health":
            self._send_json({"status": "ok", "model": MODEL_ID})
        else:
            self._send_json({"error": "Not found"}, 404)


# ── Server ───────────────────────────────────────────────────────────────

def run_server(port: int):
    """Start the HTTP server."""
    server = HTTPServer(("0.0.0.0", port), InterviewHandler)
    print(f"Life Story Interviewer server running on port {port}")
    print(f"Model: {MODEL_ID}")
    print(f"Health check: http://localhost:{port}/api/health")
    print(f"API endpoint: POST http://localhost:{port}/api/interview")
    print()
    print("Press Ctrl+C to stop.")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        # Save all transcripts
        for cid, session in _sessions.items():
            session.save_transcript()
        server.server_close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Life Story Interviewer Server")
    parser.add_argument("--port", type=int, default=PORT, help="Port to listen on")
    parser.add_argument("--model", default=MODEL_ID, help="Model ID to use")
    args = parser.parse_args()

    MODEL_ID = args.model
    run_server(args.port)
