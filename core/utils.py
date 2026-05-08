import sublime
import subprocess
import os
import time
import traceback

from .constants import (
    LOG_PREFIX,
    SETTINGS_FILE,
    STARTUP_DELAY_MS,
    SECONDS_PER_MINUTE,
    SECONDS_PER_HOUR,
    SECONDS_PER_DAY,
    SECONDS_PER_MONTH,
    SECONDS_PER_YEAR,
)


STARTUP_INFO = None
if os.name == "nt":
    STARTUP_INFO = subprocess.STARTUPINFO()
    STARTUP_INFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    STARTUP_INFO.wShowWindow = subprocess.SW_HIDE


_startup_complete = False


def plugin_loaded():
    global _startup_complete
    sublime.set_timeout(lambda: _set_startup_complete(), STARTUP_DELAY_MS)


def _set_startup_complete():
    global _startup_complete
    _startup_complete = True


def is_startup_complete():
    return _startup_complete


def get_settings():
    return sublime.load_settings(SETTINGS_FILE)


def log(msg):
    if get_settings().get("debug", False):
        print(f"[{LOG_PREFIX}] {msg}")


def log_error(msg):
    print(f"[{LOG_PREFIX}] ERROR: {msg}")
    traceback.print_exc()


def relative_time(timestamp):
    now = time.time()
    diff = int(now - timestamp)

    if diff < SECONDS_PER_MINUTE:
        return "just now"
    elif diff < SECONDS_PER_HOUR:
        mins = diff // SECONDS_PER_MINUTE
        return f"{mins} min{'s' if mins != 1 else ''} ago"
    elif diff < SECONDS_PER_DAY:
        hours = diff // SECONDS_PER_HOUR
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff < SECONDS_PER_MONTH:
        days = diff // SECONDS_PER_DAY
        return f"{days} day{'s' if days != 1 else ''} ago"
    elif diff < SECONDS_PER_YEAR:
        months = diff // SECONDS_PER_MONTH
        return f"{months} month{'s' if months != 1 else ''} ago"
    else:
        years = diff // SECONDS_PER_YEAR
        return f"{years} year{'s' if years != 1 else ''} ago"
