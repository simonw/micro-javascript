"""Test String methods that use RegExp."""

import pytest
from microjs import Context


class TestStringMatch:
    """Test String.prototype.match()."""

    def test_match_simple(self):
        """Match with simple regex."""
        ctx = Context()
        result = ctx.eval('"hello world".match(/world/)')
        assert result[0] == "world"

    def test_match_no_match(self):
        """Match returns null when no match."""
        ctx = Context()
        result = ctx.eval('"hello".match(/xyz/)')
        assert result is None

    def test_match_with_groups(self):
        """Match captures groups."""
        ctx = Context()
        result = ctx.eval('"user@host".match(/(\\w+)@(\\w+)/)')
        assert result[0] == "user@host"
        assert result[1] == "user"
        assert result[2] == "host"

    def test_match_global(self):
        """Match with global flag returns all matches."""
        ctx = Context()
        result = ctx.eval('"abab".match(/a/g)')
        assert len(result) == 2
        assert result[0] == "a"
        assert result[1] == "a"

    def test_match_index(self):
        """Match result has index property."""
        ctx = Context()
        result = ctx.eval(
            """
            var m = "hello world".match(/world/);
            m.index
        """
        )
        assert result == 6

    def test_match_with_string_pattern(self):
        """Match with string pattern (not regex)."""
        ctx = Context()
        result = ctx.eval('"hello world".match("world")')
        assert result[0] == "world"


class TestStringSearch:
    """Test String.prototype.search()."""

    def test_search_found(self):
        """Search returns index when found."""
        ctx = Context()
        result = ctx.eval('"hello world".search(/world/)')
        assert result == 6

    def test_search_not_found(self):
        """Search returns -1 when not found."""
        ctx = Context()
        result = ctx.eval('"hello".search(/xyz/)')
        assert result == -1

    def test_search_at_start(self):
        """Search finds match at start."""
        ctx = Context()
        result = ctx.eval('"hello world".search(/hello/)')
        assert result == 0

    def test_search_with_string(self):
        """Search with string pattern."""
        ctx = Context()
        result = ctx.eval('"hello world".search("wor")')
        assert result == 6


class TestStringReplace:
    """Test String.prototype.replace()."""

    def test_replace_simple(self):
        """Replace first occurrence."""
        ctx = Context()
        result = ctx.eval('"hello world".replace(/world/, "there")')
        assert result == "hello there"

    def test_replace_no_match(self):
        """Replace returns original when no match."""
        ctx = Context()
        result = ctx.eval('"hello".replace(/xyz/, "abc")')
        assert result == "hello"

    def test_replace_global(self):
        """Replace all occurrences with global flag."""
        ctx = Context()
        result = ctx.eval('"abab".replace(/a/g, "X")')
        assert result == "XbXb"

    def test_replace_with_groups(self):
        """Replace with group references."""
        ctx = Context()
        result = ctx.eval('"hello world".replace(/(\\w+) (\\w+)/, "$2 $1")')
        assert result == "world hello"

    def test_replace_string_pattern(self):
        """Replace with string pattern."""
        ctx = Context()
        result = ctx.eval('"hello world".replace("world", "there")')
        assert result == "hello there"

    def test_replace_special_replacement(self):
        """Replace with special patterns in replacement."""
        ctx = Context()
        # $& is the matched substring
        result = ctx.eval('"hello".replace(/l/, "[$&]")')
        assert result == "he[l]lo"


class TestStringSplit:
    """Test String.prototype.split() with regex."""

    def test_split_regex(self):
        """Split with regex pattern."""
        ctx = Context()
        result = ctx.eval('"a1b2c3".split(/\\d/)')
        assert result == ["a", "b", "c", ""]

    def test_split_regex_with_groups(self):
        """Split with capturing groups includes captures."""
        ctx = Context()
        result = ctx.eval('"a1b2c".split(/(\\d)/)')
        # With captures: ["a", "1", "b", "2", "c"]
        assert "1" in result
        assert "2" in result

    def test_split_with_limit(self):
        """Split with limit."""
        ctx = Context()
        result = ctx.eval('"a,b,c,d".split(/,/, 2)')
        assert len(result) == 2
        assert result == ["a", "b"]


class TestStringTrimStart:
    """Test String.prototype.trimStart()."""

    def test_trimStart_basic(self):
        """trimStart removes leading whitespace."""
        ctx = Context()
        result = ctx.eval('"  hello".trimStart()')
        assert result == "hello"

    def test_trimStart_preserves_trailing(self):
        """trimStart preserves trailing whitespace."""
        ctx = Context()
        result = ctx.eval('"  hello  ".trimStart()')
        assert result == "hello  "

    def test_trimStart_no_change(self):
        """trimStart on string without leading whitespace."""
        ctx = Context()
        result = ctx.eval('"hello".trimStart()')
        assert result == "hello"

    def test_trimStart_all_whitespace(self):
        """trimStart on all whitespace string."""
        ctx = Context()
        result = ctx.eval('"   ".trimStart()')
        assert result == ""


class TestStringTrimEnd:
    """Test String.prototype.trimEnd()."""

    def test_trimEnd_basic(self):
        """trimEnd removes trailing whitespace."""
        ctx = Context()
        result = ctx.eval('"hello  ".trimEnd()')
        assert result == "hello"

    def test_trimEnd_preserves_leading(self):
        """trimEnd preserves leading whitespace."""
        ctx = Context()
        result = ctx.eval('"  hello  ".trimEnd()')
        assert result == "  hello"

    def test_trimEnd_no_change(self):
        """trimEnd on string without trailing whitespace."""
        ctx = Context()
        result = ctx.eval('"hello".trimEnd()')
        assert result == "hello"

    def test_trimEnd_all_whitespace(self):
        """trimEnd on all whitespace string."""
        ctx = Context()
        result = ctx.eval('"   ".trimEnd()')
        assert result == ""


class TestStringReplaceAll:
    """Test String.prototype.replaceAll()."""

    def test_replaceAll_basic(self):
        """replaceAll replaces all occurrences."""
        ctx = Context()
        result = ctx.eval('"abcabc".replaceAll("b", "x")')
        assert result == "axcaxc"

    def test_replaceAll_no_match(self):
        """replaceAll with no match returns original."""
        ctx = Context()
        result = ctx.eval('"hello".replaceAll("x", "y")')
        assert result == "hello"

    def test_replaceAll_with_dollar_ampersand(self):
        """replaceAll with $& replacement pattern."""
        ctx = Context()
        result = ctx.eval('"abcabc".replaceAll("b", "$&$&")')
        assert result == "abbcabbc"

    def test_replaceAll_with_dollar_dollar(self):
        """replaceAll with $$ replacement pattern (literal $)."""
        ctx = Context()
        result = ctx.eval('"abcabc".replaceAll("b", "$$")')
        assert result == "a$ca$c"

    def test_replaceAll_complex_replacement(self):
        """replaceAll with combined $$ and $& patterns."""
        ctx = Context()
        result = ctx.eval('"abcabc".replaceAll("b", "a$$b$&")')
        assert result == "aa$bbcaa$bbc"


class TestStringMethodsEdgeCases:
    """Test edge cases for string methods with regex."""

    def test_match_with_case_insensitive(self):
        """Match with case-insensitive flag."""
        ctx = Context()
        result = ctx.eval('"Hello World".match(/hello/i)')
        assert result[0] == "Hello"

    def test_match_with_multiline(self):
        """Match with multiline flag."""
        ctx = Context()
        result = ctx.eval('"line1\\nline2".match(/^line2/m)')
        assert result[0] == "line2"

    def test_search_with_case_insensitive(self):
        """Search with case-insensitive flag."""
        ctx = Context()
        result = ctx.eval('"Hello World".search(/HELLO/i)')
        assert result == 0

    def test_replace_with_case_insensitive(self):
        """Replace with case-insensitive flag."""
        ctx = Context()
        result = ctx.eval('"Hello World".replace(/HELLO/i, "hi")')
        assert result == "hi World"

    def test_split_with_case_insensitive(self):
        """Split with case-insensitive flag."""
        ctx = Context()
        result = ctx.eval('"aXbXc".split(/x/i)')
        assert result == ["a", "b", "c"]

    def test_match_empty_string(self):
        """Match against empty string."""
        ctx = Context()
        result = ctx.eval('"".match(/a/)')
        assert result is None

    def test_match_zero_width(self):
        """Match with zero-width pattern (boundary)."""
        ctx = Context()
        result = ctx.eval('"hello world".match(/\\b/g)')
        # Should match at word boundaries
        assert len(result) > 0

    def test_replace_with_empty_match(self):
        """Replace with pattern that matches empty string."""
        ctx = Context()
        result = ctx.eval('"abc".replace(/(?=.)/g, "-")')
        assert result == "-a-b-c"

    def test_split_empty_pattern(self):
        """Split with empty string pattern."""
        ctx = Context()
        result = ctx.eval('"abc".split("")')
        assert result == ["a", "b", "c"]

    def test_match_multiple_groups(self):
        """Match with multiple capturing groups."""
        ctx = Context()
        result = ctx.eval('"2024-12-27".match(/(\\d{4})-(\\d{2})-(\\d{2})/)')
        assert result[0] == "2024-12-27"
        assert result[1] == "2024"
        assert result[2] == "12"
        assert result[3] == "27"

    def test_replace_with_multiple_groups(self):
        """Replace with multiple group references."""
        ctx = Context()
        result = ctx.eval(
            '"2024-12-27".replace(/(\\d{4})-(\\d{2})-(\\d{2})/, "$2/$3/$1")'
        )
        assert result == "12/27/2024"

    def test_split_with_capturing_group(self):
        """Split with capturing group preserves separators."""
        ctx = Context()
        result = ctx.eval('"a1b2c".split(/(\\d)/)')
        # Should include captured separators
        assert "1" in result
        assert "2" in result

    def test_match_optional_group(self):
        """Match with optional capturing group."""
        ctx = Context()
        result = ctx.eval('"ac".match(/a(b)?c/)')
        assert result[0] == "ac"
        # Group 1 should be undefined when not matched
        assert result[1] is None or result.get("1") is None


class TestStringMethodsTimeLimits:
    """Test that string methods respect time limits via microjs.regex.

    These tests use ReDoS patterns that cause catastrophic backtracking.
    The pattern (a+)+b matching against 'aaa...c' causes exponential O(2^n)
    backtracking because it never matches (no 'b' at the end).

    We use a long string (50+ 'a' characters) to ensure the pattern takes
    more time than the timeout even on fast hardware.
    """

    # Long string that guarantees timeout - 50 'a' chars causes 2^50 paths
    LONG_REDOS_INPUT = "a" * 50 + "c"

    @pytest.mark.parametrize(
        "method",
        ["match", "search", "replace", "split"],
    )
    def test_string_methods_respect_time_limit(self, method):
        """Test that string regex methods respect Context time_limit.

        This uses a pattern known to cause catastrophic backtracking:
        (a+)+b matching against 'aaa...c' causes exponential backtracking.
        """
        from microjs import TimeLimitError

        # Build the method call dynamically with a long input string
        if method == "replace":
            method_code = f'"{self.LONG_REDOS_INPUT}".replace(/(a+)+b/, "x")'
        elif method == "split":
            method_code = f'"{self.LONG_REDOS_INPUT}".split(/(a+)+b/)'
        else:
            method_code = f'"{self.LONG_REDOS_INPUT}".{method}(/(a+)+b/)'

        ctx = Context(time_limit=0.05)  # 50ms timeout
        with pytest.raises(TimeLimitError):
            ctx.eval(method_code)


class TestStringMethodsRobust:
    """Additional robust tests for string regex methods."""

    def test_match_global_with_groups_returns_only_full_matches(self):
        """Global match should return only full matches, not groups."""
        ctx = Context()
        result = ctx.eval('"ab cd".match(/(\\w+)/g)')
        assert result == ["ab", "cd"]
        assert len(result) == 2

    def test_match_non_global_includes_groups(self):
        """Non-global match should include capture groups."""
        ctx = Context()
        result = ctx.eval('"user@example.com".match(/(\\w+)@(\\w+)\\.(\\w+)/)')
        assert result[0] == "user@example.com"
        assert result[1] == "user"
        assert result[2] == "example"
        assert result[3] == "com"

    def test_replace_global_replaces_all(self):
        """Global replace should replace all occurrences."""
        ctx = Context()
        result = ctx.eval('"abcabc".replace(/b/g, "X")')
        assert result == "aXcaXc"

    def test_replace_non_global_replaces_first(self):
        """Non-global replace should only replace first occurrence."""
        ctx = Context()
        result = ctx.eval('"abcabc".replace(/b/, "X")')
        assert result == "aXcabc"

    def test_split_limit_zero(self):
        """Split with limit 0 returns empty array."""
        ctx = Context()
        result = ctx.eval('"a,b,c".split(/,/, 0)')
        assert result == []

    def test_split_no_match(self):
        """Split with no matching separator returns original string."""
        ctx = Context()
        result = ctx.eval('"abc".split(/x/)')
        assert result == ["abc"]

    def test_search_returns_negative_one_on_no_match(self):
        """Search returns -1 when pattern not found."""
        ctx = Context()
        result = ctx.eval('"hello".search(/xyz/)')
        assert result == -1

    def test_match_returns_null_on_no_match(self):
        """Match returns null when pattern not found."""
        ctx = Context()
        result = ctx.eval('"hello".match(/xyz/)')
        assert result is None

    def test_replace_no_match_returns_original(self):
        """Replace with no match returns original string."""
        ctx = Context()
        result = ctx.eval('"hello".replace(/xyz/, "abc")')
        assert result == "hello"

    def test_special_characters_in_pattern(self):
        """Test regex with special characters."""
        ctx = Context()
        result = ctx.eval('"hello.world".match(/\\./)')
        assert result[0] == "."

    def test_unicode_in_string(self):
        """Test string methods with unicode characters."""
        ctx = Context()
        result = ctx.eval('"hello 世界".match(/世界/)')
        assert result[0] == "世界"

    def test_replace_with_dollar_in_replacement(self):
        """Replace with escaped dollar sign in replacement."""
        ctx = Context()
        result = ctx.eval('"abc".replace(/b/, "$$100")')
        assert result == "a$100c"

    def test_replace_all_group_refs(self):
        """Replace with multiple group references."""
        ctx = Context()
        result = ctx.eval('"a1b2c3".replace(/(\\w)(\\d)/g, "$2$1")')
        assert result == "1a2b3c"
