"""Tests for try/finally, break, continue, return and labels."""

import pytest

from microjs import Context, JSSyntaxError


def run(source, **kwargs):
    kwargs.setdefault("time_limit", 5.0)
    return Context(**kwargs).eval(source)


class TestFinally:
    def test_finally_runs_when_catch_throws(self):
        assert run("""
            var log = "";
            try {
                try { throw 1 } catch (e) { throw 2 } finally { log += "F" }
            } catch (e2) { log += e2 }
            log
        """) == "F2"

    def test_return_value_evaluated_before_finally(self):
        assert run("""
            var log = "";
            function v() { log += "v"; return 1 }
            function f() { try { return v() } finally { log += "f" } }
            f() + log
        """) == "1vf"

    def test_return_in_finally_overrides(self):
        assert run("function f() { try { return 1 } finally { return 2 } } f()") == 2

    def test_return_in_finally_overrides_throw(self):
        assert run("function f() { try { throw 1 } finally { return 2 } } f()") == 2

    def test_nested_finally_blocks_run_inner_first(self):
        assert run("""
            var log = "";
            function f() {
                try {
                    try { return "r" } finally { log += "1" }
                } finally { log += "2" }
            }
            f() + log
        """) == "r12"

    def test_finally_not_inlined_into_nested_function(self):
        assert run("""
            var n = 0;
            try { var f = function () { return 1 } } finally { n++ }
            f(); f();
            n
        """) == 1

    def test_throw_in_finally_replaces_exception(self):
        assert run("""
            var r;
            try { try { throw 1 } finally { throw 2 } } catch (e) { r = e }
            r
        """) == 2

    def test_catch_variable_is_thrown_value(self):
        assert run("var r; try { throw 7 } catch (e) { r = e } finally {} r") == 7


class TestBreakContinueThroughTry:
    def test_break_out_of_try_pops_its_handler(self):
        assert run("""
            var r;
            try {
                for (;;) { try { break } catch (e) { r = "inner" } }
                throw 1;
            } catch (e) { r = "outer" }
            r
        """) == "outer"

    def test_continue_out_of_try_pops_its_handler(self):
        assert run("""
            var r = [];
            try {
                for (var i = 0; i < 2; i++) { try { continue } catch (e) { r.push("inner") } }
                throw 1;
            } catch (e) { r.push("outer") }
            r.join()
        """) == "outer"

    def test_break_runs_enclosing_finally_once(self):
        assert run("var n = 0; try { for (;;) { break } } finally { n++ } n") == 1

    def test_break_runs_finally_inside_loop(self):
        assert run("var n = 0; for (;;) { try { break } finally { n++ } } n") == 1

    def test_continue_runs_finally_each_iteration(self):
        assert run("""
            var n = 0;
            for (var i = 0; i < 3; i++) { try { continue } finally { n++ } }
            n
        """) == 3

    def test_break_in_finally_discards_exception(self):
        assert (
            run(
                """
            var n = 0;
            for (var i = 0; i < 20000; i++) {
                for (;;) { try { throw 1 } finally { break } }
                n++;
            }
            n
        """,
                memory_limit=1024 * 1024,
                time_limit=30.0,
            )
            == 20000
        )


class TestStackBalance:
    """Leaving a loop or switch early must pop its stack values."""

    def test_break_out_of_for_in(self):
        assert (
            run(
                "for (var i = 0; i < 20000; i++) { for (var k in {a: 1}) break } i",
                memory_limit=1024 * 1024,
                time_limit=30.0,
            )
            == 20000
        )

    def test_break_out_of_for_of(self):
        assert (
            run(
                "for (var i = 0; i < 20000; i++) { for (var x of [1]) break } i",
                memory_limit=1024 * 1024,
                time_limit=30.0,
            )
            == 20000
        )

    def test_break_out_of_switch(self):
        assert (
            run(
                "for (var i = 0; i < 20000; i++) {"
                " switch (i) { case 0: break; default: break } } i",
                memory_limit=1024 * 1024,
                time_limit=30.0,
            )
            == 20000
        )

    def test_continue_from_switch_inside_loop(self):
        assert (
            run(
                "var n = 0; for (var i = 0; i < 20000; i++) {"
                " switch (i) { default: continue } } i",
                memory_limit=1024 * 1024,
                time_limit=30.0,
            )
            == 20000
        )

    def test_labelled_break_out_of_nested_for_in(self):
        assert (
            run(
                "var n = 0; for (var i = 0; i < 20000; i++) {"
                " outer: for (var a in {x: 1}) { for (var b in {y: 1}) break outer }"
                " n++ } n",
                memory_limit=1024 * 1024,
                time_limit=30.0,
            )
            == 20000
        )


class TestLabels:
    def test_labelled_continue(self):
        assert run("""
            var i, n = 0;
            outer: for (i = 0; i < 3; i++) { for (;;) { n++; continue outer } }
            i + n
        """) == 6

    def test_labelled_continue_with_stacked_labels(self):
        assert run("""
            var n = 0;
            a: b: for (var i = 0; i < 3; i++) { for (;;) { n++; continue a } }
            n
        """) == 3

    def test_labelled_continue_while(self):
        assert run("""
            var i = 0, n = 0;
            outer: while (i < 3) { i++; for (;;) { n++; continue outer } }
            n
        """) == 3

    def test_labelled_break_out_of_block(self):
        assert run("var r = 1; out: { r = 2; break out; r = 3 } r") == 2

    def test_continue_to_non_loop_label_is_syntax_error(self):
        with pytest.raises(JSSyntaxError):
            run("out: { for (;;) { continue out } }")


class TestSyntaxErrors:
    def test_break_outside_loop(self):
        with pytest.raises(JSSyntaxError):
            run("break")

    def test_continue_outside_loop(self):
        with pytest.raises(JSSyntaxError):
            run("continue")

    def test_unknown_label(self):
        with pytest.raises(JSSyntaxError):
            run("for (;;) { break nope }")
