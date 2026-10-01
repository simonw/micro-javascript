"""Built-in methods live on real prototype objects."""

import pytest

from microjs import Context


@pytest.mark.parametrize(
    "source,expected",
    [
        # One function object per method, shared by every instance
        ("Array.prototype.sort === [].sort", True),
        ("[].push === [].push", True),
        ('"a".charAt === String.prototype.charAt', True),
        ("(1).toFixed === Number.prototype.toFixed", True),
        ("(function () {}).call === Function.prototype.call", True),
        # Constructors and prototypes point at each other
        ("[].constructor === Array", True),
        ('"abc".constructor === String', True),
        ("(5).constructor === Number", True),
        ("true.constructor === Boolean", True),
        ("/x/.constructor === RegExp", True),
        ("({}).constructor === Object", True),
        ("Object.getPrototypeOf([]) === Array.prototype", True),
        ("Object.getPrototypeOf({}) === Object.prototype", True),
        ("Object.getPrototypeOf(Array.prototype) === Object.prototype", True),
        ("Object.getPrototypeOf(Array) === Function.prototype", True),
        ("typeof Function.prototype", "function"),
        ("Object.keys(Array.prototype).length", 0),
        ('"x".split(",").join === Array.prototype.join', True),
        # Methods called on other values with call/apply
        ('Array.prototype.slice.call({length: 2, 0: "a", 1: "b"}).join()', "a,b"),
        ('Array.prototype.join.call("abc", "-")', "a-b-c"),
        (
            "(function () { return Array.prototype.slice.call(arguments, 1) })"
            "(1, 2, 3).join()",
            "2,3",
        ),
        (
            'var o = {length: 0}; Array.prototype.push.call(o, "a"); o.length + o[0]',
            "1a",
        ),
        ("var push = Array.prototype.push, a = []; push.call(a, 1); a.length", 1),
        ('Object.prototype.hasOwnProperty.call({a: 1}, "a")', True),
        ("Object.prototype.toString.call(null)", "[object Null]"),
        ("Object.prototype.toString.call(function () {})", "[object Function]"),
        ("Object.prototype.toString.call(new TypeError())", "[object Error]"),
        ('String.prototype.toUpperCase.call("abc")', "ABC"),
        ("Math.max.apply(null, [1, 5, 3])", 5),
        ("Math.max.call(null, 1, 2)", 2),
        ("Function.prototype.apply.call(Math.max, null, [1, 3])", 3),
        # Scripts can extend and override built-ins
        (
            "Array.prototype.last = function () { return this[this.length - 1] }; [1, 2].last()",
            2,
        ),
        (
            'String.prototype.shout = function () { return this + "!" }; "hi".shout()',
            "hi!",
        ),
        ("Number.prototype.double = function () { return this * 2 }; (4).double()", 8),
        (
            "Boolean.prototype.flip = function () { return !this.valueOf() }; true.flip()",
            False,
        ),
        (
            "Function.prototype.twice = function () { return this() * 2 }; (function () { return 3 }).twice()",
            6,
        ),
        (
            'Object.prototype.hello = function () { return "hi" }; [].hello() + ({}).hello()',
            "hihi",
        ),
        (
            'Array.prototype.toString = function () { return "custom" }; String([1])',
            "custom",
        ),
        ('Array.prototype.join = function () { return "J" }; [1, 2].join()', "J"),
        ("var a = [3, 1, 2]; a.sort = null; a.sort", None),
        # Error types inherit from Error
        ('new TypeError("x") instanceof Error', True),
        ("new RangeError() instanceof Error", True),
        ("new SyntaxError() instanceof TypeError", False),
        ('new TypeError("x").toString()', "TypeError: x"),
        ('String(new Error("m"))', "Error: m"),
        ('"" + new RangeError("r")', "RangeError: r"),
        ("Object.getPrototypeOf(TypeError.prototype) === Error.prototype", True),
        ('var e = new TypeError("t"); e.name + ":" + e.message', "TypeError:t"),
        ("new Error().message", ""),
        # instanceof with built-in constructors
        ("[] instanceof Array", True),
        ("[] instanceof Object", True),
        ('"s" instanceof String', False),
        ("/x/ instanceof RegExp", True),
        ("({}) instanceof Array", False),
        ("Array instanceof Function", True),
        # Accessors are found along the chain and called on the receiver
        (
            "var proto = {get who() { return this.name }};"
            ' var o = Object.create(proto); o.name = "o"; o.who',
            "o",
        ),
        ("var o = {x: 1}; var c = Object.create(o); c.x = 2; o.x + c.x", 3),
    ],
)
def test_prototypes(source, expected):
    assert Context(time_limit=5.0).eval(source) == expected
