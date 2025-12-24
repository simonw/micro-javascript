"""JavaScript lexer (tokenizer)."""

from typing import Iterator, Optional
from .tokens import Token, TokenType, KEYWORDS
from .errors import JSSyntaxError


class Lexer:
    """Tokenizes JavaScript source code."""

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.length = len(source)

    def _current(self) -> str:
        """Get current character or empty string if at end."""
        if self.pos >= self.length:
            return ""
        return self.source[self.pos]

    def _peek(self, offset: int = 1) -> str:
        """Peek ahead at character."""
        pos = self.pos + offset
        if pos >= self.length:
            return ""
        return self.source[pos]

    def _advance(self) -> str:
        """Advance and return current character."""
        if self.pos >= self.length:
            return ""
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def _skip_whitespace(self) -> None:
        """Skip whitespace and comments."""
        while self.pos < self.length:
            ch = self._current()

            # Whitespace
            if ch in " \t\r\n":
                self._advance()
                continue

            # Single-line comment
            if ch == "/" and self._peek() == "/":
                self._advance()  # /
                self._advance()  # /
                while self._current() and self._current() != "\n":
                    self._advance()
                continue

            # Multi-line comment
            if ch == "/" and self._peek() == "*":
                self._advance()  # /
                self._advance()  # *
                while self.pos < self.length:
                    if self._current() == "*" and self._peek() == "/":
                        self._advance()  # *
                        self._advance()  # /
                        break
                    self._advance()
                continue

            break

    def _read_string(self, quote: str) -> str:
        """Read a string literal."""
        result = []
        self._advance()  # Skip opening quote

        while self._current() and self._current() != quote:
            ch = self._advance()

            if ch == "\\":
                # Escape sequence
                escape = self._advance()
                if escape == "n":
                    result.append("\n")
                elif escape == "r":
                    result.append("\r")
                elif escape == "t":
                    result.append("\t")
                elif escape == "\\":
                    result.append("\\")
                elif escape == "'":
                    result.append("'")
                elif escape == '"':
                    result.append('"')
                elif escape == "0":
                    result.append("\0")
                elif escape == "x":
                    # Hex escape \xNN
                    hex_chars = self._advance() + self._advance()
                    try:
                        result.append(chr(int(hex_chars, 16)))
                    except ValueError:
                        raise JSSyntaxError(
                            f"Invalid hex escape: \\x{hex_chars}",
                            self.line,
                            self.column,
                        )
                elif escape == "u":
                    # Unicode escape \uNNNN or \u{N...}
                    if self._current() == "{":
                        self._advance()  # {
                        hex_chars = ""
                        while self._current() and self._current() != "}":
                            hex_chars += self._advance()
                        self._advance()  # }
                    else:
                        hex_chars = ""
                        for _ in range(4):
                            hex_chars += self._advance()
                    try:
                        result.append(chr(int(hex_chars, 16)))
                    except ValueError:
                        raise JSSyntaxError(
                            f"Invalid unicode escape: \\u{hex_chars}",
                            self.line,
                            self.column,
                        )
                else:
                    # Unknown escape - just use the character
                    result.append(escape)
            elif ch == "\n":
                raise JSSyntaxError("Unterminated string literal", self.line, self.column)
            else:
                result.append(ch)

        if not self._current():
            raise JSSyntaxError("Unterminated string literal", self.line, self.column)

        self._advance()  # Skip closing quote
        return "".join(result)

    def _read_number(self) -> float | int:
        """Read a number literal."""
        start = self.pos
        line = self.line
        col = self.column

        # Check for hex, octal, or binary
        if self._current() == "0":
            next_ch = self._peek()
            if next_ch and next_ch in "xX":
                # Hexadecimal
                self._advance()  # 0
                self._advance()  # x
                hex_str = ""
                while self._current() and self._current() in "0123456789abcdefABCDEF":
                    hex_str += self._advance()
                if not hex_str:
                    raise JSSyntaxError("Invalid hex literal", line, col)
                return int(hex_str, 16)
            elif next_ch and next_ch in "oO":
                # Octal
                self._advance()  # 0
                self._advance()  # o
                oct_str = ""
                while self._current() and self._current() in "01234567":
                    oct_str += self._advance()
                if not oct_str:
                    raise JSSyntaxError("Invalid octal literal", line, col)
                return int(oct_str, 8)
            elif next_ch and next_ch in "bB":
                # Binary
                self._advance()  # 0
                self._advance()  # b
                bin_str = ""
                while self._current() and self._current() in "01":
                    bin_str += self._advance()
                if not bin_str:
                    raise JSSyntaxError("Invalid binary literal", line, col)
                return int(bin_str, 2)
            # Could be 0, 0.xxx, or 0e... - fall through to decimal handling

        # Decimal number (integer part)
        while self._current() and self._current().isdigit():
            self._advance()

        # Decimal point
        is_float = False
        if self._current() == "." and self._peek().isdigit():
            is_float = True
            self._advance()  # .
            while self._current() and self._current().isdigit():
                self._advance()

        # Exponent
        if self._current() and self._current() in "eE":
            is_float = True
            self._advance()
            if self._current() in "+-":
                self._advance()
            if not self._current() or not self._current().isdigit():
                raise JSSyntaxError("Invalid number literal", line, col)
            while self._current() and self._current().isdigit():
                self._advance()

        num_str = self.source[start : self.pos]
        if is_float:
            return float(num_str)
        return int(num_str)

    def _read_identifier(self) -> str:
        """Read an identifier."""
        start = self.pos
        while self._current() and (
            self._current().isalnum() or self._current() in "_$"
        ):
            self._advance()
        return self.source[start : self.pos]

    def next_token(self) -> Token:
        """Get the next token."""
        self._skip_whitespace()

        line = self.line
        column = self.column

        if self.pos >= self.length:
            return Token(TokenType.EOF, None, line, column)

        ch = self._current()

        # String literals
        if ch in "'\"":
            value = self._read_string(ch)
            return Token(TokenType.STRING, value, line, column)

        # Number literals
        if ch.isdigit() or (ch == "." and self._peek().isdigit()):
            value = self._read_number()
            return Token(TokenType.NUMBER, value, line, column)

        # Identifiers and keywords
        if ch.isalpha() or ch in "_$":
            value = self._read_identifier()
            token_type = KEYWORDS.get(value, TokenType.IDENTIFIER)
            return Token(token_type, value, line, column)

        # Operators and punctuation
        self._advance()

        # Two or three character operators
        if ch == "=" and self._current() == "=":
            self._advance()
            if self._current() == "=":
                self._advance()
                return Token(TokenType.EQEQ, "===", line, column)
            return Token(TokenType.EQ, "==", line, column)

        if ch == "=" and self._current() == ">":
            self._advance()
            return Token(TokenType.ARROW, "=>", line, column)

        if ch == "!" and self._current() == "=":
            self._advance()
            if self._current() == "=":
                self._advance()
                return Token(TokenType.NENE, "!==", line, column)
            return Token(TokenType.NE, "!=", line, column)

        if ch == "<":
            if self._current() == "=":
                self._advance()
                return Token(TokenType.LE, "<=", line, column)
            if self._current() == "<":
                self._advance()
                if self._current() == "=":
                    self._advance()
                    return Token(TokenType.LSHIFT_ASSIGN, "<<=", line, column)
                return Token(TokenType.LSHIFT, "<<", line, column)
            return Token(TokenType.LT, "<", line, column)

        if ch == ">":
            if self._current() == "=":
                self._advance()
                return Token(TokenType.GE, ">=", line, column)
            if self._current() == ">":
                self._advance()
                if self._current() == ">":
                    self._advance()
                    if self._current() == "=":
                        self._advance()
                        return Token(TokenType.URSHIFT_ASSIGN, ">>>=", line, column)
                    return Token(TokenType.URSHIFT, ">>>", line, column)
                if self._current() == "=":
                    self._advance()
                    return Token(TokenType.RSHIFT_ASSIGN, ">>=", line, column)
                return Token(TokenType.RSHIFT, ">>", line, column)
            return Token(TokenType.GT, ">", line, column)

        if ch == "&":
            if self._current() == "&":
                self._advance()
                return Token(TokenType.AND, "&&", line, column)
            if self._current() == "=":
                self._advance()
                return Token(TokenType.AND_ASSIGN, "&=", line, column)
            return Token(TokenType.AMPERSAND, "&", line, column)

        if ch == "|":
            if self._current() == "|":
                self._advance()
                return Token(TokenType.OR, "||", line, column)
            if self._current() == "=":
                self._advance()
                return Token(TokenType.OR_ASSIGN, "|=", line, column)
            return Token(TokenType.PIPE, "|", line, column)

        if ch == "+":
            if self._current() == "+":
                self._advance()
                return Token(TokenType.PLUSPLUS, "++", line, column)
            if self._current() == "=":
                self._advance()
                return Token(TokenType.PLUS_ASSIGN, "+=", line, column)
            return Token(TokenType.PLUS, "+", line, column)

        if ch == "-":
            if self._current() == "-":
                self._advance()
                return Token(TokenType.MINUSMINUS, "--", line, column)
            if self._current() == "=":
                self._advance()
                return Token(TokenType.MINUS_ASSIGN, "-=", line, column)
            return Token(TokenType.MINUS, "-", line, column)

        if ch == "*":
            if self._current() == "*":
                self._advance()
                return Token(TokenType.STARSTAR, "**", line, column)
            if self._current() == "=":
                self._advance()
                return Token(TokenType.STAR_ASSIGN, "*=", line, column)
            return Token(TokenType.STAR, "*", line, column)

        if ch == "/":
            if self._current() == "=":
                self._advance()
                return Token(TokenType.SLASH_ASSIGN, "/=", line, column)
            return Token(TokenType.SLASH, "/", line, column)

        if ch == "%":
            if self._current() == "=":
                self._advance()
                return Token(TokenType.PERCENT_ASSIGN, "%=", line, column)
            return Token(TokenType.PERCENT, "%", line, column)

        if ch == "^":
            if self._current() == "=":
                self._advance()
                return Token(TokenType.XOR_ASSIGN, "^=", line, column)
            return Token(TokenType.CARET, "^", line, column)

        # Single character tokens
        single_char_tokens = {
            "(": TokenType.LPAREN,
            ")": TokenType.RPAREN,
            "{": TokenType.LBRACE,
            "}": TokenType.RBRACE,
            "[": TokenType.LBRACKET,
            "]": TokenType.RBRACKET,
            ";": TokenType.SEMICOLON,
            ",": TokenType.COMMA,
            ".": TokenType.DOT,
            ":": TokenType.COLON,
            "?": TokenType.QUESTION,
            "~": TokenType.TILDE,
            "!": TokenType.NOT,
            "=": TokenType.ASSIGN,
        }

        if ch in single_char_tokens:
            return Token(single_char_tokens[ch], ch, line, column)

        raise JSSyntaxError(f"Unexpected character: {ch!r}", line, column)

    def read_regex_literal(self) -> Token:
        """Read a regex literal after the opening slash has been consumed.

        This is called by the parser when it knows a regex is expected.
        The opening / has already been consumed.
        """
        line = self.line
        column = self.column - 1  # Account for the / we already consumed

        # Go back one position to re-read from /
        self.pos -= 1
        self.column -= 1

        if self._current() != "/":
            raise JSSyntaxError("Expected regex literal", line, column)

        self._advance()  # Skip opening /

        # Read pattern
        pattern = []
        in_char_class = False

        while self.pos < self.length:
            ch = self._current()

            if ch == "\\" and self.pos + 1 < self.length:
                # Escape sequence - include both characters
                pattern.append(self._advance())
                pattern.append(self._advance())
            elif ch == "[":
                in_char_class = True
                pattern.append(self._advance())
            elif ch == "]":
                in_char_class = False
                pattern.append(self._advance())
            elif ch == "/" and not in_char_class:
                # End of pattern
                self._advance()
                break
            elif ch == "\n":
                raise JSSyntaxError("Unterminated regex literal", line, column)
            else:
                pattern.append(self._advance())

        # Read flags
        flags = []
        while self._current() and self._current() in "gimsuy":
            flags.append(self._advance())

        return Token(
            TokenType.REGEX,
            ("".join(pattern), "".join(flags)),
            line,
            column
        )

    def tokenize(self) -> Iterator[Token]:
        """Tokenize the entire source."""
        while True:
            token = self.next_token()
            yield token
            if token.type == TokenType.EOF:
                break
