"""Tests for computed object keys and String replace/replaceAll."""

import pytest

from microjs import Context


@pytest.mark.parametrize(
    "source,expected",
    [
        ('var s = "x"; ({[s]: 1}).x', 1),
        ('var s = "x"; ({[s]: 1}).s', None),
        ('({["a" + "b"]: 2}).ab', 2),
        ("({[1 + 1]: 3})[2]", 3),
        ('var k = "n"; var o = {[k]: 1, k: 2}; o.n + o.k', 3),
    ],
)
def test_computed_property_keys(source, expected):
    assert Context(time_limit=5.0).eval(source) == expected


@pytest.mark.parametrize(
    "source,expected",
    [
        # Function replacements receive (match, ...groups, offset, string)
        ('"a1b2".replace(/\\d/g, function (m) { return m * 2 })', "a2b4"),
        (
            '"x-10 y-20".replace(/(\\w)-(\\d+)/g, function (m, a, b, i) {'
            " return b + a + i })",
            "10x0 20y5",
        ),
        ('"abc".replace(/b/, function (m, i, s) { return s })', "aabcc"),
        ('"aXbX".replace("X", function (m, i) { return i })', "a1bX"),
        ('"aXbX".replaceAll("X", function (m, i) { return i })', "a1b3"),
        ('"aXbX".replaceAll(/X/g, function () { return "-" })', "a-b-"),
        # Replacement patterns
        ('"abc".replace("b", "[$&]")', "a[b]c"),
        ('"abc".replace("b", "[$`]")', "a[a]c"),
        ('"abc".replace("b", "[$\']")', "a[c]c"),
        ('"abc".replace("b", "$$")', "a$c"),
        ('"abc".replace(/(b)/, "[$1$2]")', "a[b$2]c"),
        (
            '"abcdefghijk".replace(/(a)(b)(c)(d)(e)(f)(g)(h)(i)(j)(k)/, "$11-$10")',
            "k-j",
        ),
        ('"aaa".replaceAll("a", "$&$&")', "aaaaaa"),
        ('"a.b.c".replaceAll(".", "$`")', "aaba.bc"),
    ],
)
def test_string_replace(source, expected):
    assert Context(time_limit=5.0).eval(source) == expected
