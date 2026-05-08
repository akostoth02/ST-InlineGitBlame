import subprocess
import os
import re

from .constants import BLAME_TIMEOUT_SECS, GIT_TIMEOUT_SECS
from .utils import STARTUP_INFO


def find_git_root(file_path):
    directory = os.path.dirname(file_path)
    while True:
        if os.path.isdir(os.path.join(directory, ".git")):
            return directory
        parent = os.path.dirname(directory)
        if parent == directory:
            return None
        directory = parent


def get_remote_url(git_root):
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=GIT_TIMEOUT_SECS,
            cwd=git_root,
            startupinfo=STARTUP_INFO
        )
        url = result.stdout.strip()
        url = re.sub(r"\.git$", "", url)
        url = re.sub(r"^git@([^:]+):", r"https://\1/", url)
        return url
    except Exception:
        return None


def parse_blame_porcelain(output):
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


def run_blame(file_path, git_root):
    try:
        result = subprocess.run(
            ["git", "blame", "--porcelain", "--", file_path],
            capture_output=True, text=True, timeout=BLAME_TIMEOUT_SECS,
            cwd=git_root,
            startupinfo=STARTUP_INFO
        )
        if result.returncode != 0:
            return {}
        return parse_blame_porcelain(result.stdout)
    except Exception:
        return {}


def get_commit_details(sha, git_root):
    try:
        result = subprocess.run(
            ["git", "show", "--no-patch", "--format=%H%n%an%n%ae%n%ai%n%s%n%b", sha],
            capture_output=True, text=True, timeout=GIT_TIMEOUT_SECS,
            cwd=git_root,
            startupinfo=STARTUP_INFO
        )
        if result.returncode != 0:
            return None

        lines = result.stdout.strip().split("\n")
        return {
            "sha": lines[0] if len(lines) > 0 else sha,
            "author": lines[1] if len(lines) > 1 else "Unknown",
            "email": lines[2] if len(lines) > 2 else "",
            "date": lines[3] if len(lines) > 3 else "",
            "subject": lines[4] if len(lines) > 4 else "",
            "body": "\n".join(lines[5:]).strip() if len(lines) > 5 else "",
        }
    except Exception:
        return None
