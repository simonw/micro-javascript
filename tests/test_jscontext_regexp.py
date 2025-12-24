"""Test RegExp integration with JSContext."""

import pytest
from microjs import JSContext


class TestRegExpConstructor:
    """Test RegExp construction in JavaScript."""

    def test_new_regexp_basic(self):
        """Create RegExp with constructor."""
        ctx = JSContext()
        result = ctx.eval('var re = new RegExp("abc"); re.source')
        assert result == "abc"

    def test_new_regexp_flags(self):
        """Create RegExp with flags."""
        ctx = JSContext()
        result = ctx.eval('var re = new RegExp("abc", "gi"); re.flags')
        assert result == "gi"

    def test_regexp_global_flag(self):
        """Check global flag property."""
        ctx = JSContext()
        result = ctx.eval('var re = new RegExp("abc", "g"); re.global')
        assert result is True

    def test_regexp_ignorecase_flag(self):
        """Check ignoreCase flag property."""
        ctx = JSContext()
        result = ctx.eval('var re = new RegExp("abc", "i"); re.ignoreCase')
        assert result is True


class TestRegExpTest:
    """Test RegExp.test() method."""

    def test_simple_match(self):
        """Test simple pattern match."""
        ctx = JSContext()
        result = ctx.eval('var re = new RegExp("hello"); re.test("hello world")')
        assert result is True

    def test_no_match(self):
        """Test no match."""
        ctx = JSContext()
        result = ctx.eval('var re = new RegExp("hello"); re.test("goodbye")')
        assert result is False

    def test_case_insensitive_match(self):
        """Test case insensitive match."""
        ctx = JSContext()
        result = ctx.eval('var re = new RegExp("hello", "i"); re.test("HELLO")')
        assert result is True

    def test_digit_pattern(self):
        """Test digit pattern."""
        ctx = JSContext()
        result = ctx.eval('var re = new RegExp("\\\\d+"); re.test("abc123")')
        assert result is True


class TestRegExpExec:
    """Test RegExp.exec() method."""

    def test_exec_match(self):
        """Test exec returns match array."""
        ctx = JSContext()
        result = ctx.eval('''
            var re = new RegExp("(\\\\w+)@(\\\\w+)");
            var m = re.exec("user@host");
            m[0]
        ''')
        assert result == "user@host"

    def test_exec_group(self):
        """Test exec captures groups."""
        ctx = JSContext()
        result = ctx.eval('''
            var re = new RegExp("(\\\\w+)@(\\\\w+)");
            var m = re.exec("user@host");
            m[1]
        ''')
        assert result == "user"

    def test_exec_no_match(self):
        """Test exec returns null on no match."""
        ctx = JSContext()
        result = ctx.eval('var re = new RegExp("xyz"); re.exec("abc")')
        assert result is None

    def test_exec_index(self):
        """Test exec result has index."""
        ctx = JSContext()
        result = ctx.eval('''
            var re = new RegExp("world");
            var m = re.exec("hello world");
            m.index
        ''')
        assert result == 6


class TestRegExpGlobal:
    """Test RegExp with global flag."""

    def test_global_exec_advances(self):
        """Test exec with global flag advances lastIndex."""
        ctx = JSContext()
        result = ctx.eval('''
            var re = new RegExp("a", "g");
            var s = "abab";
            var r1 = re.exec(s);
            var idx1 = r1.index;
            var r2 = re.exec(s);
            var idx2 = r2.index;
            idx1 + "," + idx2
        ''')
        assert result == "0,2"

    def test_lastindex_property(self):
        """Test lastIndex property is updated."""
        ctx = JSContext()
        result = ctx.eval('''
            var re = new RegExp("a", "g");
            var li1 = re.lastIndex;
            re.exec("abab");
            var li2 = re.lastIndex;
            li1 + "," + li2
        ''')
        assert result == "0,1"


class TestRegExpPatterns:
    """Test various regex patterns."""

    def test_word_boundary(self):
        """Test word boundary."""
        ctx = JSContext()
        result = ctx.eval('new RegExp("\\\\bword\\\\b").test("a word here")')
        assert result is True

    def test_anchors(self):
        """Test anchors."""
        ctx = JSContext()
        result = ctx.eval('new RegExp("^hello").test("hello world")')
        assert result is True
        result = ctx.eval('new RegExp("^hello").test("say hello")')
        assert result is False

    def test_quantifiers(self):
        """Test quantifiers."""
        ctx = JSContext()
        result = ctx.eval('new RegExp("a+").test("aaa")')
        assert result is True
        result = ctx.eval('new RegExp("a{2,3}").test("aaaa")')
        assert result is True

    def test_character_class(self):
        """Test character classes."""
        ctx = JSContext()
        result = ctx.eval('new RegExp("[a-z]+").test("hello")')
        assert result is True
        result = ctx.eval('new RegExp("[0-9]+").test("123")')
        assert result is True
