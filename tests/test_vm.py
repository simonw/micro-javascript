"""Tests for the JavaScript VM and context."""

import pytest
from microjs import Context, JSError, JSSyntaxError


class TestContextBasics:
    """Test basic context functionality."""

    def test_evaluate_number(self):
        """Evaluate a simple number."""
        ctx = Context()
        assert ctx.eval("42") == 42

    def test_evaluate_float(self):
        """Evaluate a float."""
        ctx = Context()
        assert ctx.eval("3.14") == 3.14

    def test_evaluate_string(self):
        """Evaluate a string literal."""
        ctx = Context()
        assert ctx.eval('"hello"') == "hello"

    def test_evaluate_boolean_true(self):
        """Evaluate boolean true."""
        ctx = Context()
        assert ctx.eval("true") is True

    def test_evaluate_boolean_false(self):
        """Evaluate boolean false."""
        ctx = Context()
        assert ctx.eval("false") is False

    def test_evaluate_null(self):
        """Evaluate null."""
        ctx = Context()
        assert ctx.eval("null") is None


class TestArithmetic:
    """Test arithmetic operations."""

    def test_addition(self):
        """Test addition."""
        ctx = Context()
        assert ctx.eval("1 + 2") == 3

    def test_subtraction(self):
        """Test subtraction."""
        ctx = Context()
        assert ctx.eval("5 - 3") == 2

    def test_multiplication(self):
        """Test multiplication."""
        ctx = Context()
        assert ctx.eval("4 * 5") == 20

    def test_division(self):
        """Test division."""
        ctx = Context()
        assert ctx.eval("20 / 4") == 5.0

    def test_modulo(self):
        """Test modulo."""
        ctx = Context()
        assert ctx.eval("10 % 3") == 1

    def test_complex_expression(self):
        """Test complex expression with precedence."""
        ctx = Context()
        assert ctx.eval("2 + 3 * 4") == 14

    def test_parentheses(self):
        """Test parentheses."""
        ctx = Context()
        assert ctx.eval("(2 + 3) * 4") == 20

    def test_unary_minus(self):
        """Test unary minus."""
        ctx = Context()
        assert ctx.eval("-5") == -5


class TestVariables:
    """Test variable operations."""

    def test_var_declaration(self):
        """Test variable declaration."""
        ctx = Context()
        result = ctx.eval("var x = 10; x")
        assert result == 10

    def test_var_assignment(self):
        """Test variable assignment."""
        ctx = Context()
        result = ctx.eval("var x = 5; x = 10; x")
        assert result == 10

    def test_compound_assignment(self):
        """Test compound assignment."""
        ctx = Context()
        result = ctx.eval("var x = 10; x += 5; x")
        assert result == 15

    def test_multiple_vars(self):
        """Test multiple variable declarations."""
        ctx = Context()
        result = ctx.eval("var a = 1, b = 2; a + b")
        assert result == 3


class TestComparisons:
    """Test comparison operations."""

    def test_less_than(self):
        """Test less than."""
        ctx = Context()
        assert ctx.eval("1 < 2") is True
        assert ctx.eval("2 < 1") is False

    def test_greater_than(self):
        """Test greater than."""
        ctx = Context()
        assert ctx.eval("2 > 1") is True
        assert ctx.eval("1 > 2") is False

    def test_equal(self):
        """Test equality."""
        ctx = Context()
        assert ctx.eval("1 == 1") is True
        assert ctx.eval("1 == 2") is False

    def test_strict_equal(self):
        """Test strict equality."""
        ctx = Context()
        assert ctx.eval("1 === 1") is True

    def test_not_equal(self):
        """Test not equal."""
        ctx = Context()
        assert ctx.eval("1 != 2") is True
        assert ctx.eval("1 != 1") is False


class TestLogical:
    """Test logical operations."""

    def test_logical_and(self):
        """Test logical AND."""
        ctx = Context()
        assert ctx.eval("true && true") is True
        assert ctx.eval("true && false") is False

    def test_logical_or(self):
        """Test logical OR."""
        ctx = Context()
        assert ctx.eval("false || true") is True
        assert ctx.eval("false || false") is False

    def test_logical_not(self):
        """Test logical NOT."""
        ctx = Context()
        assert ctx.eval("!true") is False
        assert ctx.eval("!false") is True


class TestConditionals:
    """Test conditional operations."""

    def test_ternary(self):
        """Test ternary operator."""
        ctx = Context()
        assert ctx.eval("true ? 1 : 2") == 1
        assert ctx.eval("false ? 1 : 2") == 2

    def test_if_statement(self):
        """Test if statement."""
        ctx = Context()
        result = ctx.eval("var x = 0; if (true) x = 1; x")
        assert result == 1

    def test_if_else_statement(self):
        """Test if-else statement."""
        ctx = Context()
        result = ctx.eval("var x = 0; if (false) x = 1; else x = 2; x")
        assert result == 2


class TestLoops:
    """Test loop operations."""

    def test_while_loop(self):
        """Test while loop."""
        ctx = Context()
        result = ctx.eval("var x = 0; while (x < 5) x = x + 1; x")
        assert result == 5

    def test_for_loop(self):
        """Test for loop."""
        ctx = Context()
        result = ctx.eval("var sum = 0; for (var i = 0; i < 5; i++) sum = sum + i; sum")
        assert result == 10

    def test_do_while_loop(self):
        """Test do-while loop."""
        ctx = Context()
        result = ctx.eval("var x = 0; do { x = x + 1; } while (x < 3); x")
        assert result == 3

    def test_break(self):
        """Test break statement."""
        ctx = Context()
        result = ctx.eval("var x = 0; while (true) { x = x + 1; if (x >= 3) break; } x")
        assert result == 3


class TestFunctions:
    """Test function operations."""

    def test_function_declaration(self):
        """Test function declaration."""
        ctx = Context()
        result = ctx.eval("function add(a, b) { return a + b; } add(2, 3)")
        assert result == 5

    def test_function_expression(self):
        """Test function expression."""
        ctx = Context()
        result = ctx.eval("var mul = function(a, b) { return a * b; }; mul(3, 4)")
        assert result == 12


class TestArrays:
    """Test array operations."""

    def test_array_literal(self):
        """Test array literal."""
        ctx = Context()
        result = ctx.eval("[1, 2, 3]")
        assert result == [1, 2, 3]

    def test_array_access(self):
        """Test array access."""
        ctx = Context()
        result = ctx.eval("var arr = [10, 20, 30]; arr[1]")
        assert result == 20

    def test_array_length(self):
        """Test array length."""
        ctx = Context()
        result = ctx.eval("var arr = [1, 2, 3, 4, 5]; arr.length")
        assert result == 5


class TestObjects:
    """Test object operations."""

    def test_object_literal(self):
        """Test object literal."""
        ctx = Context()
        result = ctx.eval("({a: 1, b: 2})")
        assert result == {"a": 1, "b": 2}

    def test_object_property_access(self):
        """Test object property access."""
        ctx = Context()
        result = ctx.eval("var obj = {x: 10}; obj.x")
        assert result == 10

    def test_object_property_set(self):
        """Test object property set."""
        ctx = Context()
        result = ctx.eval("var obj = {}; obj.x = 5; obj.x")
        assert result == 5


class TestStrings:
    """Test string operations."""

    def test_string_concatenation(self):
        """Test string concatenation."""
        ctx = Context()
        result = ctx.eval('"hello" + " " + "world"')
        assert result == "hello world"

    def test_string_length(self):
        """Test string length."""
        ctx = Context()
        result = ctx.eval('"hello".length')
        assert result == 5


class TestGlobalAccess:
    """Test global variable access."""

    def test_set_global(self):
        """Test setting a global variable."""
        ctx = Context()
        ctx.set("x", 42)
        result = ctx.eval("x")
        assert result == 42

    def test_get_global(self):
        """Test getting a global variable."""
        ctx = Context()
        ctx.eval("var myVar = 100")
        result = ctx.get("myVar")
        assert result == 100


"""Test void operator."""
import pytest
from microjs import Context


class TestVoidOperator:
    def test_void_returns_undefined(self):
        ctx = Context()
        result = ctx.eval("void 0")
        assert result is None or str(result) == "undefined"

    def test_void_expression(self):
        ctx = Context()
        result = ctx.eval("void (1 + 2)")
        assert result is None or str(result) == "undefined"

    def test_void_function_call(self):
        ctx = Context()
        result = ctx.eval("var x = 0; void (x = 5); x")
        assert result == 5  # Side effect happens, but void returns undefined


"""Test for...of loops."""
import pytest
from microjs import Context


class TestForOf:
    def test_for_of_array(self):
        """Basic for...of with array."""
        ctx = Context()
        result = ctx.eval(
            """
            var sum = 0;
            var arr = [1, 2, 3, 4, 5];
            for (var x of arr) {
                sum += x;
            }
            sum
        """
        )
        assert result == 15

    def test_for_of_string(self):
        """for...of with string iterates characters."""
        ctx = Context()
        result = ctx.eval(
            """
            var chars = [];
            for (var c of "abc") {
                chars.push(c);
            }
            chars.join(",")
        """
        )
        assert result == "a,b,c"


"""Test getter/setter property syntax."""
import pytest
from microjs import Context


class TestGetterSetter:
    def test_getter(self):
        """Basic getter."""
        ctx = Context()
        result = ctx.eval(
            """
            var obj = {
                _x: 10,
                get x() { return this._x; }
            };
            obj.x
        """
        )
        assert result == 10

    def test_setter(self):
        """Basic setter."""
        ctx = Context()
        result = ctx.eval(
            """
            var obj = {
                _x: 0,
                set x(v) { this._x = v; }
            };
            obj.x = 42;
            obj._x
        """
        )
        assert result == 42

    def test_getter_setter_combined(self):
        """Getter and setter together."""
        ctx = Context()
        result = ctx.eval(
            """
            var obj = {
                _value: 5,
                get value() { return this._value * 2; },
                set value(v) { this._value = v; }
            };
            obj.value = 10;
            obj.value
        """
        )
        assert result == 20  # 10 * 2


class TestTryFinallyBreak:
    """Test that finally blocks execute before break/continue/return."""

    def test_break_in_try_finally(self):
        """Break inside try should run finally block first."""
        ctx = Context()
        result = ctx.eval(
            """
            var s = '';
            for(;;) {
                try {
                    s += 't';
                    break;
                } finally {
                    s += 'f';
                }
            }
            s
        """
        )
        assert result == "tf"


class TestLabeledStatements:
    """Test labeled statements."""

    def test_labeled_break_after_while(self):
        """Labeled break after while without braces."""
        ctx = Context()
        # Should not hang - breaks immediately
        result = ctx.eval("var x = 0; while (1) label: break; x")
        assert result == 0

    def test_labeled_break_in_block(self):
        """Labeled break in block."""
        ctx = Context()
        result = ctx.eval("var x = 0; label: { x = 1; break label; x = 2; } x")
        assert result == 1


class TestBuiltinConstructors:
    """Test built-in constructors like new Object(), new Array()."""

    def test_new_object(self):
        """new Object() creates empty object."""
        ctx = Context()
        result = ctx.eval("var o = new Object(); o.x = 1; o.x")
        assert result == 1

    def test_new_array(self):
        """new Array() creates array."""
        ctx = Context()
        result = ctx.eval("new Array(3).length")
        assert result == 3

    def test_new_array_with_elements(self):
        """new Array(1, 2, 3) creates array with elements."""
        ctx = Context()
        result = ctx.eval("var a = new Array(1, 2, 3); a[1]")
        assert result == 2


class TestASI:
    """Test automatic semicolon insertion."""

    def test_break_asi_newline(self):
        """break followed by identifier on new line should not consume identifier as label."""
        ctx = Context()
        # break should get ASI, i++ should be a separate statement
        result = ctx.eval(
            """
            var i = 0;
            while (i < 3) {
                if (i > 0)
                    break
                i++
            }
            i
        """
        )
        assert result == 1

    def test_continue_asi_newline(self):
        """continue followed by identifier on new line should not consume identifier as label."""
        ctx = Context()
        result = ctx.eval(
            """
            var sum = 0;
            for (var i = 0; i < 5; i++) {
                if (i == 2)
                    continue
                sum += i
            }
            sum
        """
        )
        # 0 + 1 + 3 + 4 = 8 (skipping 2)
        assert result == 8


class TestMemberUpdate:
    """Test update expressions on member expressions."""

    def test_object_property_postfix_increment(self):
        """a.x++ returns old value and increments."""
        ctx = Context()
        result = ctx.eval(
            """
            var a = {x: 5};
            var r = a.x++;
            [r, a.x]
        """
        )
        assert result[0] == 5
        assert result[1] == 6

    def test_object_property_prefix_increment(self):
        """++a.x returns new value."""
        ctx = Context()
        result = ctx.eval(
            """
            var a = {x: 5};
            var r = ++a.x;
            [r, a.x]
        """
        )
        assert result[0] == 6
        assert result[1] == 6

    def test_array_element_postfix_increment(self):
        """arr[0]++ works."""
        ctx = Context()
        result = ctx.eval(
            """
            var arr = [10];
            var r = arr[0]++;
            [r, arr[0]]
        """
        )
        assert result[0] == 10
        assert result[1] == 11

    def test_object_property_decrement(self):
        """a.x-- works."""
        ctx = Context()
        result = ctx.eval(
            """
            var a = {x: 5};
            var r = a.x--;
            [r, a.x]
        """
        )
        assert result[0] == 5
        assert result[1] == 4


class TestBackwardsCompatibleAlias:
    """Test that the JSContext alias works for backwards compatibility."""

    def test_jscontext_alias_exists(self):
        """JSContext should be importable as an alias for Context."""
        from microjs import JSContext

        ctx = JSContext()
        result = ctx.eval("1 + 2")
        assert result == 3
