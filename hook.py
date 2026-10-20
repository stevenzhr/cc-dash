#!/usr/bin/env python3
"""Claude Code hook for cc-dash: records when a session is waiting on the user.

Wired to several hook events in ~/.claude/settings.json. Reads the hook JSON on
stdin and keeps one small file per session in ~/.claude/cc-dash/state/:

  PermissionRequest                          -> waiting: permission
  Notification (permission_prompt)           -> waiting: permission
  Notification (elicitation_dialog)          -> waiting: question
  PreToolUse (AskUserQuestion)               -> waiting: question
  PostToolUse / PostToolUseFailure /
  PermissionDenied / UserPromptSubmit /
  Stop / SessionEnd                          -> cleared

Never fails the hook: any error exits 0 silently.
"""
import json
import os
import re
import sys
import time

STATE_DIR = os.path.expanduser("~/.claude/cc-dash/state")
SESSION_ID_RE = re.compile(r"^[0-9a-fA-F-]{8,64}$")
CLEAR_EVENTS = {
    "PostToolUse", "PostToolUseFailure", "PermissionDenied",
    "UserPromptSubmit", "Stop", "SessionEnd",
}


def tool_detail(inp):
    if not isinstance(inp, dict):
        return ""
    for key in ("description", "command", "file_path", "pattern", "url", "query", "prompt"):
        val = inp.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()[:300]
    return ""


def classify(ev):
    """Return a waiting-state dict, None to clear, or ... to leave state untouched."""
    name = ev.get("hook_event_name")
    if name == "PermissionRequest":
        return {"waiting": "permission", "tool": ev.get("tool_name"),
                "detail": tool_detail(ev.get("tool_input"))}
    if name == "PreToolUse":
        if ev.get("tool_name") == "AskUserQuestion":
            return {"waiting": "question", "tool": "AskUserQuestion", "detail": ""}
        return ...
    if name == "Notification":
        ntype = ev.get("notification_type") or ""
        msg = ev.get("message") or ""
        if ntype == "permission_prompt" or (not ntype and "permission" in msg.lower()):
            return {"waiting": "permission", "message": msg}
        if ntype == "elicitation_dialog":
            return {"waiting": "question", "message": msg}
        return ...  # e.g. idle_prompt: registry status already covers idle
    if name in CLEAR_EVENTS:
        return None
    return ...


def main():
    ev = json.load(sys.stdin)
    sid = ev.get("session_id") or ""
    if not SESSION_ID_RE.match(sid):
        return
    state = classify(ev)
    if state is ...:
        return
    path = os.path.join(STATE_DIR, sid + ".json")
    if state is None:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        return
    if state.get("tool") is None and os.path.exists(path):
        # A Notification right after PermissionRequest: keep the richer tool info.
        try:
            with open(path) as f:
                prev = json.load(f)
            if prev.get("waiting") == state["waiting"]:
                prev["message"] = state.get("message") or prev.get("message")
                state = prev
        except (OSError, ValueError):
            pass
    state.setdefault("since", time.time() * 1000)
    state["sessionId"] = sid
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, path)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
