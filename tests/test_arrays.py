"""Arrays are dense (MQuickJS "stricter mode"): no holes."""

import pytest

from microjs import Context, JSSyntaxError


def run(source):
    return Context(time_limit=5.0).eval(source)


def test_write_past_the_end_is_an_error():
    assert (
        run(
            "var a = [1]; var r; try { a[5] = 1 } catch (e) { r = e.name }"
            " r + a.length + Object.keys(a).length"
        )
        == "TypeError11"
    )


def test_appending_at_the_end_works():
    assert run("var a = [1]; a[1] = 2; a[2] = 3; a.join()") == "1,2,3"


def test_non_index_keys_are_properties():
    assert run("var a = [1, 2]; a[-1] = 5; a.foo = 6; a.length + a[-1] + a.foo") == 13


def test_array_literal_hole_is_syntax_error():
    with pytest.raises(JSSyntaxError):
        run("[1, , 3]")


def test_array_literal_trailing_comma_is_allowed():
    assert run("[1, 2, ].length") == 2


@pytest.mark.parametrize(
    "source,expected",
    [
        ("Object.keys([5, 6]).join()", "0,1"),
        ("var a = [5, 6]; a.x = 1; Object.keys(a).join()", "0,1,x"),
        ("Object.values([5, 6]).join()", "5,6"),
        ('JSON.stringify(Object.entries(["a"]))', '[["0","a"]]'),
        ('Object.keys("ab").join()', "0,1"),
        ("Object.keys({get x() { return 1 }, y: 2}).join()", "x,y"),
        ("Object.values({get x() { return 1 }}).join()", "1"),
        ("JSON.stringify(Object.assign({}, {get x() { return 7 }}))", '{"x":7}'),
        ("var r = []; for (var k in {get x() { return 1 }}) r.push(k); r.join()", "x"),
    ],
)
def test_own_enumerable_keys(source, expected):
    assert run(source) == expected
