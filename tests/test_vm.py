"""Tests for the JavaScript VM and context."""

import pytest
from mquickjs_python import JSContext, JSError, JSSyntaxError


class TestJSContextBasics:
    """Test basic context functionality."""

    def test_evaluate_number(self):
        """Evaluate a simple number."""
        ctx = JSContext()
        assert ctx.eval("42") == 42

    def test_evaluate_float(self):
        """Evaluate a float."""
        ctx = JSContext()
        assert ctx.eval("3.14") == 3.14

    def test_evaluate_string(self):
        """Evaluate a string literal."""
        ctx = JSContext()
        assert ctx.eval('"hello"') == "hello"

    def test_evaluate_boolean_true(self):
        """Evaluate boolean true."""
        ctx = JSContext()
        assert ctx.eval("true") is True

    def test_evaluate_boolean_false(self):
        """Evaluate boolean false."""
        ctx = JSContext()
        assert ctx.eval("false") is False

    def test_evaluate_null(self):
        """Evaluate null."""
        ctx = JSContext()
        assert ctx.eval("null") is None


class TestArithmetic:
    """Test arithmetic operations."""

    def test_addition(self):
        """Test addition."""
        ctx = JSContext()
        assert ctx.eval("1 + 2") == 3

    def test_subtraction(self):
        """Test subtraction."""
        ctx = JSContext()
        assert ctx.eval("5 - 3") == 2

    def test_multiplication(self):
        """Test multiplication."""
        ctx = JSContext()
        assert ctx.eval("4 * 5") == 20

    def test_division(self):
        """Test division."""
        ctx = JSContext()
        assert ctx.eval("20 / 4") == 5.0

    def test_modulo(self):
        """Test modulo."""
        ctx = JSContext()
        assert ctx.eval("10 % 3") == 1

    def test_complex_expression(self):
        """Test complex expression with precedence."""
        ctx = JSContext()
        assert ctx.eval("2 + 3 * 4") == 14

    def test_parentheses(self):
        """Test parentheses."""
        ctx = JSContext()
        assert ctx.eval("(2 + 3) * 4") == 20

    def test_unary_minus(self):
        """Test unary minus."""
        ctx = JSContext()
        assert ctx.eval("-5") == -5


class TestVariables:
    """Test variable operations."""

    def test_var_declaration(self):
        """Test variable declaration."""
        ctx = JSContext()
        result = ctx.eval("var x = 10; x")
        assert result == 10

    def test_var_assignment(self):
        """Test variable assignment."""
        ctx = JSContext()
        result = ctx.eval("var x = 5; x = 10; x")
        assert result == 10

    def test_compound_assignment(self):
        """Test compound assignment."""
        ctx = JSContext()
        result = ctx.eval("var x = 10; x += 5; x")
        assert result == 15

    def test_multiple_vars(self):
        """Test multiple variable declarations."""
        ctx = JSContext()
        result = ctx.eval("var a = 1, b = 2; a + b")
        assert result == 3


class TestComparisons:
    """Test comparison operations."""

    def test_less_than(self):
        """Test less than."""
        ctx = JSContext()
        assert ctx.eval("1 < 2") is True
        assert ctx.eval("2 < 1") is False

    def test_greater_than(self):
        """Test greater than."""
        ctx = JSContext()
        assert ctx.eval("2 > 1") is True
        assert ctx.eval("1 > 2") is False

    def test_equal(self):
        """Test equality."""
        ctx = JSContext()
        assert ctx.eval("1 == 1") is True
        assert ctx.eval("1 == 2") is False

    def test_strict_equal(self):
        """Test strict equality."""
        ctx = JSContext()
        assert ctx.eval("1 === 1") is True

    def test_not_equal(self):
        """Test not equal."""
        ctx = JSContext()
        assert ctx.eval("1 != 2") is True
        assert ctx.eval("1 != 1") is False


class TestLogical:
    """Test logical operations."""

    def test_logical_and(self):
        """Test logical AND."""
        ctx = JSContext()
        assert ctx.eval("true && true") is True
        assert ctx.eval("true && false") is False

    def test_logical_or(self):
        """Test logical OR."""
        ctx = JSContext()
        assert ctx.eval("false || true") is True
        assert ctx.eval("false || false") is False

    def test_logical_not(self):
        """Test logical NOT."""
        ctx = JSContext()
        assert ctx.eval("!true") is False
        assert ctx.eval("!false") is True


class TestConditionals:
    """Test conditional operations."""

    def test_ternary(self):
        """Test ternary operator."""
        ctx = JSContext()
        assert ctx.eval("true ? 1 : 2") == 1
        assert ctx.eval("false ? 1 : 2") == 2

    def test_if_statement(self):
        """Test if statement."""
        ctx = JSContext()
        result = ctx.eval("var x = 0; if (true) x = 1; x")
        assert result == 1

    def test_if_else_statement(self):
        """Test if-else statement."""
        ctx = JSContext()
        result = ctx.eval("var x = 0; if (false) x = 1; else x = 2; x")
        assert result == 2


class TestLoops:
    """Test loop operations."""

    def test_while_loop(self):
        """Test while loop."""
        ctx = JSContext()
        result = ctx.eval("var x = 0; while (x < 5) x = x + 1; x")
        assert result == 5

    def test_for_loop(self):
        """Test for loop."""
        ctx = JSContext()
        result = ctx.eval("var sum = 0; for (var i = 0; i < 5; i++) sum = sum + i; sum")
        assert result == 10

    def test_do_while_loop(self):
        """Test do-while loop."""
        ctx = JSContext()
        result = ctx.eval("var x = 0; do { x = x + 1; } while (x < 3); x")
        assert result == 3

    def test_break(self):
        """Test break statement."""
        ctx = JSContext()
        result = ctx.eval("var x = 0; while (true) { x = x + 1; if (x >= 3) break; } x")
        assert result == 3


class TestFunctions:
    """Test function operations."""

    def test_function_declaration(self):
        """Test function declaration."""
        ctx = JSContext()
        result = ctx.eval("function add(a, b) { return a + b; } add(2, 3)")
        assert result == 5

    def test_function_expression(self):
        """Test function expression."""
        ctx = JSContext()
        result = ctx.eval("var mul = function(a, b) { return a * b; }; mul(3, 4)")
        assert result == 12


class TestArrays:
    """Test array operations."""

    def test_array_literal(self):
        """Test array literal."""
        ctx = JSContext()
        result = ctx.eval("[1, 2, 3]")
        assert result == [1, 2, 3]

    def test_array_access(self):
        """Test array access."""
        ctx = JSContext()
        result = ctx.eval("var arr = [10, 20, 30]; arr[1]")
        assert result == 20

    def test_array_length(self):
        """Test array length."""
        ctx = JSContext()
        result = ctx.eval("var arr = [1, 2, 3, 4, 5]; arr.length")
        assert result == 5


class TestObjects:
    """Test object operations."""

    def test_object_literal(self):
        """Test object literal."""
        ctx = JSContext()
        result = ctx.eval("({a: 1, b: 2})")
        assert result == {"a": 1, "b": 2}

    def test_object_property_access(self):
        """Test object property access."""
        ctx = JSContext()
        result = ctx.eval("var obj = {x: 10}; obj.x")
        assert result == 10

    def test_object_property_set(self):
        """Test object property set."""
        ctx = JSContext()
        result = ctx.eval("var obj = {}; obj.x = 5; obj.x")
        assert result == 5


class TestStrings:
    """Test string operations."""

    def test_string_concatenation(self):
        """Test string concatenation."""
        ctx = JSContext()
        result = ctx.eval('"hello" + " " + "world"')
        assert result == "hello world"

    def test_string_length(self):
        """Test string length."""
        ctx = JSContext()
        result = ctx.eval('"hello".length')
        assert result == 5


class TestGlobalAccess:
    """Test global variable access."""

    def test_set_global(self):
        """Test setting a global variable."""
        ctx = JSContext()
        ctx.set("x", 42)
        result = ctx.eval("x")
        assert result == 42

    def test_get_global(self):
        """Test getting a global variable."""
        ctx = JSContext()
        ctx.eval("var myVar = 100")
        result = ctx.get("myVar")
        assert result == 100
"""Test void operator."""
import pytest
from mquickjs_python import JSContext

class TestVoidOperator:
    def test_void_returns_undefined(self):
        ctx = JSContext()
        result = ctx.eval("void 0")
        assert result is None or str(result) == "undefined"

    def test_void_expression(self):
        ctx = JSContext()
        result = ctx.eval("void (1 + 2)")
        assert result is None or str(result) == "undefined"

    def test_void_function_call(self):
        ctx = JSContext()
        result = ctx.eval("var x = 0; void (x = 5); x")
        assert result == 5  # Side effect happens, but void returns undefined
"""Test for...of loops."""
import pytest
from mquickjs_python import JSContext

class TestForOf:
    def test_for_of_array(self):
        """Basic for...of with array."""
        ctx = JSContext()
        result = ctx.eval('''
            var sum = 0;
            var arr = [1, 2, 3, 4, 5];
            for (var x of arr) {
                sum += x;
            }
            sum
        ''')
        assert result == 15

    def test_for_of_string(self):
        """for...of with string iterates characters."""
        ctx = JSContext()
        result = ctx.eval('''
            var chars = [];
            for (var c of "abc") {
                chars.push(c);
            }
            chars.join(",")
        ''')
        assert result == "a,b,c"
"""Test getter/setter property syntax."""
import pytest
from mquickjs_python import JSContext

class TestGetterSetter:
    def test_getter(self):
        """Basic getter."""
        ctx = JSContext()
        result = ctx.eval('''
            var obj = {
                _x: 10,
                get x() { return this._x; }
            };
            obj.x
        ''')
        assert result == 10

    def test_setter(self):
        """Basic setter."""
        ctx = JSContext()
        result = ctx.eval('''
            var obj = {
                _x: 0,
                set x(v) { this._x = v; }
            };
            obj.x = 42;
            obj._x
        ''')
        assert result == 42

    def test_getter_setter_combined(self):
        """Getter and setter together."""
        ctx = JSContext()
        result = ctx.eval('''
            var obj = {
                _value: 5,
                get value() { return this._value * 2; },
                set value(v) { this._value = v; }
            };
            obj.value = 10;
            obj.value
        ''')
        assert result == 20  # 10 * 2
