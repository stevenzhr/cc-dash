# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running

- Run with `python3 cc-dash.py [--port N]`; files aren't executable. Serves on 127.0.0.1:7777.
- Lint with `uvx ruff check .`.
- `index.html` is read from disk per request: edits need only a browser reload. `cc-dash.py` edits need a server restart.
- `hook.py` runs fresh per event, and `~/.claude/settings.json` references it by path, so moving or renaming it breaks installed hooks.
- Paths are hardcoded to the real `~/.claude`, with no fixture dir. Piping test JSON into `hook.py` writes real state files to `~/.claude/cc-dash/state/`, so remove them afterwards.

## Conventions

- Stay stdlib-only and build-free by default; add a dependency only with clear justification. `hook.py` runs under `python3 -I`, so it must stay stdlib-only regardless.
- Target modern Python and keep non-macOS working. Known gaps: this Mac's `python3` is 3.9.6, so 3.10+ syntax breaks here until it's upgraded, and `/api/focus` doesn't catch a missing `osascript`.
- No tests exist yet. Add stdlib `unittest` coverage for new parsing logic, and also verify by running the server and checking the page or curling the endpoints.
- Commit directly to main. Subjects are imperative, sentence case, no period, no conventional-commit prefix, and name the user-visible change. Update the README in the same commit when documented behavior changes.

## hook.py

- It must always exit 0 and swallow errors; failures are silent by design.
- `classify()` has three outcomes: a dict sets state, `None` clears it, `...` leaves it untouched.
- It shares no code with `cc-dash.py`. `SESSION_ID_RE` and the tool-input summarizer are duplicated, so check both files when changing either. `since` is epoch milliseconds, compared against the registry's `statusUpdatedAt`.

## Claude Code's files

The server parses Claude Code's undocumented session registry and transcripts, so parse defensively and let missing fields render empty.

- `session_image` searches for the raw bytes `"uuid":"<id>"` to avoid parsing large base64 lines; this relies on compact JSON.
- Cards parse only the last 512 KB of a transcript; the detail view parses the whole file. Keep these paths distinct.

## Frontend

- `#grid` is rebuilt via `innerHTML` every 2 s, so delegate handlers on `grid` and don't rely on per-card DOM state.
- Pass interpolated values through `esc()` and markdown through `md()` (DOMPurify).
- The dark palette is repeated in the media query and `[data-theme="dark"]`, so change colors in every copy.

## Security

Transcripts are sensitive; preserve these:

- Bind to 127.0.0.1 only.
- POST requires the `X-CC-Dash: 1` header (CSRF guard).
- Validate IDs with `SESSION_ID_RE` before using them in a path or glob.
- Pass the tty to `osascript` as argv, never spliced into the script.
