import sublime
import sublime_plugin
import subprocess
import os
import re
import time
import webbrowser
import traceback


_STARTUP_INFO = None
if os.name == "nt":
    _STARTUP_INFO = subprocess.STARTUPINFO()
    _STARTUP_INFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    _STARTUP_INFO.wShowWindow = subprocess.SW_HIDE


_PREFIX = "InlineGitBlame"


def _log(msg):
    print(f"[{_PREFIX}] {msg}")


def _log_error(msg):
    print(f"[{_PREFIX}] ERROR: {msg}")
    traceback.print_exc()


_startup_complete = False


def plugin_loaded():
    global _startup_complete
    sublime.set_timeout(lambda: _set_startup_complete(), 1000)


def _set_startup_complete():
    global _startup_complete
    _startup_complete = True


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
            cwd=git_root,
            startupinfo=_STARTUP_INFO
        )
        url = result.stdout.strip()
        url = re.sub(r"\.git$", "", url)
        url = re.sub(r"^git@([^:]+):", r"https://\1/", url)
        return url
    except Exception:
        return None


def _parse_blame_porcelain(output):
    if not output.strip():
        return {}

    result = {}
    commits = {}
    lines = output.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        parts = line.split()
        if not parts:
            i += 1
            continue

        if len(parts) >= 3 and len(parts[0]) == 40:
            sha = parts[0]
            line_num = int(parts[2])
            info = {"sha": sha}

            i += 1
            while i < len(lines):
                l = lines[i]
                if l.startswith("\t"):
                    i += 1
                    break
                elif l.startswith("author "):
                    info["author"] = l[7:]
                elif l.startswith("author-mail "):
                    info["author_mail"] = l[12:]
                elif l.startswith("author-time "):
                    info["author_time"] = int(l[12:])
                elif l.startswith("summary "):
                    info["summary"] = l[8:]
                i += 1

            if "author" in info:
                commits[sha] = info
            elif sha in commits:
                info = dict(commits[sha])
                info["sha"] = sha

            result[line_num] = info
        else:
            i += 1

    return result


_listeners = {}


class InlineGitBlameListener(sublime_plugin.ViewEventListener):
    def __init__(self, view):
        super().__init__(view)
        self.phantom_set = sublime.PhantomSet(view, "inline_git_blame")
        self._last_row = -1
        self._cache = {}
        self._git_root = None
        self._remote_url = None
        self._ignore_next_selection = False
        _listeners[view.id()] = self

    @classmethod
    def is_applicable(cls, settings):
        return _get_settings().get("enabled", True)

    def on_load_async(self):
        if _get_settings().get("enabled", True):
            if _startup_complete:
                self._update_blame()
            else:
                sublime.set_timeout_async(self._update_blame, 500)

    def on_activated_async(self):
        if _get_settings().get("enabled", True):
            self._update_blame()

    def on_selection_modified_async(self):
        if self._ignore_next_selection:
            self._ignore_next_selection = False
            return

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

        self._update_blame()

    def on_modified_async(self):
        self.phantom_set.update([])
        self._cache.clear()

    def on_close(self):
        self._cache.clear()
        _listeners.pop(self.view.id(), None)

    def on_post_save_async(self):
        self._cache.clear()
        self._update_blame()

    def _update_blame(self):
        file_path = self.view.file_name()
        if not file_path:
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

        cursor_pos = sel[0].begin()
        row, _ = self.view.rowcol(cursor_pos)
        line_num = row + 1

        if not self._cache:
            self._cache = self._run_blame_file(file_path)

        info = self._cache.get(line_num)
        if not info or info["sha"].startswith("0000000"):
            self.phantom_set.update([])
            return

        line_region = self.view.line(self.view.text_point(row, 0))
        if line_region.empty():
            self.phantom_set.update([])
            return

        self._show_phantom(info, line_region.end(), cursor_pos)

    def _run_blame_file(self, file_path):
        try:
            result = subprocess.run(
                ["git", "blame", "--porcelain", "--", file_path],
                capture_output=True, text=True, timeout=30,
                cwd=self._git_root,
                startupinfo=_STARTUP_INFO
            )
            if result.returncode != 0:
                return {}
            return _parse_blame_porcelain(result.stdout)
        except Exception:
            return {}

    def _show_phantom(self, info, line_end, cursor_pos):
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

        html = (
            f'<body id="inline-git-blame">'
            f'<style>'
            f'  a {{ color: color(var(--foreground) alpha(0.4)); font-style: italic; padding-left: 4em; font-size: 0.9em; text-decoration: none; }}'
            f'  a:hover {{ text-decoration: underline; }}'
            f'</style>'
            f'<a href="details:{sha}">'
            f'{author}, {date_str} '
            f'({sha[:7]})'
            f' \u2014 {sublime.html.escape(summary)}'
            f'</a>'
            f'</body>'
        )

        phantom = sublime.Phantom(
            sublime.Region(line_end, line_end),
            html,
            sublime.LAYOUT_INLINE,
            on_navigate=self._on_navigate
        )
        self.phantom_set.update([phantom])

        # Restore cursor if the phantom pushed it past end of line
        sublime.set_timeout(lambda: self._restore_cursor(cursor_pos), 0)

    def _restore_cursor(self, target_pos):
        sel = self.view.sel()
        if not sel:
            return
        current_pos = sel[0].begin()
        if current_pos != target_pos:
            self._ignore_next_selection = True
            self.view.sel().clear()
            self.view.sel().add(sublime.Region(target_pos, target_pos))

    def _on_navigate(self, href):
        if href.startswith("details:"):
            sha = href[8:]
            self._show_details_popup(sha)

    def _show_details_popup(self, sha):
        try:
            result = subprocess.run(
                ["git", "show", "--no-patch", "--format=%H%n%an%n%ae%n%ai%n%s%n%b", sha],
                capture_output=True, text=True, timeout=5,
                cwd=self._git_root,
                startupinfo=_STARTUP_INFO
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


class InlineGitBlameShowDetailsCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        _log(f"ShowDetails command triggered, view_id={self.view.id()}")
        _log(f"Known listeners: {list(_listeners.keys())}")

        listener = _listeners.get(self.view.id())
        if not listener:
            _log("No listener found for this view")
            return

        sel = self.view.sel()
        if not sel:
            _log("No selection")
            return

        row, _ = self.view.rowcol(sel[0].begin())
        line_num = row + 1
        info = listener._cache.get(line_num)
        _log(f"Line {line_num}, info={info}")
        if info and not info["sha"].startswith("0000000"):
            listener._show_details_popup(info["sha"])
        else:
            _log("No blame info for this line")


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
