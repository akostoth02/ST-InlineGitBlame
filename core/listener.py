import sublime
import sublime_plugin
import time
import webbrowser

from .constants import (
    PHANTOM_KEY,
    SUMMARY_MAX_LENGTH,
    SUMMARY_ELLIPSIS_LENGTH,
    DEFAULT_SPACING_CHARS,
    MIN_SPACING_CHARS,
    DEFAULT_ALIGN_COLUMN,
    DEFAULT_TAB_SIZE,
    LOAD_DELAY_MS,
    UNCOMMITTED_SHA_PREFIX,
    POPUP_MAX_WIDTH,
    POPUP_MAX_HEIGHT,
)
from .utils import get_settings, is_startup_complete, relative_time, log
from .git import find_git_root, get_remote_url, run_blame, get_commit_details
from .templates import render_blame_phantom, render_details_popup


_listeners = {}


class InlineGitBlameListener(sublime_plugin.ViewEventListener):
    def __init__(self, view):
        super().__init__(view)
        self.phantom_set = sublime.PhantomSet(view, PHANTOM_KEY)
        self._last_row = -1
        self._cache = {}
        self._git_root = None
        self._remote_url = None
        self._ignore_next_selection = False
        _listeners[view.id()] = self

    @classmethod
    def is_applicable(cls, settings):
        return get_settings().get("enabled", True)

    def on_load_async(self):
        if get_settings().get("enabled", True):
            if is_startup_complete():
                self._update_blame()
            else:
                sublime.set_timeout_async(self._update_blame, LOAD_DELAY_MS)

    def on_activated_async(self):
        if get_settings().get("enabled", True):
            self._update_blame()

    def on_selection_modified_async(self):
        if self._ignore_next_selection:
            self._ignore_next_selection = False
            return

        if not get_settings().get("enabled", True):
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
            self._git_root = find_git_root(file_path)
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
            self._cache = run_blame(file_path, self._git_root)

        info = self._cache.get(line_num)
        if not info or info["sha"].startswith(UNCOMMITTED_SHA_PREFIX):
            self.phantom_set.update([])
            return

        line_region = self.view.line(self.view.text_point(row, 0))
        if line_region.empty():
            self.phantom_set.update([])
            return

        self._show_phantom(info, line_region.end(), cursor_pos)

    def _show_phantom(self, info, line_end, cursor_pos):
        author = info.get("author", "Unknown")
        timestamp = info.get("author_time", 0)
        summary = info.get("summary", "")
        sha = info.get("sha", "")

        settings = get_settings()
        date_format = settings.get("date_format", "relative")
        if date_format == "relative":
            date_str = relative_time(timestamp)
        else:
            date_str = time.strftime("%Y-%m-%d", time.localtime(timestamp))

        if len(summary) > SUMMARY_MAX_LENGTH:
            summary = summary[:SUMMARY_ELLIPSIS_LENGTH] + "..."

        alignment = settings.get("phantom_alignment", "start")
        spacing_html = "&nbsp;" * DEFAULT_SPACING_CHARS

        if alignment == "end":
            align_column = settings.get("phantom_align_column", 0)
            if align_column <= 0:
                rulers = self.view.settings().get("rulers", [])
                align_column = int(rulers[-1]) if rulers else DEFAULT_ALIGN_COLUMN
            line_region = self.view.line(line_end)
            line_text = self.view.substr(line_region)
            tab_size = self.view.settings().get("tab_size", DEFAULT_TAB_SIZE)
            visual_col = 0
            for ch in line_text:
                if ch == "\t":
                    visual_col += tab_size - (visual_col % tab_size)
                else:
                    visual_col += 1
            padding_chars = max(MIN_SPACING_CHARS, align_column - visual_col)
            spacing_html = "&nbsp;" * padding_chars

        html = render_blame_phantom(author, date_str, sha, summary, spacing_html)

        phantom = sublime.Phantom(
            sublime.Region(line_end, line_end),
            html,
            sublime.LAYOUT_INLINE,
            on_navigate=self._on_navigate
        )
        self.phantom_set.update([phantom])

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
        details = get_commit_details(sha, self._git_root)
        if not details:
            details = {
                "sha": sha,
                "author": "Unknown",
                "email": "",
                "date": "",
                "subject": "",
                "body": "",
            }

        if self._remote_url is None:
            self._remote_url = get_remote_url(self._git_root) or ""

        html = render_details_popup(
            subject=details["subject"],
            sha=details["sha"],
            author=details["author"],
            email=details["email"],
            date=details["date"],
            body=details["body"],
            remote_url=self._remote_url,
        )

        self.view.show_popup(
            html,
            sublime.COOPERATE_WITH_AUTO_COMPLETE,
            max_width=POPUP_MAX_WIDTH,
            max_height=POPUP_MAX_HEIGHT,
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
