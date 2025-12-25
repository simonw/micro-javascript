"""
MQuickJS Python - A Pure Python JavaScript Sandbox Engine

A sandboxed JavaScript execution environment with memory and time limits,
implemented entirely in Python with no external dependencies.

Based on: https://github.com/bellard/mquickjs
"""

__version__ = "0.1.0"

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
