"""
Main regex module - public interface.

Provides JavaScript-compatible RegExp with ReDoS protection.
"""

from typing import Optional, Callable, List
from .parser import RegexParser, RegExpError
from .compiler import RegexCompiler
from .vm import RegexVM, MatchResult, RegexTimeoutError, RegexStackOverflow


__all__ = ['RegExp', 'RegExpError', 'match', 'search', 'test',
           'RegexTimeoutError', 'RegexStackOverflow', 'MatchResult']


def _utf16_len(s: str) -> int:
    """Get UTF-16 length of a string (counting surrogate pairs as 2)."""
    length = 0
    for ch in s:
        cp = ord(ch)
        if cp > 0xFFFF:
            length += 2  # Surrogate pair
        else:
            length += 1
    return length


def _utf16_to_codepoint_index(s: str, utf16_idx: int) -> Optional[int]:
    """Convert UTF-16 index to code point index.

    Returns None if utf16_idx points to the middle of a surrogate pair.
    """
    if utf16_idx < 0:
        return None

    utf16_pos = 0
    for cp_idx, ch in enumerate(s):
        if utf16_pos == utf16_idx:
            return cp_idx
        cp = ord(ch)
        if cp > 0xFFFF:
            utf16_pos += 2
            # Check if pointing to middle of surrogate pair
            if utf16_pos > utf16_idx:
                return None  # Invalid - in middle of surrogate pair
        else:
            utf16_pos += 1

    # Check if pointing to end of string
    if utf16_pos == utf16_idx:
        return len(s)
    return None


def _codepoint_to_utf16_index(s: str, cp_idx: int) -> int:
    """Convert code point index to UTF-16 index."""
    utf16_pos = 0
    for i, ch in enumerate(s):
        if i == cp_idx:
            return utf16_pos
        cp = ord(ch)
        if cp > 0xFFFF:
            utf16_pos += 2
        else:
            utf16_pos += 1
    return utf16_pos


class RegExp:
    """
    JavaScript-compatible regular expression object.

    Provides safe regex matching with ReDoS protection.
    """

    def __init__(
        self,
        pattern: str,
        flags: str = "",
        poll_callback: Optional[Callable[[], bool]] = None,
        stack_limit: int = 10000,
        poll_interval: int = 100
    ):
        """
        Create a new RegExp.

        Args:
            pattern: The regex pattern string
            flags: Optional flags (g, i, m, s, u, y)
            poll_callback: Called periodically; return True to abort
            stack_limit: Maximum backtrack stack size
            poll_interval: Steps between poll calls
        """
        self.source = pattern
        self.flags = flags
        self._global = 'g' in flags
        self._ignore_case = 'i' in flags
        self._multiline = 'm' in flags
        self._dotall = 's' in flags
        self._unicode = 'u' in flags
        self._sticky = 'y' in flags
        self.lastIndex = 0

        self._poll_callback = poll_callback
        self._stack_limit = stack_limit
        self._poll_interval = poll_interval

        # Parse and compile
        try:
            parser = RegexParser(pattern, flags)
            self._ast, self._capture_count = parser.parse()

            compiler = RegexCompiler(flags)
            self._bytecode = compiler.compile(self._ast, self._capture_count)
            self._compiled = True
        except Exception as e:
            if isinstance(e, RegExpError):
                raise
            raise RegExpError(f"Failed to compile regex: {e}")

    @property
    def global_(self):
        return self._global

    @property
    def ignoreCase(self):
        return self._ignore_case

    @property
    def multiline(self):
        return self._multiline

    @property
    def dotAll(self):
        return self._dotall

    @property
    def unicode(self):
        return self._unicode

    @property
    def sticky(self):
        return self._sticky

    def _create_vm(self) -> RegexVM:
        """Create a new VM instance."""
        return RegexVM(
            self._bytecode,
            self._capture_count,
            self.flags,
            self._poll_callback,
            self._stack_limit,
            self._poll_interval
        )

    def test(self, string: str) -> bool:
        """
        Test if the pattern matches the string.

        Args:
            string: The string to test

        Returns:
            True if there's a match, False otherwise
        """
        vm = self._create_vm()

        if self._sticky:
            result = vm.match(string, self.lastIndex)
            if result:
                if self._global:
                    self.lastIndex = result.index + len(result[0]) if result[0] else result.index
                return True
            if self._global:
                self.lastIndex = 0
            return False

        result = vm.search(string, self.lastIndex if self._global else 0)
        if result:
            if self._global:
                self.lastIndex = result.index + len(result[0]) if result[0] else result.index + 1
            return True

        if self._global:
            self.lastIndex = 0
        return False

    def exec(self, string: str) -> Optional[MatchResult]:
        """
        Execute a search for a match.

        Args:
            string: The string to search

        Returns:
            Match array or None if no match
        """
        vm = self._create_vm()

        # In unicode mode, lastIndex is a UTF-16 index
        # Convert to code point index for internal matching
        if self._unicode and (self._global or self._sticky):
            cp_start = _utf16_to_codepoint_index(string, self.lastIndex)
            if cp_start is None:
                # Invalid UTF-16 index (e.g., in middle of surrogate pair)
                self.lastIndex = 0
                return None
            start_pos = cp_start
        else:
            start_pos = self.lastIndex if self._global else 0

        if self._sticky:
            result = vm.match(string, start_pos)
            if result:
                if self._global or self._sticky:
                    end_cp = result.index + len(result[0]) if result[0] else result.index
                    if self._unicode:
                        self.lastIndex = _codepoint_to_utf16_index(string, end_cp)
                    else:
                        self.lastIndex = end_cp
                return result
            if self._global or self._sticky:
                self.lastIndex = 0
            return None

        result = vm.search(string, start_pos)

        if result:
            if self._global:
                end_cp = result.index + len(result[0]) if result[0] else result.index + 1
                if self._unicode:
                    self.lastIndex = _codepoint_to_utf16_index(string, end_cp)
                else:
                    self.lastIndex = end_cp
            return result

        if self._global:
            self.lastIndex = 0
        return None


def match(pattern: str, string: str, flags: str = "") -> Optional[MatchResult]:
    """
    Convenience function to match pattern against string.

    Args:
        pattern: The regex pattern
        string: The string to match
        flags: Optional flags

    Returns:
        Match result or None
    """
    return RegExp(pattern, flags).exec(string)


def search(pattern: str, string: str, flags: str = "") -> Optional[MatchResult]:
    """
    Search for pattern in string.

    Args:
        pattern: The regex pattern
        string: The string to search
        flags: Optional flags

    Returns:
        Match result or None
    """
    return RegExp(pattern, flags).exec(string)


def test(pattern: str, string: str, flags: str = "") -> bool:
    """
    Test if pattern matches string.

    Args:
        pattern: The regex pattern
        string: The string to test
        flags: Optional flags

    Returns:
        True if matches, False otherwise
    """
    return RegExp(pattern, flags).test(string)
