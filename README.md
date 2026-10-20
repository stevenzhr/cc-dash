# cc-dash

Local web dashboard for the Claude Code sessions running on this machine: how many there are, which are busy, and what each one is doing.

```bash
python3 cc-dash.py            # http://127.0.0.1:7777
python3 cc-dash.py --port 8080
```

No dependencies beyond the Python 3 standard library. Binds to `127.0.0.1` only, because transcripts can contain sensitive content.

## Data sources

| Source | Used for |
|---|---|
| `~/.claude/sessions/<pid>.json` | Live session registry: name, cwd, `busy`/`idle` status, start time, version. Entries whose pid is gone are skipped. |
| `~/.claude/projects/*/<sessionId>.jsonl` (last 512 KB) | AI title, last prompt, last tool call (and whether it is still running), last reply, PR link, permission mode |
| `git -C <cwd> branch --show-current` | Branch, cached 30 s |

Both Claude Code files are internal and undocumented; fields may change across versions, so parsing is tolerant and missing fields render empty.

## Next ideas

- Hooks (`UserPromptSubmit` / `PreToolUse` / `Stop` / `Notification`) posting events, to show "waiting for permission" precisely
- Click a card to focus that terminal tab
