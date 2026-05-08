import sublime
import sublime_plugin

from .constants import PHANTOM_KEY, SETTINGS_FILE
from .utils import get_settings, log
from .listener import _listeners


class InlineGitBlameToggleCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        settings = get_settings()
        current = settings.get("enabled", True)
        settings.set("enabled", not current)
        sublime.save_settings(SETTINGS_FILE)
        state = "enabled" if not current else "disabled"
        sublime.status_message(f"Inline Git Blame {state}")

        if current:
            for window in sublime.windows():
                for view in window.views():
                    ps = sublime.PhantomSet(view, PHANTOM_KEY)
                    ps.update([])


class InlineGitBlameShowDetailsCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        log(f"ShowDetails command triggered, view_id={self.view.id()}")
        log(f"Known listeners: {list(_listeners.keys())}")

        listener = _listeners.get(self.view.id())
        if not listener:
            log("No listener found for this view")
            return

        sel = self.view.sel()
        if not sel:
            log("No selection")
            return

        row, _ = self.view.rowcol(sel[0].begin())
        line_num = row + 1
        info = listener._cache.get(line_num)
        log(f"Line {line_num}, info={info}")
        if info and not info["sha"].startswith("0000000"):
            listener._show_details_popup(info["sha"])
        else:
            log("No blame info for this line")


class InlineGitBlameClearCacheCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        sublime.status_message("Inline Git Blame cache cleared")
