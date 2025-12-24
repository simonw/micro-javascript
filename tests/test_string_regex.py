"""Test String methods that use RegExp."""

import pytest
from microjs import JSContext


class TestStringMatch:
    """Test String.prototype.match()."""

    def test_match_simple(self):
        """Match with simple regex."""
        ctx = JSContext()
        result = ctx.eval('"hello world".match(/world/)')
        assert result[0] == "world"

    def test_match_no_match(self):
        """Match returns null when no match."""
        ctx = JSContext()
        result = ctx.eval('"hello".match(/xyz/)')
        assert result is None

    def test_match_with_groups(self):
        """Match captures groups."""
        ctx = JSContext()
        result = ctx.eval('"user@host".match(/(\\w+)@(\\w+)/)')
        assert result[0] == "user@host"
        assert result[1] == "user"
        assert result[2] == "host"

    def test_match_global(self):
        """Match with global flag returns all matches."""
        ctx = JSContext()
        result = ctx.eval('"abab".match(/a/g)')
        assert len(result) == 2
        assert result[0] == "a"
        assert result[1] == "a"

    def test_match_index(self):
        """Match result has index property."""
        ctx = JSContext()
        result = ctx.eval('''
            var m = "hello world".match(/world/);
            m.index
        ''')
        assert result == 6

    def test_match_with_string_pattern(self):
        """Match with string pattern (not regex)."""
        ctx = JSContext()
        result = ctx.eval('"hello world".match("world")')
        assert result[0] == "world"


class TestStringSearch:
    """Test String.prototype.search()."""

    def test_search_found(self):
        """Search returns index when found."""
        ctx = JSContext()
        result = ctx.eval('"hello world".search(/world/)')
        assert result == 6

    def test_search_not_found(self):
        """Search returns -1 when not found."""
        ctx = JSContext()
        result = ctx.eval('"hello".search(/xyz/)')
        assert result == -1

    def test_search_at_start(self):
        """Search finds match at start."""
        ctx = JSContext()
        result = ctx.eval('"hello world".search(/hello/)')
        assert result == 0

    def test_search_with_string(self):
        """Search with string pattern."""
        ctx = JSContext()
        result = ctx.eval('"hello world".search("wor")')
        assert result == 6


class TestStringReplace:
    """Test String.prototype.replace()."""

    def test_replace_simple(self):
        """Replace first occurrence."""
        ctx = JSContext()
        result = ctx.eval('"hello world".replace(/world/, "there")')
        assert result == "hello there"

    def test_replace_no_match(self):
        """Replace returns original when no match."""
        ctx = JSContext()
        result = ctx.eval('"hello".replace(/xyz/, "abc")')
        assert result == "hello"

    def test_replace_global(self):
        """Replace all occurrences with global flag."""
        ctx = JSContext()
        result = ctx.eval('"abab".replace(/a/g, "X")')
        assert result == "XbXb"

    def test_replace_with_groups(self):
        """Replace with group references."""
        ctx = JSContext()
        result = ctx.eval('"hello world".replace(/(\\w+) (\\w+)/, "$2 $1")')
        assert result == "world hello"

    def test_replace_string_pattern(self):
        """Replace with string pattern."""
        ctx = JSContext()
        result = ctx.eval('"hello world".replace("world", "there")')
        assert result == "hello there"

    def test_replace_special_replacement(self):
        """Replace with special patterns in replacement."""
        ctx = JSContext()
        # $& is the matched substring
        result = ctx.eval('"hello".replace(/l/, "[$&]")')
        assert result == "he[l]lo"


class TestStringSplit:
    """Test String.prototype.split() with regex."""

    def test_split_regex(self):
        """Split with regex pattern."""
        ctx = JSContext()
        result = ctx.eval('"a1b2c3".split(/\\d/)')
        assert result == ["a", "b", "c", ""]

    def test_split_regex_with_groups(self):
        """Split with capturing groups includes captures."""
        ctx = JSContext()
        result = ctx.eval('"a1b2c".split(/(\\d)/)')
        # With captures: ["a", "1", "b", "2", "c"]
        assert "1" in result
        assert "2" in result

    def test_split_with_limit(self):
        """Split with limit."""
        ctx = JSContext()
        result = ctx.eval('"a,b,c,d".split(/,/, 2)')
        assert len(result) == 2
        assert result == ["a", "b"]


class TestStringTrimStart:
    """Test String.prototype.trimStart()."""

    def test_trimStart_basic(self):
        """trimStart removes leading whitespace."""
        ctx = JSContext()
        result = ctx.eval('"  hello".trimStart()')
        assert result == "hello"

    def test_trimStart_preserves_trailing(self):
        """trimStart preserves trailing whitespace."""
        ctx = JSContext()
        result = ctx.eval('"  hello  ".trimStart()')
        assert result == "hello  "

    def test_trimStart_no_change(self):
        """trimStart on string without leading whitespace."""
        ctx = JSContext()
        result = ctx.eval('"hello".trimStart()')
        assert result == "hello"

    def test_trimStart_all_whitespace(self):
        """trimStart on all whitespace string."""
        ctx = JSContext()
        result = ctx.eval('"   ".trimStart()')
        assert result == ""


class TestStringTrimEnd:
    """Test String.prototype.trimEnd()."""

    def test_trimEnd_basic(self):
        """trimEnd removes trailing whitespace."""
        ctx = JSContext()
        result = ctx.eval('"hello  ".trimEnd()')
        assert result == "hello"

    def test_trimEnd_preserves_leading(self):
        """trimEnd preserves leading whitespace."""
        ctx = JSContext()
        result = ctx.eval('"  hello  ".trimEnd()')
        assert result == "  hello"

    def test_trimEnd_no_change(self):
        """trimEnd on string without trailing whitespace."""
        ctx = JSContext()
        result = ctx.eval('"hello".trimEnd()')
        assert result == "hello"

    def test_trimEnd_all_whitespace(self):
        """trimEnd on all whitespace string."""
        ctx = JSContext()
        result = ctx.eval('"   ".trimEnd()')
        assert result == ""


class TestStringReplaceAll:
    """Test String.prototype.replaceAll()."""

    def test_replaceAll_basic(self):
        """replaceAll replaces all occurrences."""
        ctx = JSContext()
        result = ctx.eval('"abcabc".replaceAll("b", "x")')
        assert result == "axcaxc"

    def test_replaceAll_no_match(self):
        """replaceAll with no match returns original."""
        ctx = JSContext()
        result = ctx.eval('"hello".replaceAll("x", "y")')
        assert result == "hello"

    def test_replaceAll_with_dollar_ampersand(self):
        """replaceAll with $& replacement pattern."""
        ctx = JSContext()
        result = ctx.eval('"abcabc".replaceAll("b", "$&$&")')
        assert result == "abbcabbc"

    def test_replaceAll_with_dollar_dollar(self):
        """replaceAll with $$ replacement pattern (literal $)."""
        ctx = JSContext()
        result = ctx.eval('"abcabc".replaceAll("b", "$$")')
        assert result == "a$ca$c"

    def test_replaceAll_complex_replacement(self):
        """replaceAll with combined $$ and $& patterns."""
        ctx = JSContext()
        result = ctx.eval('"abcabc".replaceAll("b", "a$$b$&")')
        assert result == "aa$bbcaa$bbc"
