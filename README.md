# Inline Git Blame

A Sublime Text 4 plugin that displays git blame information inline as a phantom at the end of the current line.

## Features

- Inline blame annotation showing author, relative date, commit SHA, and commit message
- Click the blame annotation to view full commit details in a popup
- From the popup: copy the full SHA or open the commit in your browser
- Auto-detects GitHub, GitLab, and Bitbucket remote URLs for commit links
- Automatically adapts to your current color scheme
- Blame data is cached per file for instant navigation
- Blame appears on startup for the active file

## Requirements

- Sublime Text 4 (build 4000+)
- Git installed and available in your PATH

## Installation

Coming soon via Package Control.

## Usage

Open any file that is tracked by git. The blame annotation appears inline at the end of the current line as you navigate.

### Commands

All commands are accessible via the Command Palette (`Ctrl+Shift+P`).

- **Inline Git Blame: Toggle** — Enable or disable inline blame
- **Inline Git Blame: Show Commit Details** — Show the commit details popup for the current line
- **Inline Git Blame: Clear Cache** — Clear the cached blame data for the current file

### Key Bindings

- <kbd>Ctrl+Alt+B</kbd> — Toggle inline blame
- <kbd>Ctrl+Alt+Shift+B</kbd> — Show commit details popup

To customize key bindings, go to **Preferences > Package Settings > Inline Git Blame > Key Bindings** or add entries to your user keymap:

```json
[
    { "keys": ["ctrl+alt+b"], "command": "inline_git_blame_toggle" },
    { "keys": ["ctrl+alt+shift+b"], "command": "inline_git_blame_show_details" }
]
```

## Settings

Available via **Preferences > Package Settings > Inline Git Blame > Settings**.

```json
{
    // Enable/disable inline git blame annotations
    "enabled": true,

    // Date format: "relative" (e.g. "3 days ago") or "absolute" (e.g. "2025-01-15")
    "date_format": "relative"
}
```

- **`enabled`** (boolean, default: `true`) — Enable or disable inline blame annotations
- **`date_format`** (string, default: `"relative"`) — `"relative"` for human-readable times (e.g. "3 days ago") or `"absolute"` for ISO dates (e.g. "2025-01-15")

## Commit Details Popup

Clicking the inline blame annotation (or using the keybinding) opens a popup with:

- Commit subject
- Full commit SHA (truncated for display)
- Author name and email
- Commit date
- Commit body (if present)
- **Copy SHA** — copies the full SHA to clipboard
- **Open in browser** — opens the commit on GitHub/GitLab/Bitbucket (when a remote is configured)

## How It Works

1. On first access, the plugin runs `git blame --porcelain` for the entire file and caches the results
2. As you navigate between lines, blame info is looked up instantly from the cache
3. The cache is cleared when the file is modified or saved, triggering a fresh blame on the next navigation
4. The annotation is rendered as a Sublime Text phantom (`LAYOUT_INLINE`) at the end of the current line

## Troubleshooting

If the plugin doesn't work as expected, open the Sublime Text console (`` Ctrl+` ``) and look for messages prefixed with `[InlineGitBlame]`.

Common issues:

- **No blame appears**: Ensure the file is tracked by git and has at least one commit. Newly created or untracked files won't show blame.
- **Empty lines**: Blame is not shown on empty lines by design, as there is no content to annotate.
- **CMD windows flashing (Windows)**: This should not happen. If it does, please file an issue.

## Commit Convention

Commit messages are prefixed with a tag indicating the type of change:

- **`[FEATURE]`** — New functionality
- **`[FIX]`** — Bug fix
- **`[REFACTOR]`** — Code restructuring without behavior change
- **`[DOCS]`** — Documentation only
- **`[CHORE]`** — Maintenance, config, dependencies, tooling
- **`[STYLE]`** — Formatting, whitespace, cosmetic changes
- **`[TEST]`** — Adding or updating tests

Example: `[FEATURE] Add support for Bitbucket Server remote URLs`

## Releasing

This project uses tag-based releases with semantic versioning.

To cut a new release:

1. Add a version entry to `messages.json`:
   ```json
   "1.1.0": "messages/1.1.0.txt"
   ```
2. Create `messages/<version>.txt` with release notes
3. Commit the changes
4. Create a signed annotated tag:
   ```
   git tag -a 1.1.0 -m "Short description of the release"
   ```
5. Push the commit and tag:
   ```
   git push origin main --tags
   ```

Package Control picks up new tags automatically.

## License

MIT
