"""Commonly used built-ins beyond ES5 (expected values checked with Node.js)."""

import pytest

from microjs import Context


@pytest.mark.parametrize(
    "source,expected",
    [
        # Object
        ("Object.is(NaN, NaN)", True),
        ("Object.is(0, -0)", False),
        ('Object.is("a", "a")', True),
        ('JSON.stringify(Object.fromEntries([["a", 1], ["b", 2]]))', '{"a":1,"b":2}'),
        ("Object.getOwnPropertyNames({a: 1, b: 2}).join()", "a,b"),
        ("Object.getOwnPropertyNames([1, 2]).join()", "0,1,length"),
        (
            "function F() {} Object.getOwnPropertyNames(F.prototype).join()",
            "constructor",
        ),
        ("Object.getOwnPropertyDescriptors({a: 1}).a.value", 1),
        ('({a: 1}).propertyIsEnumerable("a")', True),
        ('[].propertyIsEnumerable("length")', False),
        ("({}).toLocaleString()", "[object Object]"),
        # Freezing and sealing
        ("var o = Object.freeze({a: 1}); Object.isFrozen(o)", True),
        ("Object.isFrozen({a: 1})", False),
        (
            "var o = Object.freeze({a: 1}); var r; try { o.a = 2 } catch (e) { r = e.name } r + o.a",
            "TypeError1",
        ),
        (
            "var o = Object.freeze({}); var r; try { o.b = 2 } catch (e) { r = e.name } r",
            "TypeError",
        ),
        (
            "var o = Object.freeze({a: 1}); var r; try { delete o.a } catch (e) { r = e.name } r",
            "TypeError",
        ),
        (
            "var a = Object.freeze([1]); var r; try { a.push(2) } catch (e) { r = e.name } r + a.length",
            "TypeError1",
        ),
        (
            "var a = Object.freeze([1]); var r; try { a[0] = 5 } catch (e) { r = e.name } r + a[0]",
            "TypeError1",
        ),
        (
            "var o = Object.seal({a: 1}); o.a = 2; var r; try { o.b = 1 } catch (e) { r = e.name } r + o.a",
            "TypeError2",
        ),
        ("Object.isSealed(Object.seal({}))", True),
        ("Object.isSealed(Object.freeze({}))", True),
        (
            "var o = Object.preventExtensions({a: 1}); delete o.a; Object.isExtensible(o) + ':' + ('a' in o)",
            "false:false",
        ),
        ("Object.isExtensible({})", True),
        ("Object.freeze(5)", 5),
        # Array statics
        ('Array.from("abc").join("-")', "a-b-c"),
        ("Array.from({length: 3}, function (_, i) { return i * 2 }).join()", "0,2,4"),
        ("Array.from([1, 2], function (x) { return x + 1 }).join()", "2,3"),
        ("Array.of(7, 8).join()", "7,8"),
        ("Array.of(3).length", 1),
        # Array.prototype
        ("[1, 2, 3].at(-1)", 3),
        ("[1, 2, 3].at(5)", None),
        ("[1, [2, [3, [4]]]].flat().length", 3),
        ("[1, [2, [3, [4]]]].flat(Infinity).join()", "1,2,3,4"),
        ("[1, 2].flatMap(function (x) { return [x, x * 10] }).join()", "1,10,2,20"),
        ("[1, 2, 3, 4].findLast(function (x) { return x % 2 })", 3),
        ("[1, 2, 3, 4].findLastIndex(function (x) { return x > 9 })", -1),
        ("[1, 2, 3, 4].fill(0, 1, 3).join()", "1,0,0,4"),
        ("new Array(3).fill(7).join()", "7,7,7"),
        ("[1, 2, 3, 4, 5].copyWithin(0, 3).join()", "4,5,3,4,5"),
        ("var a = [3, 1, 2]; a.toSorted().join() + '|' + a.join()", "1,2,3|3,1,2"),
        ("var a = [1, 2, 3]; a.toReversed().join() + '|' + a.join()", "3,2,1|1,2,3"),
        (
            "var a = [1, 2, 3]; a.toSpliced(1, 1, 9, 9).join() + '|' + a.join()",
            "1,9,9,3|1,2,3",
        ),
        ("var a = [1, 2, 3]; a.with(1, 5).join() + '|' + a.join()", "1,5,3|1,2,3"),
        ("[1, 2].toLocaleString()", "1,2"),
        # String
        ("String.fromCodePoint(72, 105)", "Hi"),
        ('"abc".at(-1)', "c"),
        ('"abc".at(3)', None),
        ('"abc".codePointAt(1)', 98),
        ('"a".localeCompare("b")', -1),
        ('"b".localeCompare("a")', 1),
        ('"a".localeCompare("a")', 0),
        ('"\\u0041\\u030a".normalize("NFC").length', 1),
        ('"  x  ".trimLeft() + "|"', "x  |"),
        ('"  x  ".trimRight() + "|"', "  x|"),
        ('"abcdef".substr(2, 3)', "cde"),
        ('"abcdef".substr(-2)', "ef"),
        ('"ABC".toLocaleLowerCase()', "abc"),
        ('"abc".toLocaleUpperCase()', "ABC"),
        # URI encoding
        ('encodeURIComponent("a b&c/d?é")', "a%20b%26c%2Fd%3F%C3%A9"),
        (
            'encodeURI("http://x.com/a b?q=1&r=é#h")',
            "http://x.com/a%20b?q=1&r=%C3%A9#h",
        ),
        ('decodeURIComponent("a%20b%26%C3%A9")', "a b&é"),
        ('decodeURI("a%20b%26")', "a b%26"),
        (
            'var r; try { decodeURIComponent("%") } catch (e) { r = e.name } r',
            "URIError",
        ),
    ],
)
def test_builtins(source, expected):
    assert Context(time_limit=5.0).eval(source) == expected
