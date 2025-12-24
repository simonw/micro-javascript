"""JavaScript parser - produces an AST from tokens."""

from typing import List, Optional, Callable
from .lexer import Lexer
from .tokens import Token, TokenType
from .errors import JSSyntaxError
from .ast_nodes import (
    Node, Program, NumericLiteral, StringLiteral, BooleanLiteral, NullLiteral,
    RegexLiteral, Identifier, ThisExpression, ArrayExpression, ObjectExpression, Property,
    UnaryExpression, UpdateExpression, BinaryExpression, LogicalExpression,
    ConditionalExpression, AssignmentExpression, SequenceExpression,
    MemberExpression, CallExpression, NewExpression,
    ExpressionStatement, BlockStatement, EmptyStatement,
    VariableDeclaration, VariableDeclarator,
    IfStatement, WhileStatement, DoWhileStatement, ForStatement,
    ForInStatement, ForOfStatement, BreakStatement, ContinueStatement,
    ReturnStatement, ThrowStatement, TryStatement, CatchClause,
    SwitchStatement, SwitchCase, LabeledStatement,
    FunctionDeclaration, FunctionExpression,
)


# Operator precedence (higher = binds tighter)
PRECEDENCE = {
    "||": 1,
    "&&": 2,
    "|": 3,
    "^": 4,
    "&": 5,
    "==": 6, "!=": 6, "===": 6, "!==": 6,
    "<": 7, ">": 7, "<=": 7, ">=": 7, "in": 7, "instanceof": 7,
    "<<": 8, ">>": 8, ">>>": 8,
    "+": 9, "-": 9,
    "*": 10, "/": 10, "%": 10,
    "**": 11,
}


class Parser:
    """Recursive descent parser for JavaScript."""

    def __init__(self, source: str):
        self.lexer = Lexer(source)
        self.current: Token = self.lexer.next_token()
        self.previous: Optional[Token] = None

    def _error(self, message: str) -> JSSyntaxError:
        """Create a syntax error at current position."""
        return JSSyntaxError(message, self.current.line, self.current.column)

    def _advance(self) -> Token:
        """Advance to next token and return previous."""
        self.previous = self.current
        self.current = self.lexer.next_token()
        return self.previous

    def _check(self, *types: TokenType) -> bool:
        """Check if current token is one of the given types."""
        return self.current.type in types

    def _match(self, *types: TokenType) -> bool:
        """If current token matches, advance and return True."""
        if self._check(*types):
            self._advance()
            return True
        return False

    def _expect(self, token_type: TokenType, message: str) -> Token:
        """Expect a specific token type or raise error."""
        if self.current.type != token_type:
            raise self._error(message)
        return self._advance()

    def _is_at_end(self) -> bool:
        """Check if we've reached the end of input."""
        return self.current.type == TokenType.EOF

    def _peek_next(self) -> Token:
        """Peek at the next token without consuming it."""
        # Save current state
        saved_pos = self.lexer.pos
        saved_line = self.lexer.line
        saved_column = self.lexer.column
        saved_current = self.current

        # Get next token
        next_token = self.lexer.next_token()

        # Restore state
        self.lexer.pos = saved_pos
        self.lexer.line = saved_line
        self.lexer.column = saved_column

        return next_token

    def parse(self) -> Program:
        """Parse the entire program."""
        body: List[Node] = []
        while not self._is_at_end():
            stmt = self._parse_statement()
            if stmt is not None:
                body.append(stmt)
        return Program(body)

    # ---- Statements ----

    def _parse_statement(self) -> Optional[Node]:
        """Parse a statement."""
        if self._match(TokenType.SEMICOLON):
            return EmptyStatement()

        if self._check(TokenType.LBRACE):
            return self._parse_block_statement()

        if self._match(TokenType.VAR):
            return self._parse_variable_declaration()

        if self._match(TokenType.IF):
            return self._parse_if_statement()

        if self._match(TokenType.WHILE):
            return self._parse_while_statement()

        if self._match(TokenType.DO):
            return self._parse_do_while_statement()

        if self._match(TokenType.FOR):
            return self._parse_for_statement()

        if self._match(TokenType.BREAK):
            return self._parse_break_statement()

        if self._match(TokenType.CONTINUE):
            return self._parse_continue_statement()

        if self._match(TokenType.RETURN):
            return self._parse_return_statement()

        if self._match(TokenType.THROW):
            return self._parse_throw_statement()

        if self._match(TokenType.TRY):
            return self._parse_try_statement()

        if self._match(TokenType.SWITCH):
            return self._parse_switch_statement()

        if self._match(TokenType.FUNCTION):
            return self._parse_function_declaration()

        # Check for labeled statement: IDENTIFIER COLON statement
        if self._check(TokenType.IDENTIFIER):
            # Look ahead for colon to detect labeled statement
            if self._peek_next().type == TokenType.COLON:
                label_token = self._advance()  # consume identifier
                self._advance()  # consume colon
                body = self._parse_statement()
                return LabeledStatement(Identifier(label_token.value), body)

        # Expression statement
        return self._parse_expression_statement()

    def _parse_block_statement(self) -> BlockStatement:
        """Parse a block statement: { ... }"""
        self._expect(TokenType.LBRACE, "Expected '{'")
        body: List[Node] = []
        while not self._check(TokenType.RBRACE) and not self._is_at_end():
            stmt = self._parse_statement()
            if stmt is not None:
                body.append(stmt)
        self._expect(TokenType.RBRACE, "Expected '}'")
        return BlockStatement(body)

    def _parse_variable_declaration(self) -> VariableDeclaration:
        """Parse variable declaration: var a = 1, b = 2;"""
        declarations: List[VariableDeclarator] = []

        while True:
            name = self._expect(TokenType.IDENTIFIER, "Expected variable name")
            init = None
            if self._match(TokenType.ASSIGN):
                init = self._parse_assignment_expression()
            declarations.append(VariableDeclarator(Identifier(name.value), init))

            if not self._match(TokenType.COMMA):
                break

        self._consume_semicolon()
        return VariableDeclaration(declarations)

    def _parse_if_statement(self) -> IfStatement:
        """Parse if statement: if (test) consequent else alternate"""
        self._expect(TokenType.LPAREN, "Expected '(' after 'if'")
        test = self._parse_expression()
        self._expect(TokenType.RPAREN, "Expected ')' after condition")
        consequent = self._parse_statement()
        alternate = None
        if self._match(TokenType.ELSE):
            alternate = self._parse_statement()
        return IfStatement(test, consequent, alternate)

    def _parse_while_statement(self) -> WhileStatement:
        """Parse while statement: while (test) body"""
        self._expect(TokenType.LPAREN, "Expected '(' after 'while'")
        test = self._parse_expression()
        self._expect(TokenType.RPAREN, "Expected ')' after condition")
        body = self._parse_statement()
        return WhileStatement(test, body)

    def _parse_do_while_statement(self) -> DoWhileStatement:
        """Parse do-while statement: do body while (test);"""
        body = self._parse_statement()
        self._expect(TokenType.WHILE, "Expected 'while' after do block")
        self._expect(TokenType.LPAREN, "Expected '(' after 'while'")
        test = self._parse_expression()
        self._expect(TokenType.RPAREN, "Expected ')' after condition")
        self._consume_semicolon()
        return DoWhileStatement(body, test)

    def _parse_for_statement(self) -> Node:
        """Parse for/for-in/for-of statement."""
        self._expect(TokenType.LPAREN, "Expected '(' after 'for'")

        # Parse init part
        init = None
        if self._match(TokenType.SEMICOLON):
            pass  # No init
        elif self._match(TokenType.VAR):
            # Could be for or for-in
            name = self._expect(TokenType.IDENTIFIER, "Expected variable name")
            if self._match(TokenType.IN):
                # for (var x in obj)
                right = self._parse_expression()
                self._expect(TokenType.RPAREN, "Expected ')' after for-in")
                body = self._parse_statement()
                left = VariableDeclaration(
                    [VariableDeclarator(Identifier(name.value), None)]
                )
                return ForInStatement(left, right, body)
            elif self._match(TokenType.OF):
                # for (var x of iterable)
                right = self._parse_expression()
                self._expect(TokenType.RPAREN, "Expected ')' after for-of")
                body = self._parse_statement()
                left = VariableDeclaration(
                    [VariableDeclarator(Identifier(name.value), None)]
                )
                return ForOfStatement(left, right, body)
            else:
                # Regular for with var init
                var_init = None
                if self._match(TokenType.ASSIGN):
                    var_init = self._parse_assignment_expression()
                declarations = [VariableDeclarator(Identifier(name.value), var_init)]
                while self._match(TokenType.COMMA):
                    n = self._expect(TokenType.IDENTIFIER, "Expected variable name")
                    vi = None
                    if self._match(TokenType.ASSIGN):
                        vi = self._parse_assignment_expression()
                    declarations.append(VariableDeclarator(Identifier(n.value), vi))
                init = VariableDeclaration(declarations)
                self._expect(TokenType.SEMICOLON, "Expected ';' after for init")
        else:
            # Expression init (could also be for-in with identifier or member expression)
            # Parse with exclude_in=True so 'in' isn't treated as binary operator
            expr = self._parse_expression(exclude_in=True)
            if self._match(TokenType.IN):
                # for (x in obj) or for (a.x in obj)
                right = self._parse_expression()
                self._expect(TokenType.RPAREN, "Expected ')' after for-in")
                body = self._parse_statement()
                return ForInStatement(expr, right, body)
            init = expr
            self._expect(TokenType.SEMICOLON, "Expected ';' after for init")

        # Regular for loop
        test = None
        if not self._check(TokenType.SEMICOLON):
            test = self._parse_expression()
        self._expect(TokenType.SEMICOLON, "Expected ';' after for condition")

        update = None
        if not self._check(TokenType.RPAREN):
            update = self._parse_expression()
        self._expect(TokenType.RPAREN, "Expected ')' after for update")

        body = self._parse_statement()
        return ForStatement(init, test, update, body)

    def _parse_break_statement(self) -> BreakStatement:
        """Parse break statement."""
        label = None
        if self._check(TokenType.IDENTIFIER):
            label = Identifier(self._advance().value)
        self._consume_semicolon()
        return BreakStatement(label)

    def _parse_continue_statement(self) -> ContinueStatement:
        """Parse continue statement."""
        label = None
        if self._check(TokenType.IDENTIFIER):
            label = Identifier(self._advance().value)
        self._consume_semicolon()
        return ContinueStatement(label)

    def _parse_return_statement(self) -> ReturnStatement:
        """Parse return statement."""
        argument = None
        if not self._check(TokenType.SEMICOLON) and not self._check(TokenType.RBRACE):
            argument = self._parse_expression()
        self._consume_semicolon()
        return ReturnStatement(argument)

    def _parse_throw_statement(self) -> ThrowStatement:
        """Parse throw statement."""
        argument = self._parse_expression()
        self._consume_semicolon()
        return ThrowStatement(argument)

    def _parse_try_statement(self) -> TryStatement:
        """Parse try statement."""
        block = self._parse_block_statement()
        handler = None
        finalizer = None

        if self._match(TokenType.CATCH):
            self._expect(TokenType.LPAREN, "Expected '(' after 'catch'")
            param = self._expect(TokenType.IDENTIFIER, "Expected catch parameter")
            self._expect(TokenType.RPAREN, "Expected ')' after catch parameter")
            catch_body = self._parse_block_statement()
            handler = CatchClause(Identifier(param.value), catch_body)

        if self._match(TokenType.FINALLY):
            finalizer = self._parse_block_statement()

        if handler is None and finalizer is None:
            raise self._error("Missing catch or finally clause")

        return TryStatement(block, handler, finalizer)

    def _parse_switch_statement(self) -> SwitchStatement:
        """Parse switch statement."""
        self._expect(TokenType.LPAREN, "Expected '(' after 'switch'")
        discriminant = self._parse_expression()
        self._expect(TokenType.RPAREN, "Expected ')' after switch expression")
        self._expect(TokenType.LBRACE, "Expected '{' before switch body")

        cases: List[SwitchCase] = []
        while not self._check(TokenType.RBRACE) and not self._is_at_end():
            test = None
            if self._match(TokenType.CASE):
                test = self._parse_expression()
            elif self._match(TokenType.DEFAULT):
                pass
            else:
                raise self._error("Expected 'case' or 'default'")

            self._expect(TokenType.COLON, "Expected ':' after case expression")

            consequent: List[Node] = []
            while not self._check(TokenType.CASE, TokenType.DEFAULT, TokenType.RBRACE):
                stmt = self._parse_statement()
                if stmt is not None:
                    consequent.append(stmt)

            cases.append(SwitchCase(test, consequent))

        self._expect(TokenType.RBRACE, "Expected '}' after switch body")
        return SwitchStatement(discriminant, cases)

    def _parse_function_declaration(self) -> FunctionDeclaration:
        """Parse function declaration."""
        name = self._expect(TokenType.IDENTIFIER, "Expected function name")
        params = self._parse_function_params()
        body = self._parse_block_statement()
        return FunctionDeclaration(Identifier(name.value), params, body)

    def _parse_function_params(self) -> List[Identifier]:
        """Parse function parameters."""
        self._expect(TokenType.LPAREN, "Expected '(' after function name")
        params: List[Identifier] = []
        if not self._check(TokenType.RPAREN):
            while True:
                param = self._expect(TokenType.IDENTIFIER, "Expected parameter name")
                params.append(Identifier(param.value))
                if not self._match(TokenType.COMMA):
                    break
        self._expect(TokenType.RPAREN, "Expected ')' after parameters")
        return params

    def _parse_expression_statement(self) -> ExpressionStatement:
        """Parse expression statement."""
        expr = self._parse_expression()
        self._consume_semicolon()
        return ExpressionStatement(expr)

    def _consume_semicolon(self) -> None:
        """Consume a semicolon if present (ASI simulation)."""
        self._match(TokenType.SEMICOLON)

    # ---- Expressions ----

    def _parse_expression(self, exclude_in: bool = False) -> Node:
        """Parse an expression (includes comma operator)."""
        expr = self._parse_assignment_expression(exclude_in)

        if self._check(TokenType.COMMA):
            expressions = [expr]
            while self._match(TokenType.COMMA):
                expressions.append(self._parse_assignment_expression(exclude_in))
            return SequenceExpression(expressions)

        return expr

    def _parse_assignment_expression(self, exclude_in: bool = False) -> Node:
        """Parse assignment expression."""
        expr = self._parse_conditional_expression(exclude_in)

        if self._check(
            TokenType.ASSIGN, TokenType.PLUS_ASSIGN, TokenType.MINUS_ASSIGN,
            TokenType.STAR_ASSIGN, TokenType.SLASH_ASSIGN, TokenType.PERCENT_ASSIGN,
            TokenType.AND_ASSIGN, TokenType.OR_ASSIGN, TokenType.XOR_ASSIGN,
            TokenType.LSHIFT_ASSIGN, TokenType.RSHIFT_ASSIGN, TokenType.URSHIFT_ASSIGN,
        ):
            op = self._advance().value
            right = self._parse_assignment_expression(exclude_in)
            return AssignmentExpression(op, expr, right)

        return expr

    def _parse_conditional_expression(self, exclude_in: bool = False) -> Node:
        """Parse conditional (ternary) expression."""
        expr = self._parse_binary_expression(0, exclude_in)

        if self._match(TokenType.QUESTION):
            consequent = self._parse_assignment_expression(exclude_in)
            self._expect(TokenType.COLON, "Expected ':' in conditional expression")
            alternate = self._parse_assignment_expression(exclude_in)
            return ConditionalExpression(expr, consequent, alternate)

        return expr

    def _parse_binary_expression(self, min_precedence: int = 0, exclude_in: bool = False) -> Node:
        """Parse binary expression with operator precedence."""
        left = self._parse_unary_expression()

        while True:
            op = self._get_binary_operator()
            if op is None:
                break

            # Skip 'in' operator when parsing for-in left-hand side
            if exclude_in and op == "in":
                break

            precedence = PRECEDENCE.get(op, 0)
            if precedence < min_precedence:
                break

            self._advance()

            # Handle right-associative operators
            if op == "**":
                right = self._parse_binary_expression(precedence, exclude_in)
            else:
                right = self._parse_binary_expression(precedence + 1, exclude_in)

            # Use LogicalExpression for && and ||
            if op in ("&&", "||"):
                left = LogicalExpression(op, left, right)
            else:
                left = BinaryExpression(op, left, right)

        return left

    def _get_binary_operator(self) -> Optional[str]:
        """Get binary operator from current token, or None."""
        token = self.current
        if token.type == TokenType.PLUS:
            return "+"
        if token.type == TokenType.MINUS:
            return "-"
        if token.type == TokenType.STAR:
            return "*"
        if token.type == TokenType.SLASH:
            return "/"
        if token.type == TokenType.PERCENT:
            return "%"
        if token.type == TokenType.STARSTAR:
            return "**"
        if token.type == TokenType.LT:
            return "<"
        if token.type == TokenType.GT:
            return ">"
        if token.type == TokenType.LE:
            return "<="
        if token.type == TokenType.GE:
            return ">="
        if token.type == TokenType.EQ:
            return "=="
        if token.type == TokenType.NE:
            return "!="
        if token.type == TokenType.EQEQ:
            return "==="
        if token.type == TokenType.NENE:
            return "!=="
        if token.type == TokenType.AND:
            return "&&"
        if token.type == TokenType.OR:
            return "||"
        if token.type == TokenType.AMPERSAND:
            return "&"
        if token.type == TokenType.PIPE:
            return "|"
        if token.type == TokenType.CARET:
            return "^"
        if token.type == TokenType.LSHIFT:
            return "<<"
        if token.type == TokenType.RSHIFT:
            return ">>"
        if token.type == TokenType.URSHIFT:
            return ">>>"
        if token.type == TokenType.IN:
            return "in"
        if token.type == TokenType.INSTANCEOF:
            return "instanceof"
        return None

    def _parse_unary_expression(self) -> Node:
        """Parse unary expression."""
        # Prefix operators
        if self._check(
            TokenType.MINUS, TokenType.PLUS, TokenType.NOT, TokenType.TILDE,
            TokenType.TYPEOF, TokenType.VOID, TokenType.DELETE,
        ):
            op_token = self._advance()
            op = op_token.value
            argument = self._parse_unary_expression()
            return UnaryExpression(op, argument)

        # Prefix increment/decrement
        if self._check(TokenType.PLUSPLUS, TokenType.MINUSMINUS):
            op_token = self._advance()
            argument = self._parse_unary_expression()
            return UpdateExpression(op_token.value, argument, prefix=True)

        return self._parse_postfix_expression()

    def _parse_postfix_expression(self) -> Node:
        """Parse postfix expression (member access, calls, postfix ++/--)."""
        expr = self._parse_new_expression()

        while True:
            if self._match(TokenType.DOT):
                # Member access: a.b
                prop = self._expect(TokenType.IDENTIFIER, "Expected property name")
                expr = MemberExpression(expr, Identifier(prop.value), computed=False)
            elif self._match(TokenType.LBRACKET):
                # Computed member access: a[b]
                prop = self._parse_expression()
                self._expect(TokenType.RBRACKET, "Expected ']' after index")
                expr = MemberExpression(expr, prop, computed=True)
            elif self._match(TokenType.LPAREN):
                # Function call: f(args)
                args = self._parse_arguments()
                self._expect(TokenType.RPAREN, "Expected ')' after arguments")
                expr = CallExpression(expr, args)
            elif self._check(TokenType.PLUSPLUS, TokenType.MINUSMINUS):
                # Postfix increment/decrement
                op = self._advance().value
                expr = UpdateExpression(op, expr, prefix=False)
            else:
                break

        return expr

    def _parse_new_expression(self) -> Node:
        """Parse new expression."""
        if self._match(TokenType.NEW):
            callee = self._parse_new_expression()
            args: List[Node] = []
            if self._match(TokenType.LPAREN):
                args = self._parse_arguments()
                self._expect(TokenType.RPAREN, "Expected ')' after arguments")
            return NewExpression(callee, args)

        return self._parse_primary_expression()

    def _parse_arguments(self) -> List[Node]:
        """Parse function call arguments."""
        args: List[Node] = []
        if not self._check(TokenType.RPAREN):
            while True:
                args.append(self._parse_assignment_expression())
                if not self._match(TokenType.COMMA):
                    break
        return args

    def _parse_primary_expression(self) -> Node:
        """Parse primary expression (literals, identifiers, grouped)."""
        # Literals
        if self._match(TokenType.NUMBER):
            return NumericLiteral(self.previous.value)

        if self._match(TokenType.STRING):
            return StringLiteral(self.previous.value)

        if self._match(TokenType.TRUE):
            return BooleanLiteral(True)

        if self._match(TokenType.FALSE):
            return BooleanLiteral(False)

        if self._match(TokenType.NULL):
            return NullLiteral()

        if self._match(TokenType.THIS):
            return ThisExpression()

        if self._match(TokenType.IDENTIFIER):
            return Identifier(self.previous.value)

        # Parenthesized expression
        if self._match(TokenType.LPAREN):
            expr = self._parse_expression()
            self._expect(TokenType.RPAREN, "Expected ')' after expression")
            return expr

        # Array literal
        if self._match(TokenType.LBRACKET):
            return self._parse_array_literal()

        # Object literal (need to be careful with block statements)
        if self._match(TokenType.LBRACE):
            return self._parse_object_literal()

        # Function expression
        if self._match(TokenType.FUNCTION):
            return self._parse_function_expression()

        # Regex literal - when we see / in primary expression context, it's a regex
        if self._check(TokenType.SLASH):
            regex_token = self.lexer.read_regex_literal()
            self.current = self.lexer.next_token()  # Move past the regex
            pattern, flags = regex_token.value
            return RegexLiteral(pattern, flags)

        raise self._error(f"Unexpected token: {self.current.type.name}")

    def _parse_array_literal(self) -> ArrayExpression:
        """Parse array literal: [a, b, c]"""
        elements: List[Node] = []
        while not self._check(TokenType.RBRACKET):
            elements.append(self._parse_assignment_expression())
            if not self._match(TokenType.COMMA):
                break
        self._expect(TokenType.RBRACKET, "Expected ']' after array elements")
        return ArrayExpression(elements)

    def _parse_object_literal(self) -> ObjectExpression:
        """Parse object literal: {a: 1, b: 2}"""
        properties: List[Property] = []
        while not self._check(TokenType.RBRACE):
            prop = self._parse_property()
            properties.append(prop)
            if not self._match(TokenType.COMMA):
                break
        self._expect(TokenType.RBRACE, "Expected '}' after object properties")
        return ObjectExpression(properties)

    def _parse_property(self) -> Property:
        """Parse object property."""
        # Check for getter/setter
        kind = "init"
        if self._check(TokenType.IDENTIFIER):
            if self.current.value == "get":
                # Could be getter or property named "get"
                self._advance()
                if self._check(TokenType.IDENTIFIER, TokenType.STRING, TokenType.NUMBER):
                    kind = "get"
                else:
                    # It's a property named "get"
                    key = Identifier("get")
                    if self._match(TokenType.COLON):
                        value = self._parse_assignment_expression()
                    else:
                        # Shorthand: {get}
                        value = key
                    return Property(key, value, "init", computed=False, shorthand=True)
            elif self.current.value == "set":
                self._advance()
                if self._check(TokenType.IDENTIFIER, TokenType.STRING, TokenType.NUMBER):
                    kind = "set"
                else:
                    key = Identifier("set")
                    if self._match(TokenType.COLON):
                        value = self._parse_assignment_expression()
                    else:
                        value = key
                    return Property(key, value, "init", computed=False, shorthand=True)

        # Parse key
        computed = False
        if self._match(TokenType.LBRACKET):
            key = self._parse_assignment_expression()
            self._expect(TokenType.RBRACKET, "Expected ']' after computed property name")
            computed = True
        elif self._match(TokenType.STRING):
            key = StringLiteral(self.previous.value)
        elif self._match(TokenType.NUMBER):
            key = NumericLiteral(self.previous.value)
        elif self._match(TokenType.IDENTIFIER):
            key = Identifier(self.previous.value)
        else:
            raise self._error("Expected property name")

        # Parse value
        if kind in ("get", "set"):
            # Getter/setter - value is a function
            params = self._parse_function_params()
            body = self._parse_block_statement()
            value = FunctionExpression(None, params, body)
        elif self._match(TokenType.LPAREN):
            # Method shorthand: {foo() { }}
            params = []
            if not self._check(TokenType.RPAREN):
                while True:
                    param = self._expect(TokenType.IDENTIFIER, "Expected parameter name")
                    params.append(Identifier(param.value))
                    if not self._match(TokenType.COMMA):
                        break
            self._expect(TokenType.RPAREN, "Expected ')' after parameters")
            body = self._parse_block_statement()
            value = FunctionExpression(None, params, body)
        elif self._match(TokenType.COLON):
            value = self._parse_assignment_expression()
        else:
            # Shorthand property: {x} means {x: x}
            if isinstance(key, Identifier):
                value = key
            else:
                raise self._error("Expected ':' after property name")

        return Property(key, value, kind, computed=computed)

    def _parse_function_expression(self) -> FunctionExpression:
        """Parse function expression."""
        name = None
        if self._check(TokenType.IDENTIFIER):
            name = Identifier(self._advance().value)
        params = self._parse_function_params()
        body = self._parse_block_statement()
        return FunctionExpression(name, params, body)
