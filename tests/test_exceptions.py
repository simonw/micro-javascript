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
