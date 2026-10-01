"""Tests for the sandbox's resource limits and JavaScript's built-in limits."""

import time
import tracemalloc

import pytest

import microjs.values
from microjs import Context, MemoryLimitError, TimeLimitError

pytestmark = pytest.mark.timeout(30)


def run(source, **kwargs):
    kwargs.setdefault("time_limit", 5.0)
    return Context(**kwargs).eval(source)


def caught_name(source, **kwargs):
    """Run source inside try/catch and return the caught error's name."""
    return run(
        f"var r = 'none'; try {{ {source} }} catch (e) {{ r = e.name }} r", **kwargs
    )


class TestEngineLimits:
    """RangeErrors JavaScript defines regardless of the sandbox limits."""

    @pytest.mark.parametrize(
        "source",
        [
            "new Array(-1)",
            "new Array(1.5)",
            "new Array(2 ** 32)",
            "Array(-1)",
            "var a = []; a.length = -1",
            '"x".repeat(-1)',
            '"x".repeat(Infinity)',
            '"x".repeat(2 ** 29)',
            '"x".padStart(2 ** 30)',
            '"x".padEnd(2 ** 30, "ab")',
        ],
    )
    def test_range_errors(self, source):
        assert caught_name(source) == "RangeError"

    def test_valid_lengths_still_work(self):
        assert run("new Array(3).length + Array(2).length + '-'.repeat(4).length") == 9
        assert run('"x".repeat(0) + "x".padStart(3, "ab")') == "abx"

    def test_string_concatenation_beyond_max_length(self, monkeypatch):
        monkeypatch.setattr(microjs.values, "MAX_STRING_LENGTH", 1000)
        assert caught_name('var s = "x".repeat(600); s + s') == "RangeError"
        assert run('var s = "x".repeat(400); (s + s).length') == 800

    def test_join_beyond_max_length(self, monkeypatch):
        monkeypatch.setattr(microjs.values, "MAX_STRING_LENGTH", 1000)
        assert caught_name('new Array(100).join("x".repeat(20))') == "RangeError"

    def test_replace_all_beyond_max_length(self, monkeypatch):
        monkeypatch.setattr(microjs.values, "MAX_STRING_LENGTH", 1000)
        source = '"a".repeat(100).replaceAll("a", "b".repeat(20))'
        assert caught_name(source) == "RangeError"

    def test_call_depth_is_limited(self):
        start = time.monotonic()
        assert caught_name("function f() { return f() } f()", time_limit=30.0) == (
            "RangeError"
        )
        assert time.monotonic() - start < 10

    def test_moderate_recursion_works(self):
        assert run("function f(n) { return n ? 1 + f(n - 1) : 0 } f(5000)") == 5000


def peak_memory(source, **kwargs):
    """Run source, returning (exception or None, peak bytes allocated)."""
    tracemalloc.start()
    try:
        run(source, **kwargs)
        error = None
    except Exception as e:
        error = e
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return error, peak


MB = 1024 * 1024


class TestMemoryLimit:
    """memory_limit bounds what a script can allocate."""

    @pytest.mark.parametrize(
        "source",
        [
            '"x".repeat(20000000)',
            "new Array(10000000)",
            '"x".repeat(500000).split("")',
            '"a".repeat(3000).replaceAll("a", "b".repeat(3000))',
            'new Array(3000).join("x".repeat(3000))',
            '"x".repeat(1000000).padEnd(30000000)',
            'var s = "x".repeat(600000); s + s',
        ],
    )
    def test_large_allocations_are_refused_up_front(self, source):
        error, peak = peak_memory(source, memory_limit=MB, time_limit=30.0)
        assert isinstance(error, MemoryLimitError), error
        assert peak < 10 * MB

    @pytest.mark.parametrize(
        "source",
        [
            'var s = "x"; for (var i = 0; i < 30; i++) s = s + s',
            "var a = []; for (var i = 0; i < 1000000; i++) a.push(i, i, i, i, i, i, i, i)",
            'var o = {}; for (var i = 0; i < 1000000; i++) o["k" + i] = i',
            "var a = []; for (;;) a = [a, a]",
            "var fs = []; for (;;) fs.push(function () {})",
        ],
    )
    def test_growing_data_is_stopped(self, source):
        with pytest.raises(MemoryLimitError):
            run(source, memory_limit=MB, time_limit=30.0)

    def test_short_lived_garbage_does_not_count(self):
        """Only live memory counts, not everything ever allocated."""
        result = run(
            """
            var total = 0;
            for (var i = 0; i < 10000; i++) {
                var s = "item" + i, a = [s, s, s], o = {s: s, a: a};
                total += a.length;
            }
            total
            """,
            memory_limit=MB,
            time_limit=60.0,
        )
        assert result == 30000

    def test_live_data_under_the_limit_is_fine(self):
        result = run(
            'var a = []; for (var i = 0; i < 2000; i++) a.push("x" + i); a.length',
            memory_limit=MB,
        )
        assert result == 2000

    def test_deep_recursion_hits_a_limit(self):
        with pytest.raises((MemoryLimitError, microjs.JSRangeError)):
            run("function f(n) { return f(n + 1) + 1 } f(0)", memory_limit=MB)


class TestTimeLimitInsideBuiltins:
    """Long-running native functions still respect the time limit."""

    @pytest.mark.parametrize(
        "source",
        [
            'var a = "x".repeat(400000).split(""); a.sort(); a.sort(); a.sort()',
            "for (;;) new Array(3000000).join()",
            'var a = "ab".repeat(300000).split(""); for (;;) a.indexOf("z")',
        ],
    )
    def test_builtin_loops_check_the_deadline(self, source):
        start = time.monotonic()
        with pytest.raises(TimeLimitError):
            run(source, time_limit=0.5)
        assert time.monotonic() - start < 3
