"""Tests for the JavaScript lexer."""

import pytest
from mquickjs_python.lexer import Lexer
from mquickjs_python.tokens import Token, TokenType
from mquickjs_python.errors import JSSyntaxError


class TestLexerBasics:
    """Basic lexer functionality tests."""

    def test_empty_input(self):
        """Empty input should produce EOF token."""
        lexer = Lexer("")
        token = lexer.next_token()
        assert token.type == TokenType.EOF

    def test_whitespace_only(self):
        """Whitespace-only input should produce EOF token."""
        lexer = Lexer("   \t\n\r  ")
        token = lexer.next_token()
        assert token.type == TokenType.EOF

    def test_single_line_comment(self):
        """Single-line comments should be skipped."""
        lexer = Lexer("// this is a comment")
        token = lexer.next_token()
        assert token.type == TokenType.EOF

    def test_multi_line_comment(self):
        """Multi-line comments should be skipped."""
        lexer = Lexer("/* this is\na multi-line\ncomment */")
        token = lexer.next_token()
        assert token.type == TokenType.EOF

    def test_comment_with_code(self):
        """Comments should not consume code."""
        lexer = Lexer("// comment\n42")
        token = lexer.next_token()
        assert token.type == TokenType.NUMBER
        assert token.value == 42


class TestLexerNumbers:
    """Number literal tests."""

    def test_integer(self):
        """Integer literals."""
        lexer = Lexer("42")
        token = lexer.next_token()
        assert token.type == TokenType.NUMBER
        assert token.value == 42
        assert isinstance(token.value, int)

    def test_zero(self):
        """Zero literal."""
        lexer = Lexer("0")
        token = lexer.next_token()
        assert token.type == TokenType.NUMBER
        assert token.value == 0

    def test_float(self):
        """Floating-point literals."""
        lexer = Lexer("3.14")
        token = lexer.next_token()
        assert token.type == TokenType.NUMBER
        assert token.value == 3.14
        assert isinstance(token.value, float)

    def test_float_no_leading_digit(self):
        """Floating-point literal starting with dot."""
        lexer = Lexer(".5")
        token = lexer.next_token()
        assert token.type == TokenType.NUMBER
        assert token.value == 0.5

    def test_exponent(self):
        """Scientific notation."""
        lexer = Lexer("1e10")
        token = lexer.next_token()
        assert token.type == TokenType.NUMBER
        assert token.value == 1e10

    def test_exponent_negative(self):
        """Scientific notation with negative exponent."""
        lexer = Lexer("1e-5")
        token = lexer.next_token()
        assert token.type == TokenType.NUMBER
        assert token.value == 1e-5

    def test_hex(self):
        """Hexadecimal literals."""
        lexer = Lexer("0xFF")
        token = lexer.next_token()
        assert token.type == TokenType.NUMBER
        assert token.value == 255

    def test_octal(self):
        """Octal literals."""
        lexer = Lexer("0o77")
        token = lexer.next_token()
        assert token.type == TokenType.NUMBER
        assert token.value == 63

    def test_binary(self):
        """Binary literals."""
        lexer = Lexer("0b1010")
        token = lexer.next_token()
        assert token.type == TokenType.NUMBER
        assert token.value == 10


class TestLexerStrings:
    """String literal tests."""

    def test_double_quoted(self):
        """Double-quoted strings."""
        lexer = Lexer('"hello"')
        token = lexer.next_token()
        assert token.type == TokenType.STRING
        assert token.value == "hello"

    def test_single_quoted(self):
        """Single-quoted strings."""
        lexer = Lexer("'hello'")
        token = lexer.next_token()
        assert token.type == TokenType.STRING
        assert token.value == "hello"

    def test_empty_string(self):
        """Empty string."""
        lexer = Lexer('""')
        token = lexer.next_token()
        assert token.type == TokenType.STRING
        assert token.value == ""

    def test_escape_newline(self):
        """Escape sequence: newline."""
        lexer = Lexer(r'"hello\nworld"')
        token = lexer.next_token()
        assert token.type == TokenType.STRING
        assert token.value == "hello\nworld"

    def test_escape_tab(self):
        """Escape sequence: tab."""
        lexer = Lexer(r'"hello\tworld"')
        token = lexer.next_token()
        assert token.type == TokenType.STRING
        assert token.value == "hello\tworld"

    def test_escape_backslash(self):
        """Escape sequence: backslash."""
        lexer = Lexer(r'"hello\\world"')
        token = lexer.next_token()
        assert token.type == TokenType.STRING
        assert token.value == "hello\\world"

    def test_escape_quote(self):
        """Escape sequence: quote."""
        lexer = Lexer(r'"hello\"world"')
        token = lexer.next_token()
        assert token.type == TokenType.STRING
        assert token.value == 'hello"world'

    def test_unicode_escape(self):
        """Unicode escape sequence."""
        lexer = Lexer(r'"\u0041"')
        token = lexer.next_token()
        assert token.type == TokenType.STRING
        assert token.value == "A"

    def test_unicode_escape_braces(self):
        """Unicode escape with braces."""
        lexer = Lexer(r'"\u{20AC}"')
        token = lexer.next_token()
        assert token.type == TokenType.STRING
        assert token.value == "€"

    def test_hex_escape(self):
        """Hex escape sequence."""
        lexer = Lexer(r'"\x41"')
        token = lexer.next_token()
        assert token.type == TokenType.STRING
        assert token.value == "A"

    def test_unterminated_string(self):
        """Unterminated string should raise error."""
        lexer = Lexer('"hello')
        with pytest.raises(JSSyntaxError):
            lexer.next_token()


class TestLexerIdentifiersAndKeywords:
    """Identifier and keyword tests."""

    def test_identifier_simple(self):
        """Simple identifier."""
        lexer = Lexer("foo")
        token = lexer.next_token()
        assert token.type == TokenType.IDENTIFIER
        assert token.value == "foo"

    def test_identifier_with_digits(self):
        """Identifier with digits."""
        lexer = Lexer("foo123")
        token = lexer.next_token()
        assert token.type == TokenType.IDENTIFIER
        assert token.value == "foo123"

    def test_identifier_underscore(self):
        """Identifier starting with underscore."""
        lexer = Lexer("_private")
        token = lexer.next_token()
        assert token.type == TokenType.IDENTIFIER
        assert token.value == "_private"

    def test_identifier_dollar(self):
        """Identifier starting with dollar sign."""
        lexer = Lexer("$jquery")
        token = lexer.next_token()
        assert token.type == TokenType.IDENTIFIER
        assert token.value == "$jquery"

    def test_keyword_var(self):
        """Keyword: var."""
        lexer = Lexer("var")
        token = lexer.next_token()
        assert token.type == TokenType.VAR

    def test_keyword_function(self):
        """Keyword: function."""
        lexer = Lexer("function")
        token = lexer.next_token()
        assert token.type == TokenType.FUNCTION

    def test_keyword_if(self):
        """Keyword: if."""
        lexer = Lexer("if")
        token = lexer.next_token()
        assert token.type == TokenType.IF

    def test_keyword_else(self):
        """Keyword: else."""
        lexer = Lexer("else")
        token = lexer.next_token()
        assert token.type == TokenType.ELSE

    def test_keyword_while(self):
        """Keyword: while."""
        lexer = Lexer("while")
        token = lexer.next_token()
        assert token.type == TokenType.WHILE

    def test_keyword_for(self):
        """Keyword: for."""
        lexer = Lexer("for")
        token = lexer.next_token()
        assert token.type == TokenType.FOR

    def test_keyword_return(self):
        """Keyword: return."""
        lexer = Lexer("return")
        token = lexer.next_token()
        assert token.type == TokenType.RETURN

    def test_keyword_true(self):
        """Keyword: true."""
        lexer = Lexer("true")
        token = lexer.next_token()
        assert token.type == TokenType.TRUE

    def test_keyword_false(self):
        """Keyword: false."""
        lexer = Lexer("false")
        token = lexer.next_token()
        assert token.type == TokenType.FALSE

    def test_keyword_null(self):
        """Keyword: null."""
        lexer = Lexer("null")
        token = lexer.next_token()
        assert token.type == TokenType.NULL

    def test_keyword_this(self):
        """Keyword: this."""
        lexer = Lexer("this")
        token = lexer.next_token()
        assert token.type == TokenType.THIS

    def test_keyword_new(self):
        """Keyword: new."""
        lexer = Lexer("new")
        token = lexer.next_token()
        assert token.type == TokenType.NEW

    def test_keyword_typeof(self):
        """Keyword: typeof."""
        lexer = Lexer("typeof")
        token = lexer.next_token()
        assert token.type == TokenType.TYPEOF


class TestLexerOperators:
    """Operator tests."""

    def test_arithmetic_operators(self):
        """Arithmetic operators."""
        ops = [
            ("+", TokenType.PLUS),
            ("-", TokenType.MINUS),
            ("*", TokenType.STAR),
            ("/", TokenType.SLASH),
            ("%", TokenType.PERCENT),
            ("**", TokenType.STARSTAR),
        ]
        for op, expected_type in ops:
            lexer = Lexer(op)
            token = lexer.next_token()
            assert token.type == expected_type, f"Failed for {op}"

    def test_comparison_operators(self):
        """Comparison operators."""
        ops = [
            ("<", TokenType.LT),
            (">", TokenType.GT),
            ("<=", TokenType.LE),
            (">=", TokenType.GE),
            ("==", TokenType.EQ),
            ("!=", TokenType.NE),
            ("===", TokenType.EQEQ),
            ("!==", TokenType.NENE),
        ]
        for op, expected_type in ops:
            lexer = Lexer(op)
            token = lexer.next_token()
            assert token.type == expected_type, f"Failed for {op}"

    def test_logical_operators(self):
        """Logical operators."""
        ops = [
            ("&&", TokenType.AND),
            ("||", TokenType.OR),
            ("!", TokenType.NOT),
        ]
        for op, expected_type in ops:
            lexer = Lexer(op)
            token = lexer.next_token()
            assert token.type == expected_type, f"Failed for {op}"

    def test_bitwise_operators(self):
        """Bitwise operators."""
        ops = [
            ("&", TokenType.AMPERSAND),
            ("|", TokenType.PIPE),
            ("^", TokenType.CARET),
            ("~", TokenType.TILDE),
            ("<<", TokenType.LSHIFT),
            (">>", TokenType.RSHIFT),
            (">>>", TokenType.URSHIFT),
        ]
        for op, expected_type in ops:
            lexer = Lexer(op)
            token = lexer.next_token()
            assert token.type == expected_type, f"Failed for {op}"

    def test_assignment_operators(self):
        """Assignment operators."""
        ops = [
            ("=", TokenType.ASSIGN),
            ("+=", TokenType.PLUS_ASSIGN),
            ("-=", TokenType.MINUS_ASSIGN),
            ("*=", TokenType.STAR_ASSIGN),
            ("/=", TokenType.SLASH_ASSIGN),
            ("%=", TokenType.PERCENT_ASSIGN),
            ("&=", TokenType.AND_ASSIGN),
            ("|=", TokenType.OR_ASSIGN),
            ("^=", TokenType.XOR_ASSIGN),
            ("<<=", TokenType.LSHIFT_ASSIGN),
            (">>=", TokenType.RSHIFT_ASSIGN),
            (">>>=", TokenType.URSHIFT_ASSIGN),
        ]
        for op, expected_type in ops:
            lexer = Lexer(op)
            token = lexer.next_token()
            assert token.type == expected_type, f"Failed for {op}"

    def test_increment_decrement(self):
        """Increment and decrement operators."""
        ops = [
            ("++", TokenType.PLUSPLUS),
            ("--", TokenType.MINUSMINUS),
        ]
        for op, expected_type in ops:
            lexer = Lexer(op)
            token = lexer.next_token()
            assert token.type == expected_type, f"Failed for {op}"


class TestLexerPunctuation:
    """Punctuation tests."""

    def test_punctuation(self):
        """Punctuation marks."""
        puncts = [
            ("(", TokenType.LPAREN),
            (")", TokenType.RPAREN),
            ("{", TokenType.LBRACE),
            ("}", TokenType.RBRACE),
            ("[", TokenType.LBRACKET),
            ("]", TokenType.RBRACKET),
            (";", TokenType.SEMICOLON),
            (",", TokenType.COMMA),
            (".", TokenType.DOT),
            (":", TokenType.COLON),
            ("?", TokenType.QUESTION),
        ]
        for punct, expected_type in puncts:
            lexer = Lexer(punct)
            token = lexer.next_token()
            assert token.type == expected_type, f"Failed for {punct}"


class TestLexerMultipleTokens:
    """Tests for tokenizing multiple tokens."""

    def test_simple_expression(self):
        """Simple arithmetic expression."""
        lexer = Lexer("1 + 2")
        tokens = list(lexer.tokenize())
        assert len(tokens) == 4  # 1, +, 2, EOF
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == 1
        assert tokens[1].type == TokenType.PLUS
        assert tokens[2].type == TokenType.NUMBER
        assert tokens[2].value == 2
        assert tokens[3].type == TokenType.EOF

    def test_variable_declaration(self):
        """Variable declaration."""
        lexer = Lexer("var x = 42;")
        tokens = list(lexer.tokenize())
        assert len(tokens) == 6  # var, x, =, 42, ;, EOF
        assert tokens[0].type == TokenType.VAR
        assert tokens[1].type == TokenType.IDENTIFIER
        assert tokens[1].value == "x"
        assert tokens[2].type == TokenType.ASSIGN
        assert tokens[3].type == TokenType.NUMBER
        assert tokens[3].value == 42
        assert tokens[4].type == TokenType.SEMICOLON
        assert tokens[5].type == TokenType.EOF

    def test_function_declaration(self):
        """Function declaration."""
        lexer = Lexer("function foo(a, b) { return a + b; }")
        tokens = list(lexer.tokenize())
        types = [t.type for t in tokens]
        assert TokenType.FUNCTION in types
        assert TokenType.IDENTIFIER in types
        assert TokenType.LPAREN in types
        assert TokenType.RPAREN in types
        assert TokenType.LBRACE in types
        assert TokenType.RBRACE in types
        assert TokenType.RETURN in types

    def test_line_numbers(self):
        """Line number tracking."""
        lexer = Lexer("a\nb\nc")
        tokens = list(lexer.tokenize())
        assert tokens[0].line == 1
        assert tokens[1].line == 2
        assert tokens[2].line == 3

    def test_column_numbers(self):
        """Column number tracking."""
        lexer = Lexer("ab cd ef")
        tokens = list(lexer.tokenize())
        assert tokens[0].column == 1
        assert tokens[1].column == 4
        assert tokens[2].column == 7
