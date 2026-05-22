import sys

# kiss-reloader: clear stale submodules so package updates hot-reload cleanly.
# https://github.com/kaste/KissReloader
prefix = __spec__.parent + "."  # don't clear the base package
for module_name in [
    module_name
    for module_name in sys.modules
    if module_name.startswith(prefix) and module_name != __name__
]:
    del sys.modules[module_name]

from .core import *  # noqa: E402,F401,F403
