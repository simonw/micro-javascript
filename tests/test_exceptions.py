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


class TestUncaughtErrors:
    """Uncaught JS errors reach Python with their type and thrown value."""

    def test_uncaught_reference_error_type(self):
        from microjs.errors import JSReferenceError

        with pytest.raises(JSReferenceError) as info:
            Context().eval("nope")
        assert info.value.name == "ReferenceError"
        assert str(info.value) == "ReferenceError: nope is not defined"

    def test_uncaught_type_error_type(self):
        from microjs.errors import JSTypeError

        with pytest.raises(JSTypeError) as info:
            Context().eval("null.x")
        assert info.value.name == "TypeError"

    def test_uncaught_thrown_range_error(self):
        from microjs.errors import JSRangeError

        with pytest.raises(JSRangeError, match="RangeError: too big"):
            Context().eval('throw new RangeError("too big")')

    def test_uncaught_custom_error_name(self):
        with pytest.raises(JSError) as info:
            Context().eval('var e = new Error("m"); e.name = "MyError"; throw e')
        assert info.value.name == "MyError"
        assert str(info.value) == "MyError: m"

    def test_uncaught_thrown_object_value(self):
        with pytest.raises(JSError) as info:
            Context().eval("throw {code: 42}")
        assert info.value.value == {"code": 42}

    def test_uncaught_thrown_primitive_value(self):
        with pytest.raises(JSError) as info:
            Context().eval("throw 42")
        assert info.value.value == 42
        assert str(info.value) == "Error: 42"

    def test_uncaught_error_object_value(self):
        with pytest.raises(JSError) as info:
            Context().eval('throw new TypeError("bad")')
        assert info.value.value["message"] == "bad"
        assert info.value.value["name"] == "TypeError"


class TestPythonExceptionsBecomeJSErrors:
    """Python exceptions raised during execution are catchable JS errors."""

    def test_host_function_exception_is_catchable(self):
        ctx = Context(time_limit=5.0)
        ctx.set("boom", lambda: 1 / 0)
        result = ctx.eval(
            "var r; try { boom() } catch (e) { r = e.name + ': ' + e.message } r"
        )
        assert result == "InternalError: ZeroDivisionError: division by zero"

    def test_uncaught_host_exception_raises_jserror_with_cause(self):
        ctx = Context(time_limit=5.0)
        ctx.set("boom", lambda: 1 / 0)
        with pytest.raises(JSError) as info:
            ctx.eval("boom()")
        assert isinstance(info.value.__cause__, ZeroDivisionError)

    def test_host_exception_inside_callback_is_catchable(self):
        ctx = Context(time_limit=5.0)
        ctx.set("boom", lambda x: {}[x])
        result = ctx.eval(
            "var r; try { [1].forEach(function (x) { boom(x) }) }"
            " catch (e) { r = e.name } r"
        )
        assert result == "InternalError"

    def test_python_recursion_becomes_range_error(self):
        """JS -> native -> JS recursion exhausts the Python stack."""
        ctx = Context(time_limit=10.0)
        result = ctx.eval("""
            function f(n) { return [n].map(function (x) { return f(x + 1) }) }
            var r; try { f(0) } catch (e) { r = e.name } r
        """)
        assert result == "RangeError"


class TestLimitsAreNotCatchable:
    """JavaScript must not be able to catch the sandbox's limit errors."""

    def test_time_limit_not_catchable(self):
        from microjs import TimeLimitError

        with pytest.raises(TimeLimitError):
            Context(time_limit=0.5).eval("try { while (true) {} } catch (e) {}")

    def test_time_limit_not_catchable_in_callback(self):
        from microjs import TimeLimitError

        with pytest.raises(TimeLimitError):
            Context(time_limit=0.5).eval(
                "try { [1].forEach(function () { while (true) {} }) } catch (e) {}"
            )

    def test_time_limit_not_catchable_in_eval(self):
        import time

        from microjs import TimeLimitError

        start = time.monotonic()
        with pytest.raises(TimeLimitError):
            Context(time_limit=0.5).eval(
                'for (;;) { try { (1, eval)("while (true) {}") } catch (e) {} }'
            )
        assert time.monotonic() - start < 3

    def test_memory_limit_not_catchable(self):
        from microjs import MemoryLimitError

        with pytest.raises(MemoryLimitError):
            Context(memory_limit=100 * 1024, time_limit=5.0).eval(
                "function f() { return f() } try { f() } catch (e) {}"
            )


class TestEvalAndFunctionErrors:
    """Errors from indirect eval and new Function propagate as JS errors."""

    def test_eval_propagates_thrown_error_unchanged(self):
        ctx = Context(time_limit=5.0)
        result = ctx.eval("""
            var r;
            try { (1, eval)("throw new TypeError('x')") } catch (e) { r = e.name + ":" + e.message }
            r
        """)
        assert result == "TypeError:x"

    def test_eval_reference_error(self):
        ctx = Context(time_limit=5.0)
        result = ctx.eval('var r; try { (1, eval)("nope") } catch (e) { r = e.name } r')
        assert result == "ReferenceError"

    def test_eval_syntax_error_is_catchable(self):
        ctx = Context(time_limit=5.0)
        result = ctx.eval(
            'var r; try { (1, eval)("var @") } catch (e) { r = e.name } r'
        )
        assert result == "SyntaxError"

    def test_uncaught_eval_syntax_error(self):
        from microjs import JSSyntaxError

        with pytest.raises(JSSyntaxError):
            Context(time_limit=5.0).eval('(1, eval)("var @")')

    def test_function_constructor_syntax_error_is_catchable(self):
        ctx = Context(time_limit=5.0)
        result = ctx.eval(
            'var r; try { new Function("return @") } catch (e) { r = e.name } r'
        )
        assert result == "SyntaxError"

    def test_function_constructor_rejects_body_injection(self):
        """A body that closes the wrapper must not run code at creation."""
        ctx = Context(time_limit=5.0)
        result = ctx.eval("""
            var injected = false, r;
            try { new Function("}); injected = true; (function () {") }
            catch (e) { r = e.name }
            r + " " + injected
        """)
        assert result == "SyntaxError false"

    def test_function_constructor_still_works(self):
        ctx = Context(time_limit=5.0)
        assert ctx.eval('new Function("a", "b", "return a + b")(2, 3)') == 5


class TestSyntaxErrors:
    """Invalid programs raise SyntaxError instead of running or crashing."""

    @pytest.mark.parametrize(
        "source",
        ["1 2", "var a = 1 var b = 2", "x = 1 y = 2", "return 1 2"],
    )
    def test_invalid_programs(self, source):
        from microjs import JSSyntaxError

        with pytest.raises(JSSyntaxError):
            Context(time_limit=5.0).eval(f"function f() {{ {source}\n}}")

    def test_unterminated_comment(self):
        from microjs import JSSyntaxError

        with pytest.raises(JSSyntaxError, match="Unterminated comment"):
            Context(time_limit=5.0).eval("1 /* unterminated")

    @pytest.mark.parametrize(
        "source,expected",
        [
            ("var a = 1\nvar b = 2\na + b", 3),
            ("var a = 1; { a = 2 } a", 2),
            ("var x = 5", None),
            ("var i = 0; do { i++ } while (i < 3) i", 3),
            ("var f = function () { return 1 }\nf()", 1),
            ("/* comment */ 1 /* another\n */ + 1", 2),
        ],
    )
    def test_automatic_semicolon_insertion(self, source, expected):
        assert Context(time_limit=5.0).eval(source) == expected

    @pytest.mark.parametrize("source", ['"/(/"', '"/aaa]/u"', '"/a{2,1}/"'])
    def test_invalid_regex_literal_is_syntax_error(self, source):
        ctx = Context(time_limit=5.0)
        result = ctx.eval(
            f"var r; try {{ (1, eval)({source}) }} catch (e) {{ r = e.name }} r"
        )
        assert result == "SyntaxError"

    def test_invalid_regexp_constructor_is_syntax_error(self):
        ctx = Context(time_limit=5.0)
        result = ctx.eval(
            'var r; try { new RegExp("(") } catch (e) { r = e instanceof SyntaxError } r'
        )
        assert result is True


class TestCatchParameterScope:
    """The catch parameter is scoped to its catch block."""

    @pytest.mark.parametrize(
        "source,expected",
        [
            # Closures capture the catch parameter, at program level too
            (
                "var f; try { throw 1 } catch (e) { f = function () { return e } } f()",
                1,
            ),
            (
                "function g() { var f; try { throw 2 } catch (e)"
                " { f = function () { return e } } return f() } g()",
                2,
            ),
            # It does not overwrite a variable of the same name
            ('var e = "outer"; try { throw "inner" } catch (e) {} e', "outer"),
            (
                "function g() { var e = 1; try { throw 2 } catch (e) {} return e } g()",
                1,
            ),
            # Nested catch blocks with the same name each get their own binding
            (
                "var r = []; try { throw 1 } catch (e) {"
                " try { throw 2 } catch (e) { r.push(e) } r.push(e) } r.join()",
                "2,1",
            ),
            # Property names, shorthand properties and shadowing parameters
            ("var r; try { throw {e: 5} } catch (e) { r = e.e + ({e: 1}).e } r", 6),
            ("var r; try { throw 3 } catch (e) { r = ({e}).e } r", 3),
            (
                "var r; try { throw 1 } catch (e)"
                " { r = (function (e) { return e })(2) + e } r",
                3,
            ),
            ("var r; try { throw 1 } catch (e) { e = e + 1; r = e } r", 2),
            ("var r; try { throw 1 } catch (e) { r = typeof e } r", "number"),
        ],
    )
    def test_catch_scope(self, source, expected):
        assert Context(time_limit=5.0).eval(source) == expected

    def test_catch_parameter_not_visible_after_catch(self):
        from microjs import JSReferenceError

        with pytest.raises(JSReferenceError, match="e is not defined"):
            Context(time_limit=5.0).eval("try { throw 1 } catch (e) {} e")
