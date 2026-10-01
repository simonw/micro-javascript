"""Equality operators, with expected values computed by Node.js."""

import pytest

from microjs import Context

CASES = [
    ("null == undefined", True),
    ("null == 0", False),
    ("undefined == 0", False),
    ("null == false", False),
    ('"" == 0', True),
    ('"0" == false', True),
    ('" \\t" == 0', True),
    ("[] == false", True),
    ('[] == ""', True),
    ("[1] == 1", True),
    ('[1, 2] == "1,2"', True),
    ("NaN == NaN", False),
    ('({}) == "[object Object]"', True),
    ("[] == []", False),
    ("true == 1", True),
    ('true == "1"', True),
    ('"1e3" == 1000', True),
    ("0 === -0", True),
    ("NaN === NaN", False),
    ('"1" === 1', False),
    ("null === null", True),
    ("undefined === undefined", True),
    ("var o = {}; o == o", True),
    ("var o = {valueOf: function () { return 5 }}; o == 5", True),
    ('1 != "1"', False),
    ('1 !== "1"', True),
    ("null != undefined", False),
]


@pytest.mark.parametrize("source,expected", CASES, ids=[c[0] for c in CASES])
def test_equality(source, expected):
    assert Context(time_limit=5.0).eval(source) is expected
