#!/usr/bin/env python3
"""cc-dash: local web dashboard for running Claude Code sessions.

Reads ~/.claude/sessions/<pid>.json (live session registry) and the tail of each
session's transcript (~/.claude/projects/*/<sessionId>.jsonl). Both are internal,
undocumented Claude Code files, so every field is read defensively.

Usage: python3 cc-dash.py [--port 7777]
"""
import argparse
import glob
import json
import os
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CLAUDE_DIR = os.path.expanduser("~/.claude")
SESSIONS_DIR = os.path.join(CLAUDE_DIR, "sessions")
PROJECTS_DIR = os.path.join(CLAUDE_DIR, "projects")
TAIL_BYTES = 512 * 1024
BRANCH_TTL = 30  # seconds

_branch_cache = {}  # cwd -> (expires_at, branch)


def pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True
    except (OSError, ValueError, TypeError):
        return False


def git_branch(cwd):
    now = time.time()
    hit = _branch_cache.get(cwd)
    if hit and hit[0] > now:
        return hit[1]
    branch = None
    try:
        out = subprocess.run(
            ["git", "-C", cwd, "branch", "--show-current"],
            capture_output=True, text=True, timeout=2,
        )
        if out.returncode == 0:
            branch = out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        pass
    _branch_cache[cwd] = (now + BRANCH_TTL, branch)
    return branch


def find_transcript(session_id):
    if not session_id:
        return None
    matches = glob.glob(os.path.join(PROJECTS_DIR, "*", f"{session_id}.jsonl"))
    return max(matches, key=os.path.getmtime) if matches else None


def tail_lines(path):
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - TAIL_BYTES))
        data = f.read()
    lines = data.split(b"\n")
    if size > TAIL_BYTES:
        lines = lines[1:]  # first line is likely cut in half
    out = []
    for raw in lines:
        try:
            out.append(json.loads(raw))
        except (ValueError, UnicodeDecodeError):
            continue
    return out


def summarize_tool_input(name, inp):
    if not isinstance(inp, dict):
        return ""
    for key in ("description", "command", "file_path", "pattern", "url", "query", "prompt", "skill"):
        val = inp.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def first_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                return block["text"]
    return None


def parse_transcript(path):
    info = {
        "title": None, "lastPrompt": None, "lastReply": None, "lastTool": None,
        "toolPending": False, "pr": None, "lastActivity": None, "mode": None,
    }
    try:
        entries = tail_lines(path)
        info["lastActivity"] = os.path.getmtime(path) * 1000
    except OSError:
        return info

    pending = {}  # tool_use_id -> tool summary
    for e in entries:
        if not isinstance(e, dict):
            continue
        t = e.get("type")
        if t == "ai-title" and e.get("aiTitle"):
            info["title"] = e["aiTitle"]
        elif t == "last-prompt" and e.get("lastPrompt"):
            info["lastPrompt"] = e["lastPrompt"]
        elif t == "pr-link" and e.get("prUrl"):
            info["pr"] = {"url": e["prUrl"], "number": e.get("prNumber")}
        elif t == "mode" and e.get("mode"):
            info["mode"] = e["mode"]
        elif t in ("assistant", "user") and not e.get("isSidechain"):
            content = (e.get("message") or {}).get("content")
            if t == "assistant":
                text = first_text(content)
                if text:
                    info["lastReply"] = text
                for block in content if isinstance(content, list) else []:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool = {
                            "name": block.get("name"),
                            "detail": summarize_tool_input(block.get("name"), block.get("input")),
                        }
                        info["lastTool"] = tool
                        if block.get("id"):
                            pending[block["id"]] = tool
            else:
                for block in content if isinstance(content, list) else []:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        pending.pop(block.get("tool_use_id"), None)
    info["toolPending"] = bool(pending)
    return info


def collect_sessions():
    sessions = []
    for path in glob.glob(os.path.join(SESSIONS_DIR, "*.json")):
        try:
            with open(path) as f:
                reg = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(reg, dict):
            continue
        pid = reg.get("pid") or os.path.basename(path).split(".")[0]
        if not pid_alive(pid):
            continue
        cwd = reg.get("cwd") or ""
        transcript = find_transcript(reg.get("sessionId"))
        s = {
            "pid": pid,
            "sessionId": reg.get("sessionId"),
            "name": reg.get("name"),
            "cwd": cwd,
            "branch": git_branch(cwd) if cwd else None,
            "status": reg.get("status") or "unknown",
            "statusUpdatedAt": reg.get("statusUpdatedAt") or reg.get("updatedAt"),
            "startedAt": reg.get("startedAt"),
            "version": reg.get("version"),
            "kind": reg.get("kind"),
        }
        if transcript:
            s.update(parse_transcript(transcript))
        sessions.append(s)
    return sessions


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/sessions"):
            body = json.dumps({"now": time.time() * 1000, "sessions": collect_sessions()}).encode()
            ctype = "application/json"
        elif self.path in ("/", "/index.html"):
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"), "rb") as f:
                body = f.read()
            ctype = "text/html; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=7777)
    args = ap.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"cc-dash on http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
