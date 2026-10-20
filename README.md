# cc-dash

Local web dashboard for the Claude Code sessions running on this machine: how many there are, which are busy, and what each one is doing.

```bash
python3 cc-dash.py            # http://127.0.0.1:7777
python3 cc-dash.py --port 8080
```

No dependencies beyond the Python 3 standard library. Binds to `127.0.0.1` only, because transcripts can contain sensitive content.

## Usage

- Cards refresh every 2 s; busy sessions sort first.
- Click a card (or Enter) to open its detail: the recent main-thread conversation with prompts and replies rendered as Markdown, and tool calls as expandable input/result blocks. The detail refreshes every 3 s and follows the bottom while you are there.
- `#s=<sessionId>` in the URL deep-links to a session's detail.
- Markdown uses marked + DOMPurify from cdnjs; offline it falls back to plain text.

## Data sources

| Source | Used for |
|---|---|
| `~/.claude/sessions/<pid>.json` | Live session registry: name, cwd, `busy`/`idle` status, start time, version. Entries whose pid is gone are skipped. |
| `~/.claude/projects/*/<sessionId>.jsonl` (last 512 KB) | AI title, last prompt, last tool call (and whether it is still running), last reply, PR link |
| Same transcript, last 4 MB (detail view) | Last 150 prompts / replies / tool calls; tool input and output clipped to 4000 chars |
| `git -C <cwd> branch --show-current` | Branch, cached 30 s |

Both Claude Code files are internal and undocumented; fields may change across versions, so parsing is tolerant and missing fields render empty.

## Hooks: "needs approval" / "has a question"

The session registry only says busy/idle. `hook.py` fills the gap: Claude Code runs it on hook events and it keeps `~/.claude/cc-dash/state/<sessionId>.json` while a session waits on you.

| Event | Effect |
|---|---|
| `PermissionRequest`, `Notification` (`permission_prompt`) | waiting: permission (tool + description) |
| `PreToolUse` on `AskUserQuestion`, `Notification` (`elicitation_dialog`) | waiting: question |
| `PostToolUse`, `PostToolUseFailure`, `PermissionDenied`, `UserPromptSubmit`, `Stop`, `SessionEnd` | cleared |

Such sessions get a red badge, sort first, and the tab title shows `(N!)`. A state older than the session's last switch to idle is ignored, which covers pressing Esc on a prompt.

Install: add this to `hooks` in `~/.claude/settings.json` for each event above (`"matcher": "AskUserQuestion"` on `PreToolUse`). `async` keeps it off the critical path; the script always exits 0.

```json
{ "hooks": [{ "type": "command", "command": "python3 -I /path/to/cc-dash/hook.py", "async": true, "timeout": 5 }] }
```

## Next ideas

- Click a card to focus that terminal tab
