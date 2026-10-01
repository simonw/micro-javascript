"""Tests for converting values between Python and JavaScript."""

import pytest

from microjs import Context


def test_cyclic_array_result():
    result = Context(time_limit=5.0).eval("var a = [1]; a.push(a); a")
    assert result[0] == 1
    assert result[1] is result


def test_cyclic_object_result():
    result = Context(time_limit=5.0).eval("var o = {n: 1}; o.self = o; o")
    assert result["n"] == 1
    assert result["self"] is result


def test_shared_references_are_preserved():
    result = Context(time_limit=5.0).eval("var x = {v: 1}; [x, x]")
    assert result[0] is result[1]


def test_deeply_nested_result():
    result = Context(time_limit=10.0).eval("""
        var root = [], node = root;
        for (var i = 0; i < 5000; i++) { var child = []; node.push(child); node = child }
        root
    """)
    depth = 0
    while result:
        result = result[0]
        depth += 1
    assert depth == 5000


def test_deeply_nested_python_value_passed_in():
    deep = []
    node = deep
    for _ in range(5000):
        child = []
        node.append(child)
        node = child
    ctx = Context(time_limit=10.0)
    ctx.set("deep", deep)
    assert ctx.eval("var d = 0, n = deep; while (n.length) { n = n[0]; d++ } d") == 5000


def test_cyclic_python_value_passed_in():
    cyclic = {"name": "x"}
    cyclic["self"] = cyclic
    ctx = Context(time_limit=5.0)
    ctx.set("c", cyclic)
    assert ctx.eval("c.self.self.name") == "x"


def test_json_stringify_cycle_is_type_error():
    result = Context(time_limit=5.0).eval(
        "var o = {}; o.o = o; var r; try { JSON.stringify(o) } catch (e) { r = e.name } r"
    )
    assert result == "TypeError"


def test_json_stringify_repeated_non_cyclic_reference():
    assert (
        Context(time_limit=5.0).eval("var x = {a: 1}; JSON.stringify([x, x])")
        == '[{"a":1},{"a":1}]'
    )
