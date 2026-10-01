"""Tests for exception handling: try/catch, unwinding and error reporting."""

import pytest

from microjs import Context, JSError


class TestHandlerUnwinding:
    """Exception handlers must belong to their frame and restore the stack."""

    def test_return_inside_try_does_not_leave_stale_handler(self):
        """A later uncaught error must not jump into a returned function's catch."""
        ctx = Context(time_limit=5.0)
        ctx.eval('function f() { try { return 1 } catch (e) { return "WRONG" } }')
        ctx.eval("f()")
        with pytest.raises(JSError, match="nope is not defined"):
            ctx.eval("nope")

    def test_stale_handler_not_used_within_same_eval(self):
        ctx = Context(time_limit=5.0)
        with pytest.raises(JSError, match="nope is not defined"):
            ctx.eval(
                'function f() { try { return 1 } catch (e) { return "WRONG" } }'
                "f(); nope"
            )

    def test_caught_exceptions_do_not_leak_stack(self):
        """Catching an exception discards values pushed inside the try block."""
        ctx = Context(memory_limit=1024 * 1024, time_limit=20.0)
        result = ctx.eval("""
            var n = 0;
            for (var i = 0; i < 20000; i++) {
                try { n = 1 + (function () { throw 1 })() } catch (e) { n++ }
            }
            n
        """)
        assert result == 20000

    def test_return_from_for_in_does_not_leak_stack(self):
        """Returning from inside a for-in loop discards the iterator."""
        ctx = Context(memory_limit=1024 * 1024, time_limit=20.0)
        result = ctx.eval("""
            function f() { for (var k in {a: 1}) return k }
            for (var i = 0; i < 20000; i++) f();
            i
        """)
        assert result == 20000


class TestThrowAcrossNativeCallbacks:
    """A throw inside a callback must unwind through the native caller."""

    def test_foreach_stops_at_first_throw(self):
        ctx = Context(time_limit=5.0)
        result = ctx.eval("""
            var calls = 0;
            try {
                [1, 2, 3, 4, 5].forEach(function () { calls++; throw new Error("stop") });
            } catch (e) {}
            calls
        """)
        assert result == 1

    def test_catch_receives_value_thrown_in_map_callback(self):
        ctx = Context(time_limit=5.0)
        result = ctx.eval("""
            var r;
            try { [1, 2].map(function () { throw new Error("inner") }) }
            catch (e) { r = e.message }
            r
        """)
        assert result == "inner"

    def test_catch_receives_primitive_thrown_in_callback(self):
        ctx = Context(time_limit=5.0)
        result = ctx.eval("""
            var log = [];
            try {
                [1, 2, 3].map(function (x) { log.push(x); if (x == 1) throw "boom"; return x });
            } catch (e) { log.push("catch:" + e) }
            log.join(" ")
        """)
        assert result == "1 catch:boom"

    def test_throw_through_nested_callbacks(self):
        ctx = Context(time_limit=5.0)
        result = ctx.eval("""
            var r;
            try {
                [1].forEach(function () {
                    [2].map(function () { throw new RangeError("deep") });
                });
            } catch (e) { r = e.name + ":" + e.message }
            r
        """)
        assert result == "RangeError:deep"

    def test_callback_can_catch_its_own_errors(self):
        ctx = Context(time_limit=5.0)
        result = ctx.eval("""
            [1, 2].map(function (x) {
                try { throw x } catch (e) { return e * 10 }
            }).join(",")
        """)
        assert result == "10,20"

    def test_uncaught_throw_in_callback_reaches_python(self):
        ctx = Context(time_limit=5.0)
        with pytest.raises(JSError, match="stop"):
            ctx.eval('[1, 2].forEach(function () { throw new Error("stop") })')

    def test_typeof_undeclared_inside_callback(self):
        ctx = Context(time_limit=5.0)
        assert ctx.eval("[1].map(function () { return typeof nope })[0]") == "undefined"

    def test_add_object_uses_native_tostring(self):
        ctx = Context(time_limit=5.0)
        assert ctx.eval("[] + {}") == "[object Object]"
        assert ctx.eval("[1, 2] + [3]") == "1,23"

    def test_add_object_with_custom_tostring(self):
        ctx = Context(time_limit=5.0)
        assert ctx.eval('"" + {toString: function () { return "T" }}') == "T"
