"""
Compatibility tests: run the same JavaScript against both C quickjs and Python implementation.

These tests verify that mquickjs_python produces the same results as the reference C implementation.
"""

import pytest

# Try to import both implementations
try:
    import quickjs as c_quickjs
    C_AVAILABLE = True
except ImportError:
    C_AVAILABLE = False

from mquickjs_python import JSContext


def run_both(js_code):
    """Run JavaScript code on both implementations and return (python_result, c_result)."""
    # Run on Python implementation
    py_ctx = JSContext()
    py_result = py_ctx.eval(js_code)

    # Run on C implementation
    if C_AVAILABLE:
        c_ctx = c_quickjs.Context()
        c_result = c_ctx.eval(js_code)
        return py_result, c_result
    return py_result, None


def normalize(val):
    """Normalize values for comparison (handle type differences between implementations)."""
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return float(val) if isinstance(val, float) else val
    if isinstance(val, str):
        return val
    # For arrays/objects, convert to comparable form
    if hasattr(val, '__iter__') and not isinstance(val, str):
        return list(val)
    return val


@pytest.mark.skipif(not C_AVAILABLE, reason="C quickjs library not installed")
class TestCompatibilityArithmetic:
    """Test arithmetic produces same results."""

    def test_addition(self):
        py, c = run_both("1 + 2")
        assert py == c == 3

    def test_subtraction(self):
        py, c = run_both("10 - 4")
        assert py == c == 6

    def test_multiplication(self):
        py, c = run_both("6 * 7")
        assert py == c == 42

    def test_division(self):
        py, c = run_both("15 / 3")
        assert py == c == 5.0

    def test_modulo(self):
        py, c = run_both("17 % 5")
        assert py == c == 2

    def test_power(self):
        py, c = run_both("2 ** 10")
        assert py == c == 1024

    def test_complex_expression(self):
        py, c = run_both("(2 + 3) * 4 - 6 / 2")
        assert py == c == 17.0


@pytest.mark.skipif(not C_AVAILABLE, reason="C quickjs library not installed")
class TestCompatibilityStrings:
    """Test string operations produce same results."""

    def test_concatenation(self):
        py, c = run_both("'hello' + ' ' + 'world'")
        assert py == c == "hello world"

    def test_length(self):
        py, c = run_both("'hello'.length")
        assert py == c == 5

    def test_charAt(self):
        py, c = run_both("'hello'.charAt(1)")
        assert py == c == "e"

    def test_substring(self):
        py, c = run_both("'hello world'.substring(0, 5)")
        assert py == c == "hello"

    def test_indexOf(self):
        py, c = run_both("'hello world'.indexOf('world')")
        assert py == c == 6

    def test_toUpperCase(self):
        py, c = run_both("'hello'.toUpperCase()")
        assert py == c == "HELLO"

    def test_toLowerCase(self):
        py, c = run_both("'HELLO'.toLowerCase()")
        assert py == c == "hello"


@pytest.mark.skipif(not C_AVAILABLE, reason="C quickjs library not installed")
class TestCompatibilityArrays:
    """Test array operations produce same results."""

    def test_array_literal(self):
        py, c = run_both("[1, 2, 3].length")
        assert py == c == 3

    def test_array_access(self):
        py, c = run_both("[10, 20, 30][1]")
        assert py == c == 20

    def test_array_push(self):
        py, c = run_both("var a = [1, 2]; a.push(3); a.length")
        assert py == c == 3

    def test_array_join(self):
        py, c = run_both("[1, 2, 3].join('-')")
        assert py == c == "1-2-3"


@pytest.mark.skipif(not C_AVAILABLE, reason="C quickjs library not installed")
class TestCompatibilityObjects:
    """Test object operations produce same results."""

    def test_object_property(self):
        py, c = run_both("({x: 10}).x")
        assert py == c == 10

    def test_object_method(self):
        py, c = run_both("({x: 10, getX: function() { return this.x; }}).getX()")
        assert py == c == 10


@pytest.mark.skipif(not C_AVAILABLE, reason="C quickjs library not installed")
class TestCompatibilityFunctions:
    """Test function behavior produces same results."""

    def test_function_call(self):
        py, c = run_both("function add(a, b) { return a + b; } add(3, 4)")
        assert py == c == 7

    def test_closure(self):
        py, c = run_both("""
            function makeCounter() {
                var count = 0;
                return function() { return ++count; };
            }
            var counter = makeCounter();
            counter(); counter(); counter()
        """)
        assert py == c == 3

    def test_arrow_function(self):
        py, c = run_both("((x) => x * 2)(5)")
        assert py == c == 10


@pytest.mark.skipif(not C_AVAILABLE, reason="C quickjs library not installed")
class TestCompatibilityControlFlow:
    """Test control flow produces same results."""

    def test_if_else(self):
        py, c = run_both("var x = 10; if (x > 5) { 'big'; } else { 'small'; }")
        assert py == c == "big"

    def test_ternary(self):
        py, c = run_both("5 > 3 ? 'yes' : 'no'")
        assert py == c == "yes"

    def test_for_loop(self):
        py, c = run_both("var sum = 0; for (var i = 1; i <= 5; i++) sum += i; sum")
        assert py == c == 15

    def test_while_loop(self):
        py, c = run_both("var n = 5; var fact = 1; while (n > 1) { fact *= n; n--; } fact")
        assert py == c == 120


@pytest.mark.skipif(not C_AVAILABLE, reason="C quickjs library not installed")
class TestCompatibilityMath:
    """Test Math functions produce same results."""

    def test_math_abs(self):
        py, c = run_both("Math.abs(-5)")
        assert py == c == 5

    def test_math_floor(self):
        py, c = run_both("Math.floor(3.7)")
        assert py == c == 3

    def test_math_ceil(self):
        py, c = run_both("Math.ceil(3.2)")
        assert py == c == 4

    def test_math_round(self):
        py, c = run_both("Math.round(3.5)")
        assert py == c == 4

    def test_math_max(self):
        py, c = run_both("Math.max(1, 5, 3)")
        assert py == c == 5

    def test_math_min(self):
        py, c = run_both("Math.min(1, 5, 3)")
        assert py == c == 1

    def test_math_pow(self):
        py, c = run_both("Math.pow(2, 8)")
        assert py == c == 256

    def test_math_sqrt(self):
        py, c = run_both("Math.sqrt(16)")
        assert py == c == 4


@pytest.mark.skipif(not C_AVAILABLE, reason="C quickjs library not installed")
class TestCompatibilityTypeConversion:
    """Test type coercion produces same results."""

    def test_string_to_number(self):
        py, c = run_both("Number('42')")
        assert py == c == 42

    def test_number_to_string(self):
        py, c = run_both("String(42)")
        assert py == c == "42"

    def test_boolean_coercion(self):
        py, c = run_both("Boolean(1)")
        assert py == c == True

    def test_string_number_addition(self):
        py, c = run_both("'10' + 5")
        assert py == c == "105"

    def test_string_number_subtraction(self):
        py, c = run_both("'10' - 5")
        assert py == c == 5


@pytest.mark.skipif(not C_AVAILABLE, reason="C quickjs library not installed")
class TestCompatibilityComparison:
    """Test comparison operators produce same results."""

    def test_equals(self):
        py, c = run_both("5 == '5'")
        assert py == c == True

    def test_strict_equals(self):
        py, c = run_both("5 === '5'")
        assert py == c == False

    def test_not_equals(self):
        py, c = run_both("5 != 3")
        assert py == c == True

    def test_less_than(self):
        py, c = run_both("3 < 5")
        assert py == c == True

    def test_greater_than(self):
        py, c = run_both("5 > 3")
        assert py == c == True


# Summary of what would be needed to fix the xfail tests:
#
# 1. test_closure.js: Named function expressions need to make name available in scope
#    - `var f = function myfunc() { return myfunc; }` should work
#
# 2. test_loop.js: Has an infinite loop issue (likely in for-in or labeled statements)
#
# 3. test_language.js: Syntax error - likely needs getter/setter or computed property support
#
# 4. test_rect.js: Requires C-defined Rectangle and FilledRectangle classes (not applicable)
#
# 5. test_builtin.js: Comprehensive built-in tests (many features needed)
#
# 6. mandelbrot.js/microbench.js: Performance tests (need complete VM)
#
# 7. Lookbehind regex: Need to implement positive/negative lookbehind in regex engine
