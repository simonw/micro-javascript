"""
JavaScript feature tests for microjs.

These tests verify that microjs correctly implements JavaScript behavior.
"""

import pytest

from microjs import JSContext


def run_js(js_code):
    """Run JavaScript code and return the result."""
    ctx = JSContext()
    return ctx.eval(js_code)


class TestArithmetic:
    """Test arithmetic operations."""

    def test_addition(self):
        assert run_js("1 + 2") == 3

    def test_subtraction(self):
        assert run_js("10 - 4") == 6

    def test_multiplication(self):
        assert run_js("6 * 7") == 42

    def test_division(self):
        assert run_js("15 / 3") == 5.0

    def test_modulo(self):
        assert run_js("17 % 5") == 2

    def test_power(self):
        assert run_js("2 ** 10") == 1024

    def test_complex_expression(self):
        assert run_js("(2 + 3) * 4 - 6 / 2") == 17.0


class TestStrings:
    """Test string operations."""

    def test_concatenation(self):
        assert run_js("'hello' + ' ' + 'world'") == "hello world"

    def test_length(self):
        assert run_js("'hello'.length") == 5

    def test_charAt(self):
        assert run_js("'hello'.charAt(1)") == "e"

    def test_substring(self):
        assert run_js("'hello world'.substring(0, 5)") == "hello"

    def test_indexOf(self):
        assert run_js("'hello world'.indexOf('world')") == 6

    def test_toUpperCase(self):
        assert run_js("'hello'.toUpperCase()") == "HELLO"

    def test_toLowerCase(self):
        assert run_js("'HELLO'.toLowerCase()") == "hello"


class TestArrays:
    """Test array operations."""

    def test_array_literal(self):
        assert run_js("[1, 2, 3].length") == 3

    def test_array_access(self):
        assert run_js("[10, 20, 30][1]") == 20

    def test_array_push(self):
        assert run_js("var a = [1, 2]; a.push(3); a.length") == 3

    def test_array_join(self):
        assert run_js("[1, 2, 3].join('-')") == "1-2-3"


class TestObjects:
    """Test object operations."""

    def test_object_property(self):
        assert run_js("({x: 10}).x") == 10

    def test_object_method(self):
        assert run_js("({x: 10, getX: function() { return this.x; }}).getX()") == 10


class TestFunctions:
    """Test function behavior."""

    def test_function_call(self):
        assert run_js("function add(a, b) { return a + b; } add(3, 4)") == 7

    def test_closure(self):
        result = run_js("""
            function makeCounter() {
                var count = 0;
                return function() { return ++count; };
            }
            var counter = makeCounter();
            counter(); counter(); counter()
        """)
        assert result == 3

    def test_arrow_function(self):
        assert run_js("((x) => x * 2)(5)") == 10


class TestControlFlow:
    """Test control flow."""

    def test_if_else(self):
        assert run_js("var x = 10; if (x > 5) { 'big'; } else { 'small'; }") == "big"

    def test_ternary(self):
        assert run_js("5 > 3 ? 'yes' : 'no'") == "yes"

    def test_for_loop(self):
        assert run_js("var sum = 0; for (var i = 1; i <= 5; i++) sum += i; sum") == 15

    def test_while_loop(self):
        assert run_js("var n = 5; var fact = 1; while (n > 1) { fact *= n; n--; } fact") == 120


class TestMath:
    """Test Math functions."""

    def test_math_abs(self):
        assert run_js("Math.abs(-5)") == 5

    def test_math_floor(self):
        assert run_js("Math.floor(3.7)") == 3

    def test_math_ceil(self):
        assert run_js("Math.ceil(3.2)") == 4

    def test_math_round(self):
        assert run_js("Math.round(3.5)") == 4

    def test_math_max(self):
        assert run_js("Math.max(1, 5, 3)") == 5

    def test_math_min(self):
        assert run_js("Math.min(1, 5, 3)") == 1

    def test_math_pow(self):
        assert run_js("Math.pow(2, 8)") == 256

    def test_math_sqrt(self):
        assert run_js("Math.sqrt(16)") == 4


class TestTypeConversion:
    """Test type coercion."""

    def test_string_to_number(self):
        assert run_js("Number('42')") == 42

    def test_number_to_string(self):
        assert run_js("String(42)") == "42"

    def test_boolean_coercion(self):
        assert run_js("Boolean(1)") == True

    def test_string_number_addition(self):
        assert run_js("'10' + 5") == "105"

    def test_string_number_subtraction(self):
        assert run_js("'10' - 5") == 5


class TestComparison:
    """Test comparison operators."""

    def test_equals(self):
        assert run_js("5 == '5'") == True

    def test_strict_equals(self):
        assert run_js("5 === '5'") == False

    def test_not_equals(self):
        assert run_js("5 != 3") == True

    def test_less_than(self):
        assert run_js("3 < 5") == True

    def test_greater_than(self):
        assert run_js("5 > 3") == True
