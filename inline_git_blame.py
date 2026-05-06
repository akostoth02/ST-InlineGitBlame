import sublime
import sublime_plugin
import subprocess
import os
import re
import time
import webbrowser


def plugin_loaded():
    pass


def _get_settings():
    return sublime.load_settings("InlineGitBlame.sublime-settings")


def _relative_time(timestamp):
    now = time.time()
    diff = int(now - timestamp)

    if diff < 60:
        return "just now"
    elif diff < 3600:
        mins = diff // 60
        return f"{mins} min{'s' if mins != 1 else ''} ago"
    elif diff < 86400:
        hours = diff // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff < 2592000:
        days = diff // 86400
        return f"{days} day{'s' if days != 1 else ''} ago"
    elif diff < 31536000:
        months = diff // 2592000
        return f"{months} month{'s' if months != 1 else ''} ago"
    else:
        years = diff // 31536000
        return f"{years} year{'s' if years != 1 else ''} ago"


def _find_git_root(file_path):
    directory = os.path.dirname(file_path)
    while True:
        if os.path.isdir(os.path.join(directory, ".git")):
            return directory
        parent = os.path.dirname(directory)
        if parent == directory:
            return None
        directory = parent


def _get_remote_url(git_root):
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
            cwd=git_root
        )
        url = result.stdout.strip()
        url = re.sub(r"\.git$", "", url)
        url = re.sub(r"^git@([^:]+):", r"https://\1/", url)
        return url
    except Exception:
        return None


def _parse_blame_porcelain(output):
    if not output.strip():
        return None

    lines = output.strip().split("\n")
    info = {}

    first_line = lines[0].split()
    info["sha"] = first_line[0]

    for line in lines[1:]:
        if line.startswith("author "):
            info["author"] = line[7:]
        elif line.startswith("author-mail "):
            info["author_mail"] = line[12:]
        elif line.startswith("author-time "):
            info["author_time"] = int(line[12:])
        elif line.startswith("summary "):
            info["summary"] = line[8:]

    return info


class InlineGitBlameListener(sublime_plugin.ViewEventListener):
    def __init__(self, view):
        super().__init__(view)
        self.phantom_set = sublime.PhantomSet(view, "inline_git_blame")
        self._pending = False
        self._last_row = -1
        self._cache = {}
        self._git_root = None
        self._remote_url = None

    @classmethod
    def is_applicable(cls, settings):
        return _get_settings().get("enabled", True)

    def on_selection_modified_async(self):
        if not _get_settings().get("enabled", True):
            self.phantom_set.update([])
            return

        sel = self.view.sel()
        if not sel:
            return

        row, _ = self.view.rowcol(sel[0].begin())
        if row == self._last_row:
            return
        self._last_row = row

        if not self._pending:
            self._pending = True
            delay = _get_settings().get("delay_ms", 300)
            sublime.set_timeout_async(self._update_blame, delay)

    def on_close(self):
        self._cache.clear()

    def on_post_save_async(self):
        self._cache.clear()
        self._update_blame()

    def _update_blame(self):
        self._pending = False
        file_path = self.view.file_name()
        if not file_path or self.view.is_dirty() and not _get_settings().get("show_uncommitted", True):
            self.phantom_set.update([])
            return

        if self._git_root is None:
            self._git_root = _find_git_root(file_path)
        if not self._git_root:
            self.phantom_set.update([])
            return

        sel = self.view.sel()
        if not sel:
            return

        row, _ = self.view.rowcol(sel[0].begin())
        line_num = row + 1

        if line_num in self._cache:
            info = self._cache[line_num]
        else:
            info = self._run_blame(file_path, line_num)
            self._cache[line_num] = info

        if not info or info["sha"].startswith("0000000"):
            self.phantom_set.update([])
            return

        self._show_phantom(info, row)

    def _run_blame(self, file_path, line_num):
        try:
            result = subprocess.run(
                ["git", "blame", "--porcelain", f"-L{line_num},{line_num}", "--", file_path],
                capture_output=True, text=True, timeout=5,
                cwd=self._git_root
            )
            if result.returncode != 0:
                return None
            return _parse_blame_porcelain(result.stdout)
        except Exception:
            return None

    def _show_phantom(self, info, row):
        region = self.view.line(self.view.text_point(row, 0))
        end = region.end()

        author = info.get("author", "Unknown")
        timestamp = info.get("author_time", 0)
        summary = info.get("summary", "")
        sha = info.get("sha", "")

        date_format = _get_settings().get("date_format", "relative")
        if date_format == "relative":
            date_str = _relative_time(timestamp)
        else:
            date_str = time.strftime("%Y-%m-%d", time.localtime(timestamp))

        if len(summary) > 50:
            summary = summary[:47] + "..."

        style = _get_settings().get("style", {})
        color = style.get("color", "color(var(--foreground) alpha(0.4))")
        font_style = style.get("font_style", "italic")

        html = (
            f'<body id="inline-git-blame">'
            f'<style>'
            f'  span {{ color: {color}; font-style: {font_style}; padding-left: 4em; font-size: 0.9em; }}'
            f'  a {{ color: {color}; text-decoration: none; }}'
            f'  a:hover {{ text-decoration: underline; }}'
            f'</style>'
            f'<span>'
            f'{author}, {date_str} '
            f'<a href="details:{sha}">({sha[:7]})</a>'
            f' \u2014 {sublime.html.escape(summary)}'
            f'</span>'
            f'</body>'
        )

        phantom = sublime.Phantom(
            sublime.Region(end, end),
            html,
            sublime.LAYOUT_INLINE,
            on_navigate=self._on_navigate
        )
        self.phantom_set.update([phantom])

    def _on_navigate(self, href):
        if href.startswith("details:"):
            sha = href[8:]
            self._show_details_popup(sha)

    def _show_details_popup(self, sha):
        try:
            result = subprocess.run(
                ["git", "show", "--no-patch", "--format=%H%n%an%n%ae%n%ai%n%s%n%b", sha],
                capture_output=True, text=True, timeout=5,
                cwd=self._git_root
            )
            if result.returncode != 0:
                return

            lines = result.stdout.strip().split("\n")
            full_sha = lines[0] if len(lines) > 0 else sha
            author = lines[1] if len(lines) > 1 else "Unknown"
            email = lines[2] if len(lines) > 2 else ""
            date = lines[3] if len(lines) > 3 else ""
            subject = lines[4] if len(lines) > 4 else ""
            body = "\n".join(lines[5:]).strip() if len(lines) > 5 else ""

        except Exception:
            full_sha = sha
            author = "Unknown"
            email = ""
            date = ""
            subject = ""
            body = ""

        if self._remote_url is None:
            self._remote_url = _get_remote_url(self._git_root) or ""

        open_link = ""
        if self._remote_url:
            commit_url = f"{self._remote_url}/commit/{full_sha}"
            open_link = f'<a href="open:{commit_url}">Open in browser</a>'

        copy_link = f'<a href="copy:{full_sha}">Copy SHA</a>'

        body_html = ""
        if body:
            body_html = f'<p style="margin-top: 8px; white-space: pre-wrap;">{sublime.html.escape(body)}</p>'

        html = (
            f'<body id="inline-git-blame-popup">'
            f'<style>'
            f'  body {{ padding: 8px; font-size: 0.9em; }}'
            f'  h3 {{ margin: 0 0 4px 0; }}'
            f'  .meta {{ color: color(var(--foreground) alpha(0.7)); margin: 2px 0; }}'
            f'  .sha {{ font-family: monospace; }}'
            f'  .actions {{ margin-top: 8px; }}'
            f'  .actions a {{ margin-right: 12px; }}'
            f'</style>'
            f'<h3>{sublime.html.escape(subject)}</h3>'
            f'<p class="meta"><span class="sha">{full_sha[:12]}</span></p>'
            f'<p class="meta">{sublime.html.escape(author)} &lt;{sublime.html.escape(email)}&gt;</p>'
            f'<p class="meta">{sublime.html.escape(date)}</p>'
            f'{body_html}'
            f'<div class="actions">{copy_link} {open_link}</div>'
            f'</body>'
        )

        self.view.show_popup(
            html,
            sublime.COOPERATE_WITH_AUTO_COMPLETE,
            max_width=700,
            max_height=400,
            on_navigate=self._on_popup_navigate
        )

    def _on_popup_navigate(self, href):
        if href.startswith("open:"):
            url = href[5:]
            webbrowser.open(url)
        elif href.startswith("copy:"):
            sha = href[5:]
            sublime.set_clipboard(sha)
            sublime.status_message(f"Copied {sha[:12]} to clipboard")


class InlineGitBlameToggleCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        settings = _get_settings()
        current = settings.get("enabled", True)
        settings.set("enabled", not current)
        sublime.save_settings("InlineGitBlame.sublime-settings")
        state = "enabled" if not current else "disabled"
        sublime.status_message(f"Inline Git Blame {state}")

        if current:
            for window in sublime.windows():
                for view in window.views():
                    ps = sublime.PhantomSet(view, "inline_git_blame")
                    ps.update([])


class InlineGitBlameClearCacheCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        sublime.status_message("Inline Git Blame cache cleared")
