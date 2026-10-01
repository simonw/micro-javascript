"""
micro-javascript - A Pure Python JavaScript Sandbox Engine

A sandboxed JavaScript execution environment with memory and time limits,
implemented entirely in Python with no external dependencies.

Based on: https://github.com/bellard/mquickjs
"""

from importlib.metadata import PackageNotFoundError, version as _version

try:
    __version__ = _version("micro-javascript")
except PackageNotFoundError:  # Running from an uninstalled source checkout
    __version__ = "unknown"

from .context import Context, JSContext
from .errors import JSError, JSSyntaxError, MemoryLimitError, TimeLimitError
from .values import UNDEFINED, NULL

__all__ = [
    "Context",
    "JSError",
    "JSSyntaxError",
    "MemoryLimitError",
    "TimeLimitError",
    "UNDEFINED",
    "NULL",
]
