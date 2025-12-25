"""Test arrow function syntax."""

import pytest
from microjs import Context


class TestArrowFunctionBasics:
    """Test basic arrow function syntax."""

    def test_simple_arrow(self):
        """Simple arrow function with expression body."""
        ctx = Context()
        result = ctx.eval("var f = x => x * 2; f(5)")
        assert result == 10

    def test_arrow_no_params(self):
        """Arrow function with no parameters."""
        ctx = Context()
        result = ctx.eval("var f = () => 42; f()")
        assert result == 42

    def test_arrow_multiple_params(self):
        """Arrow function with multiple parameters."""
        ctx = Context()
        result = ctx.eval("var f = (a, b) => a + b; f(3, 4)")
        assert result == 7

    def test_arrow_with_block(self):
        """Arrow function with block body."""
        ctx = Context()
        result = ctx.eval("var f = (x) => { return x * 3; }; f(4)")
        assert result == 12

    def test_arrow_single_param_no_parens(self):
        """Single parameter doesn't need parentheses."""
        ctx = Context()
        result = ctx.eval("var f = n => n + 1; f(10)")
        assert result == 11


class TestArrowFunctionExpressions:
    """Test arrow functions as expressions."""

    def test_arrow_iife(self):
        """Immediately invoked arrow function."""
        ctx = Context()
        result = ctx.eval("((x) => x + 1)(5)")
        assert result == 6

    def test_arrow_in_array(self):
        """Arrow functions in array literals."""
        ctx = Context()
        result = ctx.eval("[1, 2, 3].map(x => x * 2)")
        assert list(result) == [2, 4, 6]

    def test_arrow_in_callback(self):
        """Arrow function as callback."""
        ctx = Context()
        result = ctx.eval("[1, 2, 3, 4].filter(x => x > 2)")
        assert list(result) == [3, 4]


class TestArrowFunctionScope:
    """Test arrow function scoping rules."""

    def test_arrow_captures_outer_var(self):
        """Arrow function captures outer variables."""
        ctx = Context()
        result = ctx.eval(
            """
            var x = 10;
            var f = () => x;
            f()
        """
        )
        assert result == 10

    def test_arrow_closure(self):
        """Arrow function creates proper closures."""
        ctx = Context()
        result = ctx.eval(
            """
            function makeAdder(n) {
                return x => x + n;
            }
            var add5 = makeAdder(5);
            add5(10)
        """
        )
        assert result == 15


class TestArrowFunctionEdgeCases:
    """Test edge cases for arrow functions."""

    def test_arrow_returns_object(self):
        """Arrow function returning object literal (needs parens)."""
        ctx = Context()
        result = ctx.eval("var f = () => ({ x: 1, y: 2 }); f().x")
        assert result == 1

    def test_arrow_multiple_statements(self):
        """Arrow function with multiple statements in block."""
        ctx = Context()
        result = ctx.eval(
            """
            var f = (a, b) => {
                var sum = a + b;
                return sum * 2;
            };
            f(3, 4)
        """
        )
        assert result == 14

    def test_nested_arrow_functions(self):
        """Nested arrow functions."""
        ctx = Context()
        result = ctx.eval("var f = x => y => x + y; f(3)(4)")
        assert result == 7
