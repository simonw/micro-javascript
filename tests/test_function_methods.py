"""Test Function.prototype methods: bind, call, apply."""

import pytest
from microjs import Context


class TestFunctionBind:
    """Test Function.prototype.bind()."""

    def test_bind_this(self):
        """Bind this context."""
        ctx = Context()
        result = ctx.eval(
            """
            var obj = { x: 10 };
            function getX() { return this.x; }
            var boundGetX = getX.bind(obj);
            boundGetX()
        """
        )
        assert result == 10

    def test_bind_partial_args(self):
        """Bind with partial arguments."""
        ctx = Context()
        result = ctx.eval(
            """
            function add(a, b) { return a + b; }
            var add5 = add.bind(null, 5);
            add5(3)
        """
        )
        assert result == 8

    def test_bind_multiple_args(self):
        """Bind with multiple arguments."""
        ctx = Context()
        result = ctx.eval(
            """
            function greet(greeting, name) {
                return greeting + ", " + name;
            }
            var sayHello = greet.bind(null, "Hello");
            sayHello("World")
        """
        )
        assert result == "Hello, World"

    def test_bind_preserves_length(self):
        """Bound function has correct length property."""
        ctx = Context()
        result = ctx.eval(
            """
            function add(a, b, c) { return a + b + c; }
            var add2 = add.bind(null, 1);
            add2.length
        """
        )
        assert result == 2


class TestFunctionCall:
    """Test Function.prototype.call()."""

    def test_call_with_this(self):
        """Call with specific this value."""
        ctx = Context()
        result = ctx.eval(
            """
            var obj = { x: 5 };
            function getX() { return this.x; }
            getX.call(obj)
        """
        )
        assert result == 5

    def test_call_with_args(self):
        """Call with arguments."""
        ctx = Context()
        result = ctx.eval(
            """
            function add(a, b) { return a + b; }
            add.call(null, 3, 4)
        """
        )
        assert result == 7

    def test_call_on_method(self):
        """Call method with different this."""
        ctx = Context()
        result = ctx.eval(
            """
            var obj1 = { name: "obj1" };
            var obj2 = { name: "obj2" };
            function getName() { return this.name; }
            getName.call(obj2)
        """
        )
        assert result == "obj2"


class TestFunctionApply:
    """Test Function.prototype.apply()."""

    def test_apply_with_this(self):
        """Apply with specific this value."""
        ctx = Context()
        result = ctx.eval(
            """
            var obj = { x: 10 };
            function getX() { return this.x; }
            getX.apply(obj)
        """
        )
        assert result == 10

    def test_apply_with_array_args(self):
        """Apply with array of arguments."""
        ctx = Context()
        result = ctx.eval(
            """
            function add(a, b, c) { return a + b + c; }
            add.apply(null, [1, 2, 3])
        """
        )
        assert result == 6

    def test_apply_for_max(self):
        """Use apply to spread array to custom function."""
        ctx = Context()
        result = ctx.eval(
            """
            function findMax(a, b, c, d, e) {
                var max = a;
                if (b > max) max = b;
                if (c > max) max = c;
                if (d > max) max = d;
                if (e > max) max = e;
                return max;
            }
            var numbers = [5, 3, 8, 1, 9];
            findMax.apply(null, numbers)
        """
        )
        assert result == 9

    def test_apply_empty_args(self):
        """Apply with no arguments array."""
        ctx = Context()
        result = ctx.eval(
            """
            function count() { return arguments.length; }
            count.apply(null)
        """
        )
        assert result == 0
