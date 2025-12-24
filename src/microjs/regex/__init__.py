"""
MQuickJS Regex Engine - A safe, sandboxed regular expression engine.

This module provides a custom regex implementation with:
- ReDoS protection (zero-advance detection)
- Memory limits
- Timeout integration via polling
- Feature parity with JavaScript regular expressions

Can be used standalone or integrated with the MQuickJS JavaScript engine.
"""

from .regex import (
    RegExp,
    RegExpError,
    RegexTimeoutError,
    RegexStackOverflow,
    MatchResult,
    match,
    search,
    test
)

__all__ = [
    'RegExp',
    'RegExpError',
    'RegexTimeoutError',
    'RegexStackOverflow',
    'MatchResult',
    'match',
    'search',
    'test'
]

__version__ = '0.1.0'
