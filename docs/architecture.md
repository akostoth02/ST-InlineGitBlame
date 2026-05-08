# Architecture

This document describes the high-level architecture of the InlineGitBlame Sublime Text plugin.

## Package Structure

The plugin follows the **Sublime Text community standard** for multi-file packages (the same pattern used by LSP, GitSavvy, and Terminus):

```
InlineGitBlame/
├── inline_git_blame.py       # Entry point (ST loads this file)
├── core/                     # Internal Python package
│   ├── __init__.py           # Re-exports plugin classes
│   ├── constants.py          # Named constants and configuration defaults
│   ├── utils.py              # Shared utilities (logging, settings, timing)
│   ├── git.py                # Git subprocess operations
│   ├── templates.py          # HTML template rendering
│   ├── listener.py           # View event listener (core plugin logic)
│   └── commands.py           # Command palette commands
├── InlineGitBlame.sublime-settings
├── Default.sublime-commands
├── Default.sublime-keymap
└── ...
```

## Design Principles

### Entry Point Pattern

Sublime Text only discovers `sublime_plugin` subclasses in top-level `.py` files within the package directory. The `core/` subdirectory is **not** scanned automatically. The top-level `inline_git_blame.py` re-exports everything ST needs via `from .core import *`.

### Separation of Concerns

- **`constants.py`** — All magic numbers, strings, and default values
- **`utils.py`** — Cross-cutting utilities: logging, settings access, time formatting, platform-specific setup
- **`git.py`** — All interactions with the `git` CLI (blame, remote URL, commit details)
- **`templates.py`** — HTML generation for phantoms and popups using `string.Template`
- **`listener.py`** — Sublime Text event handling, caching, and phantom lifecycle
- **`commands.py`** — User-facing commands (toggle, show details, clear cache)

### Constants over Magic Numbers

All numeric thresholds, timeout values, display lengths, and string identifiers are defined as named constants in `constants.py`. This provides:

- A single source of truth for configuration defaults
- Self-documenting code (the name explains the purpose)
- Easy discoverability when a value needs adjustment

### Template-Based HTML

HTML for Sublime phantoms and popups is defined as `string.Template` objects in `templates.py`, separate from the logic that computes the data. This keeps rendering concerns isolated from business logic and makes the HTML structure readable and editable.

### Stateless Git Module

`git.py` contains pure functions that accept paths/arguments and return parsed data. It holds no state and has no dependency on Sublime Text APIs, making it straightforward to reason about and test in isolation.

## Data Flow

```
File opened / cursor moved
        │
        ▼
   listener.py
   (event handler)
        │
        ├── git.py: run_blame() ──► cached per file
        │
        ▼
   templates.py: render_blame_phantom()
        │
        ▼
   Sublime Phantom (LAYOUT_INLINE)
        │
        ▼ (user clicks)
        │
        ├── git.py: get_commit_details()
        │
        ▼
   templates.py: render_details_popup()
        │
        ▼
   Sublime Popup
```

## Caching Strategy

- Blame data is cached in-memory per file path within each `ViewEventListener` instance
- Cache is invalidated on file modification (edit) and refreshed on save
- Each view maintains its own independent cache (no cross-view sharing)

## Platform Considerations

On Windows, all `subprocess` calls use `STARTUPINFO` with `SW_HIDE` to prevent CMD window flashes. This is initialized once at module load in `utils.py` and shared across all git operations.
