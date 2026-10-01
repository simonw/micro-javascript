"""Functions are objects: they have properties and a prototype chain."""

import pytest

from microjs import Context
from microjs.values import JSFunction


@pytest.mark.parametrize(
    "source,expected",
    [
        ("function F() {} F.x = 1; F.x", 1),
        (
            "function F() {} F.create = function () { return new F() };"
            " F.create() instanceof F",
            True,
        ),
        (
            'function F() {} F.prototype = {greet: function () { return "hello" }};'
            " new F().greet()",
            "hello",
        ),
        (
            """
            function Animal(name) { this.name = name }
            Animal.prototype.speak = function () { return this.name + " speaks" };
            function Dog(name) { Animal.call(this, name) }
            Dog.prototype = Object.create(Animal.prototype);
            Dog.prototype.constructor = Dog;
            var d = new Dog("Rex");
            [d.speak(), d instanceof Dog, d instanceof Animal, d.constructor === Dog].join()
            """,
            "Rex speaks,true,true,true",
        ),
        ("(function () {}) instanceof Function", True),
        ("(function () {}) instanceof Object", True),
        ("Object.getPrototypeOf(function () {}) === Function.prototype", True),
        ("Object.keys(function () {}).length", 0),
        ("function F() {} Object.keys(F.prototype).length", 0),
        ("function F() {} F.prototype.constructor === F", True),
        ("function f(a, b) {} f.length + f.name", "2f"),
        ("var g = function named() {}; g.name", "named"),
        ("(function () {}).name", ""),
        ("function F() { this.x = 1 } var o = new F(); o.hasOwnProperty('x')", True),
        ("function F() {} F.count = 0; F.count++; F.count++; F.count", 2),
        ("function f() {} delete f.x; f.y = 2; 'y' in f", True),
        ("JSON.stringify({f: function () {}, a: 1})", '{"a":1}'),
        ("JSON.stringify([function () {}])", "[null]"),
        ("typeof function () {}", "function"),
        ("var f = function () {}; f.prototype.m = 1; new f().m", 1),
    ],
)
def test_function_objects(source, expected):
    assert Context(time_limit=5.0).eval(source) == expected


def test_function_returned_to_python():
    result = Context(time_limit=5.0).eval("(function add(a, b) { return a + b })")
    assert isinstance(result, JSFunction)
