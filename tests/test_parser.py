"""Tests for the JavaScript parser."""

import pytest
from mquickjs_python.parser import Parser
from mquickjs_python.ast_nodes import (
    Program, NumericLiteral, StringLiteral, BooleanLiteral, NullLiteral,
    Identifier, ThisExpression, ArrayExpression, ObjectExpression, Property,
    UnaryExpression, UpdateExpression, BinaryExpression, LogicalExpression,
    ConditionalExpression, AssignmentExpression, SequenceExpression,
    MemberExpression, CallExpression, NewExpression,
    ExpressionStatement, BlockStatement, EmptyStatement,
    VariableDeclaration, VariableDeclarator,
    IfStatement, WhileStatement, DoWhileStatement, ForStatement,
    ForInStatement, BreakStatement, ContinueStatement, ReturnStatement,
    ThrowStatement, TryStatement, CatchClause, SwitchStatement, SwitchCase,
    LabeledStatement, FunctionDeclaration, FunctionExpression,
)
from mquickjs_python.errors import JSSyntaxError


class TestParserLiterals:
    """Test parsing of literals."""

    def test_empty_program(self):
        """Empty program."""
        ast = Parser("").parse()
        assert isinstance(ast, Program)
        assert ast.body == []

    def test_numeric_literal_integer(self):
        """Integer literal."""
        ast = Parser("42;").parse()
        assert len(ast.body) == 1
        stmt = ast.body[0]
        assert isinstance(stmt, ExpressionStatement)
        assert isinstance(stmt.expression, NumericLiteral)
        assert stmt.expression.value == 42

    def test_numeric_literal_float(self):
        """Float literal."""
        ast = Parser("3.14;").parse()
        stmt = ast.body[0]
        assert isinstance(stmt.expression, NumericLiteral)
        assert stmt.expression.value == 3.14

    def test_string_literal(self):
        """String literal."""
        ast = Parser('"hello";').parse()
        stmt = ast.body[0]
        assert isinstance(stmt.expression, StringLiteral)
        assert stmt.expression.value == "hello"

    def test_boolean_true(self):
        """Boolean literal: true."""
        ast = Parser("true;").parse()
        stmt = ast.body[0]
        assert isinstance(stmt.expression, BooleanLiteral)
        assert stmt.expression.value is True

    def test_boolean_false(self):
        """Boolean literal: false."""
        ast = Parser("false;").parse()
        stmt = ast.body[0]
        assert isinstance(stmt.expression, BooleanLiteral)
        assert stmt.expression.value is False

    def test_null_literal(self):
        """Null literal."""
        ast = Parser("null;").parse()
        stmt = ast.body[0]
        assert isinstance(stmt.expression, NullLiteral)

    def test_identifier(self):
        """Identifier."""
        ast = Parser("foo;").parse()
        stmt = ast.body[0]
        assert isinstance(stmt.expression, Identifier)
        assert stmt.expression.name == "foo"

    def test_this_expression(self):
        """This expression."""
        ast = Parser("this;").parse()
        stmt = ast.body[0]
        assert isinstance(stmt.expression, ThisExpression)


class TestParserExpressions:
    """Test parsing of expressions."""

    def test_parenthesized(self):
        """Parenthesized expression."""
        ast = Parser("(42);").parse()
        stmt = ast.body[0]
        assert isinstance(stmt.expression, NumericLiteral)
        assert stmt.expression.value == 42

    def test_unary_minus(self):
        """Unary minus."""
        ast = Parser("-42;").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, UnaryExpression)
        assert expr.operator == "-"
        assert isinstance(expr.argument, NumericLiteral)

    def test_unary_not(self):
        """Logical not."""
        ast = Parser("!true;").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, UnaryExpression)
        assert expr.operator == "!"

    def test_unary_typeof(self):
        """Typeof operator."""
        ast = Parser("typeof x;").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, UnaryExpression)
        assert expr.operator == "typeof"

    def test_prefix_increment(self):
        """Prefix increment."""
        ast = Parser("++x;").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, UpdateExpression)
        assert expr.operator == "++"
        assert expr.prefix is True

    def test_postfix_increment(self):
        """Postfix increment."""
        ast = Parser("x++;").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, UpdateExpression)
        assert expr.operator == "++"
        assert expr.prefix is False

    def test_binary_addition(self):
        """Binary addition."""
        ast = Parser("1 + 2;").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, BinaryExpression)
        assert expr.operator == "+"
        assert isinstance(expr.left, NumericLiteral)
        assert isinstance(expr.right, NumericLiteral)

    def test_binary_precedence(self):
        """Operator precedence: * before +."""
        ast = Parser("1 + 2 * 3;").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, BinaryExpression)
        assert expr.operator == "+"
        assert isinstance(expr.left, NumericLiteral)
        assert isinstance(expr.right, BinaryExpression)
        assert expr.right.operator == "*"

    def test_comparison(self):
        """Comparison operators."""
        ast = Parser("a < b;").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, BinaryExpression)
        assert expr.operator == "<"

    def test_equality(self):
        """Equality operators."""
        ast = Parser("a === b;").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, BinaryExpression)
        assert expr.operator == "==="

    def test_logical_and(self):
        """Logical AND."""
        ast = Parser("a && b;").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, LogicalExpression)
        assert expr.operator == "&&"

    def test_logical_or(self):
        """Logical OR."""
        ast = Parser("a || b;").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, LogicalExpression)
        assert expr.operator == "||"

    def test_conditional(self):
        """Conditional (ternary) expression."""
        ast = Parser("a ? b : c;").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, ConditionalExpression)
        assert isinstance(expr.test, Identifier)
        assert isinstance(expr.consequent, Identifier)
        assert isinstance(expr.alternate, Identifier)

    def test_assignment(self):
        """Assignment expression."""
        ast = Parser("a = 1;").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, AssignmentExpression)
        assert expr.operator == "="
        assert isinstance(expr.left, Identifier)
        assert isinstance(expr.right, NumericLiteral)

    def test_compound_assignment(self):
        """Compound assignment."""
        ast = Parser("a += 1;").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, AssignmentExpression)
        assert expr.operator == "+="

    def test_comma_expression(self):
        """Comma (sequence) expression."""
        ast = Parser("a, b, c;").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, SequenceExpression)
        assert len(expr.expressions) == 3


class TestParserMemberExpressions:
    """Test parsing of member and call expressions."""

    def test_member_dot(self):
        """Member expression with dot notation."""
        ast = Parser("a.b;").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, MemberExpression)
        assert expr.computed is False
        assert isinstance(expr.object, Identifier)
        assert isinstance(expr.property, Identifier)

    def test_member_bracket(self):
        """Member expression with bracket notation."""
        ast = Parser("a[0];").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, MemberExpression)
        assert expr.computed is True

    def test_member_chain(self):
        """Chained member expressions."""
        ast = Parser("a.b.c;").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, MemberExpression)
        assert isinstance(expr.object, MemberExpression)

    def test_call_no_args(self):
        """Call expression with no arguments."""
        ast = Parser("f();").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, CallExpression)
        assert isinstance(expr.callee, Identifier)
        assert expr.arguments == []

    def test_call_with_args(self):
        """Call expression with arguments."""
        ast = Parser("f(1, 2);").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, CallExpression)
        assert len(expr.arguments) == 2

    def test_method_call(self):
        """Method call."""
        ast = Parser("a.b(1);").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, CallExpression)
        assert isinstance(expr.callee, MemberExpression)

    def test_new_expression(self):
        """New expression."""
        ast = Parser("new Foo();").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, NewExpression)
        assert isinstance(expr.callee, Identifier)

    def test_new_with_args(self):
        """New expression with arguments."""
        ast = Parser("new Foo(1, 2);").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, NewExpression)
        assert len(expr.arguments) == 2


class TestParserArraysAndObjects:
    """Test parsing of array and object literals."""

    def test_empty_array(self):
        """Empty array literal."""
        ast = Parser("[];").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, ArrayExpression)
        assert expr.elements == []

    def test_array_with_elements(self):
        """Array literal with elements."""
        ast = Parser("[1, 2, 3];").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, ArrayExpression)
        assert len(expr.elements) == 3

    def test_empty_object(self):
        """Empty object literal."""
        ast = Parser("{};").parse()
        stmt = ast.body[0]
        # Note: {} could be a block or object - in expression context it's object
        assert isinstance(stmt, ExpressionStatement) or isinstance(stmt, BlockStatement)

    def test_object_with_properties(self):
        """Object literal with properties."""
        ast = Parser("({a: 1, b: 2});").parse()
        stmt = ast.body[0]
        expr = stmt.expression
        assert isinstance(expr, ObjectExpression)
        assert len(expr.properties) == 2


class TestParserStatements:
    """Test parsing of statements."""

    def test_empty_statement(self):
        """Empty statement."""
        ast = Parser(";").parse()
        assert len(ast.body) == 1
        assert isinstance(ast.body[0], EmptyStatement)

    def test_block_statement(self):
        """Block statement."""
        ast = Parser("{ 1; 2; }").parse()
        assert len(ast.body) == 1
        block = ast.body[0]
        assert isinstance(block, BlockStatement)
        assert len(block.body) == 2

    def test_var_declaration(self):
        """Variable declaration."""
        ast = Parser("var x;").parse()
        stmt = ast.body[0]
        assert isinstance(stmt, VariableDeclaration)
        assert len(stmt.declarations) == 1
        assert stmt.declarations[0].id.name == "x"
        assert stmt.declarations[0].init is None

    def test_var_with_init(self):
        """Variable declaration with initializer."""
        ast = Parser("var x = 1;").parse()
        stmt = ast.body[0]
        assert isinstance(stmt, VariableDeclaration)
        assert stmt.declarations[0].init is not None

    def test_var_multiple(self):
        """Multiple variable declarations."""
        ast = Parser("var x = 1, y = 2;").parse()
        stmt = ast.body[0]
        assert isinstance(stmt, VariableDeclaration)
        assert len(stmt.declarations) == 2

    def test_if_statement(self):
        """If statement."""
        ast = Parser("if (x) y;").parse()
        stmt = ast.body[0]
        assert isinstance(stmt, IfStatement)
        assert isinstance(stmt.test, Identifier)
        assert isinstance(stmt.consequent, ExpressionStatement)
        assert stmt.alternate is None

    def test_if_else_statement(self):
        """If-else statement."""
        ast = Parser("if (x) y; else z;").parse()
        stmt = ast.body[0]
        assert isinstance(stmt, IfStatement)
        assert stmt.alternate is not None

    def test_while_statement(self):
        """While statement."""
        ast = Parser("while (x) y;").parse()
        stmt = ast.body[0]
        assert isinstance(stmt, WhileStatement)

    def test_do_while_statement(self):
        """Do-while statement."""
        ast = Parser("do x; while (y);").parse()
        stmt = ast.body[0]
        assert isinstance(stmt, DoWhileStatement)

    def test_for_statement(self):
        """For statement."""
        ast = Parser("for (var i = 0; i < 10; i++) x;").parse()
        stmt = ast.body[0]
        assert isinstance(stmt, ForStatement)
        assert isinstance(stmt.init, VariableDeclaration)

    def test_for_in_statement(self):
        """For-in statement."""
        ast = Parser("for (var x in obj) y;").parse()
        stmt = ast.body[0]
        assert isinstance(stmt, ForInStatement)

    def test_break_statement(self):
        """Break statement."""
        ast = Parser("while(1) break;").parse()
        while_stmt = ast.body[0]
        assert isinstance(while_stmt.body, BreakStatement)

    def test_continue_statement(self):
        """Continue statement."""
        ast = Parser("while(1) continue;").parse()
        while_stmt = ast.body[0]
        assert isinstance(while_stmt.body, ContinueStatement)

    def test_return_statement(self):
        """Return statement."""
        ast = Parser("function f() { return 1; }").parse()
        func = ast.body[0]
        ret = func.body.body[0]
        assert isinstance(ret, ReturnStatement)
        assert ret.argument is not None

    def test_throw_statement(self):
        """Throw statement."""
        ast = Parser("throw x;").parse()
        stmt = ast.body[0]
        assert isinstance(stmt, ThrowStatement)

    def test_try_catch(self):
        """Try-catch statement."""
        ast = Parser("try { x; } catch (e) { y; }").parse()
        stmt = ast.body[0]
        assert isinstance(stmt, TryStatement)
        assert stmt.handler is not None
        assert stmt.finalizer is None

    def test_try_finally(self):
        """Try-finally statement."""
        ast = Parser("try { x; } finally { y; }").parse()
        stmt = ast.body[0]
        assert isinstance(stmt, TryStatement)
        assert stmt.handler is None
        assert stmt.finalizer is not None

    def test_try_catch_finally(self):
        """Try-catch-finally statement."""
        ast = Parser("try { x; } catch (e) { y; } finally { z; }").parse()
        stmt = ast.body[0]
        assert isinstance(stmt, TryStatement)
        assert stmt.handler is not None
        assert stmt.finalizer is not None

    def test_switch_statement(self):
        """Switch statement."""
        ast = Parser("switch (x) { case 1: y; break; default: z; }").parse()
        stmt = ast.body[0]
        assert isinstance(stmt, SwitchStatement)
        assert len(stmt.cases) == 2


class TestParserFunctions:
    """Test parsing of function declarations and expressions."""

    def test_function_declaration(self):
        """Function declaration."""
        ast = Parser("function foo(a, b) { return a + b; }").parse()
        stmt = ast.body[0]
        assert isinstance(stmt, FunctionDeclaration)
        assert stmt.id.name == "foo"
        assert len(stmt.params) == 2

    def test_function_expression(self):
        """Function expression."""
        ast = Parser("var f = function() { };").parse()
        stmt = ast.body[0]
        init = stmt.declarations[0].init
        assert isinstance(init, FunctionExpression)

    def test_named_function_expression(self):
        """Named function expression."""
        ast = Parser("var f = function foo() { };").parse()
        stmt = ast.body[0]
        init = stmt.declarations[0].init
        assert isinstance(init, FunctionExpression)
        assert init.id.name == "foo"
