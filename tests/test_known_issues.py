"""
Fine-grained tests for known issues in mquickjs-python.

Each test is marked with pytest.mark.xfail and documents a specific issue
that needs to be fixed. When fixing an issue, the corresponding test should
start passing and the xfail marker can be removed.

Issues are organized by category:
- Indirect eval (global scope)
- Regex capture groups
- Regex alternation
- Regex character classes
- Regex unicode
- Error line/column tracking
- Deep nesting (recursion limits)
"""
import pytest
from mquickjs_python import JSContext


# =============================================================================
# INDIRECT EVAL ISSUES
# =============================================================================

class TestIndirectEval:
    """Tests for indirect eval ((1,eval)(...)) behavior."""

    def test_indirect_eval_basic(self):
        """Indirect eval can evaluate simple expressions."""
        ctx = JSContext(time_limit=5.0)
        result = ctx.eval('(1,eval)("1+1")')
        assert result == 2

    def test_indirect_eval_var_declaration(self):
        """Indirect eval can declare new global variables."""
        ctx = JSContext(time_limit=5.0)
        ctx.eval('var g_eval = (1,eval);')
        ctx.eval('g_eval("var z = 2")')
        assert ctx.eval('z') == 2

    def test_indirect_eval_reads_global(self):
        """Indirect eval can read existing global variables."""
        ctx = JSContext(time_limit=5.0)
        ctx.eval('var z = 2;')
        ctx.eval('var g_eval = (1,eval);')
        assert ctx.eval('g_eval("z")') == 2

    @pytest.mark.xfail(reason="Indirect eval doesn't persist writes to global vars")
    def test_indirect_eval_writes_global(self):
        """Indirect eval should persist writes to existing global variables.

        Issue: When indirect eval assigns to an existing global variable,
        the assignment should modify the global scope. Currently the
        assignment happens in a temporary scope and is lost.
        """
        ctx = JSContext(time_limit=5.0)
        ctx.eval('var z = 2;')
        ctx.eval('var g_eval = (1,eval);')
        ctx.eval('g_eval("z = 3")')
        assert ctx.eval('z') == 3  # Currently returns 2

    def test_indirect_eval_if_statement(self):
        """Indirect eval can evaluate if statements."""
        ctx = JSContext(time_limit=5.0)
        assert ctx.eval('(1,eval)("if (1) 2; else 3;")') == 2
        assert ctx.eval('(1,eval)("if (0) 2; else 3;")') == 3


# =============================================================================
# REGEX CAPTURE GROUP ISSUES
# =============================================================================

class TestRegexCaptureGroups:
    """Tests for regex capture group behavior."""

    @pytest.mark.xfail(reason="Capture groups in repetitions not reset to undefined")
    def test_capture_group_reset_in_repetition(self):
        """Capture groups in repetitions should reset to undefined.

        Issue: When a capture group inside a repetition (* or +) doesn't
        participate in a particular iteration, it should be reset to undefined.
        Currently the previous iteration's capture is retained.

        Pattern: /(z)((a+)?(b+)?(c))*/
        String:  'zaacbbbcac'

        Iterations:
        1. 'aac' -> group 3='aa', group 4=undefined, group 5='c'
        2. 'bbbc' -> group 3=undefined, group 4='bbb', group 5='c'
        3. 'ac' -> group 3='a', group 4=undefined, group 5='c'

        Final result should have group 4=undefined (from iteration 3),
        not 'bbb' (from iteration 2).
        """
        ctx = JSContext(time_limit=5.0)
        result = ctx.eval('/(z)((a+)?(b+)?(c))*/.exec("zaacbbbcac")')
        expected = ['zaacbbbcac', 'z', 'ac', 'a', None, 'c']
        assert result == expected

    @pytest.mark.xfail(reason="Optional lookahead group retains capture")
    def test_optional_lookahead_no_match(self):
        """Optional lookahead that doesn't match should have undefined capture.

        Issue: When an optional group containing a lookahead doesn't match,
        the capture from the lookahead should be undefined. Currently the
        capture from a previous successful lookahead attempt is retained.

        Pattern: /(?:(?=(abc)))?a/
        String:  'abc'

        The outer group (?:...)? is optional. The lookahead (?=(abc)) would
        match 'abc', but then 'a' must match. Since the lookahead consumed
        nothing, 'a' matches at position 0. But since the outer optional
        group could match (lookahead succeeded), it's unclear if the capture
        should be retained. Per spec, if the outer group is skipped, captures
        inside should be undefined.
        """
        ctx = JSContext(time_limit=5.0)
        result = ctx.eval('/(?:(?=(abc)))?a/.exec("abc")')
        # The lookahead succeeds but the optional group as a whole is not required
        # Per ES spec, group 1 should be undefined when the optional path is taken
        expected = ['a', None]
        assert result == expected

    @pytest.mark.xfail(reason="Repeated optional lookahead group retains capture")
    def test_repeated_optional_lookahead(self):
        """Repeated optional lookahead with {0,2} quantifier.

        Issue: Similar to test_optional_lookahead_no_match, but with {0,2}.
        The capture should be undefined since the lookahead group didn't
        participate in the final match.
        """
        ctx = JSContext(time_limit=5.0)
        result = ctx.eval('/(?:(?=(abc))){0,2}a/.exec("abc")')
        expected = ['a', None]
        assert result == expected

    def test_mandatory_lookahead_preserves_capture(self):
        """Mandatory lookahead correctly preserves its capture."""
        ctx = JSContext(time_limit=5.0)
        result = ctx.eval('/(?:(?=(abc)))a/.exec("abc")')
        # Here the non-capturing group is mandatory, so the lookahead runs
        expected = ['a', 'abc']
        assert result == expected


# =============================================================================
# REGEX ALTERNATION ISSUES
# =============================================================================

class TestRegexAlternation:
    """Tests for regex alternation behavior."""

    @pytest.mark.xfail(reason="Alternation with empty alternative doesn't match correctly")
    def test_empty_alternative_in_repetition(self):
        """Empty alternative in repeated group should work correctly.

        Issue: Pattern /(?:|[\\w])+([0-9])/ should match '123a23' fully,
        capturing '3' in group 1. The (?:|[\\w])+ means: match either
        empty string or a word character, one or more times.

        Currently matches only '1' with capture '1'.
        """
        ctx = JSContext(time_limit=5.0)
        result = ctx.eval('/(?:|[\\w])+([0-9])/.exec("123a23")')
        expected = ['123a23', '3']
        assert result == expected


# =============================================================================
# REGEX CHARACTER CLASS ISSUES
# =============================================================================

class TestRegexCharacterClass:
    """Tests for regex character class behavior."""

    def test_backspace_in_character_class_with_hex(self):
        """Backspace in character class matches \\x08 (works correctly)."""
        ctx = JSContext(time_limit=5.0)
        # \\b in a character class is backspace (0x08)
        result = ctx.eval('/[\\b]/.test("\\x08")')
        assert result is True

    def test_backspace_string_literal(self):
        """String literal \\b should be parsed as backspace character."""
        ctx = JSContext(time_limit=5.0)
        # Both should be backspace
        result = ctx.eval('/[\\b]/.test("\\b")')
        assert result is True

    def test_backspace_outside_class_is_boundary(self):
        """\\b outside character class is word boundary (works correctly)."""
        ctx = JSContext(time_limit=5.0)
        assert ctx.eval('/\\bword\\b/.test("a word here")') is True
        assert ctx.eval('/\\bword\\b/.test("awordhere")') is False


# =============================================================================
# REGEX UNICODE ISSUES
# =============================================================================

class TestRegexUnicode:
    """Tests for regex Unicode handling."""

    def test_lastindex_surrogate_pair(self):
        """lastIndex pointing to second surrogate should reset to 0."""
        ctx = JSContext(time_limit=5.0)
        ctx.eval('var a = /(?:)/gu;')
        ctx.eval('a.lastIndex = 1;')  # Point to middle of surrogate pair
        ctx.eval('a.exec("🐱");')  # 🐱 is a surrogate pair
        result = ctx.eval('a.lastIndex')
        assert result == 0


# =============================================================================
# ERROR LINE/COLUMN TRACKING ISSUES
# =============================================================================

class TestErrorLineColumn:
    """Tests for error line and column number tracking."""

    def test_thrown_error_has_line_number(self):
        """Thrown errors should have lineNumber property set."""
        ctx = JSContext(time_limit=5.0)
        result = ctx.eval('''
var e;
try {
    throw new Error("test");
} catch(ex) {
    e = ex;
}
e.lineNumber
''')
        assert result == 4  # Line where throw statement is

    def test_thrown_error_has_column_number(self):
        """Thrown errors should have columnNumber property set."""
        ctx = JSContext(time_limit=5.0)
        result = ctx.eval('''
var e;
try {
    throw new Error("test");
} catch(ex) {
    e = ex;
}
e.columnNumber
''')
        assert result == 5  # Column where throw statement starts

    def test_thrown_error_line_column_multiline(self):
        """Thrown errors track correct location in multiline code."""
        ctx = JSContext(time_limit=5.0)
        result = ctx.eval('''
var e;
try {
    var x = 1;
    var y = 2;
    throw new Error("test");
} catch(ex) {
    e = ex;
}
[e.lineNumber, e.columnNumber]
''')
        assert result == [6, 5]  # Line 6, column 5

    @pytest.mark.xfail(reason="Error constructor location tracking not implemented")
    def test_error_constructor_has_line_number(self):
        """Error objects created with 'new' should have lineNumber at creation.

        Issue: Error objects should have a lineNumber property indicating
        where they were created (not just where thrown). This requires
        tracking the call location during Error construction.
        """
        ctx = JSContext(time_limit=5.0)
        result = ctx.eval('var e = new Error("test"); e.lineNumber')
        assert result is not None
        assert isinstance(result, int)

    @pytest.mark.xfail(reason="Error constructor location tracking not implemented")
    def test_error_constructor_has_column_number(self):
        """Error objects created with 'new' should have columnNumber at creation.

        Issue: Error objects should have a columnNumber property indicating
        the column where they were created.
        """
        ctx = JSContext(time_limit=5.0)
        result = ctx.eval('var e = new Error("test"); e.columnNumber')
        assert result is not None
        assert isinstance(result, int)

    @pytest.mark.xfail(reason="SyntaxError position tracking not implemented")
    def test_syntax_error_position(self):
        """SyntaxError should include line and column information.

        Issue: When a SyntaxError occurs, the error message should include
        the line and column where the error occurred.
        """
        ctx = JSContext(time_limit=5.0)
        try:
            ctx.eval('\n 123 a ')  # Invalid syntax at line 2
        except Exception as e:
            error_msg = str(e)
            # Should contain line info
            assert 'line 2' in error_msg.lower() or ':2:' in error_msg


# =============================================================================
# DEEP NESTING / RECURSION LIMIT ISSUES
# =============================================================================

class TestDeepNesting:
    """Tests for handling deeply nested expressions."""

    def test_moderate_nested_parens(self):
        """Moderate nesting of parentheses works correctly."""
        ctx = JSContext(time_limit=5.0)
        n = 100
        pattern = "(" * n + "1" + ")" * n
        result = ctx.eval(pattern)
        assert result == 1

    @pytest.mark.xfail(reason="Deep nesting causes recursion overflow")
    def test_deep_nested_parens(self):
        """Very deep nesting of parentheses should work.

        Issue: 1000 levels of nested parentheses causes Python's
        maximum recursion depth to be exceeded. The parser uses
        recursive descent which doesn't scale to very deep nesting.
        """
        ctx = JSContext(time_limit=10.0)
        n = 1000
        pattern = "(" * n + "1" + ")" * n
        result = ctx.eval(pattern)
        assert result == 1

    def test_moderate_nested_braces(self):
        """Moderate nesting of braces works correctly."""
        ctx = JSContext(time_limit=5.0)
        n = 100
        pattern = "{" * n + "1;" + "}" * n
        result = ctx.eval(pattern)
        assert result == 1

    @pytest.mark.xfail(reason="Deep nesting causes recursion overflow")
    def test_deep_nested_braces(self):
        """Very deep nesting of braces should work.

        Issue: 1000 levels of nested braces causes recursion overflow.
        """
        ctx = JSContext(time_limit=10.0)
        n = 1000
        pattern = "{" * n + "1;" + "}" * n
        result = ctx.eval(pattern)
        assert result == 1

    def test_moderate_nested_arrays(self):
        """Moderate nesting of arrays works correctly."""
        ctx = JSContext(time_limit=5.0)
        n = 100
        pattern = "[" * n + "1" + "]" * n + "[0]" * n
        result = ctx.eval(pattern)
        assert result == 1

    @pytest.mark.xfail(reason="Deep nesting causes recursion overflow")
    def test_deep_nested_arrays(self):
        """Very deep nesting of arrays with access should work.

        Issue: 1000 levels of nested arrays causes recursion overflow.
        """
        ctx = JSContext(time_limit=10.0)
        n = 1000
        pattern = "[" * n + "1" + "]" * n + "[0]" * n
        result = ctx.eval(pattern)
        assert result == 1

    @pytest.mark.xfail(reason="Deep regex nesting causes recursion overflow")
    def test_deep_nested_regex_groups(self):
        """Very deep nesting of regex non-capturing groups should work.

        Issue: 10000 levels of nested (?:) groups causes overflow.
        """
        ctx = JSContext(time_limit=10.0)
        n = 10000
        ctx.eval(f'''
            function repeat(s, n) {{
                var result = "";
                for (var i = 0; i < n; i++) result += s;
                return result;
            }}
            var a = new RegExp(repeat("(?:", {n}) + "a+" + repeat(")", {n}));
        ''')
        result = ctx.eval('a.exec("aa")')
        expected = ['aa']
        assert result == expected
