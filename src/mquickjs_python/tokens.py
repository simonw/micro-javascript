"""Token types for JavaScript lexer."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Optional


class TokenType(Enum):
    """JavaScript token types."""

    # End of file
    EOF = auto()

    # Literals
    NUMBER = auto()
    STRING = auto()
    REGEX = auto()

    # Identifiers and keywords
    IDENTIFIER = auto()

    # Keywords
    VAR = auto()
    FUNCTION = auto()
    RETURN = auto()
    IF = auto()
    ELSE = auto()
    WHILE = auto()
    DO = auto()
    FOR = auto()
    IN = auto()
    OF = auto()
    BREAK = auto()
    CONTINUE = auto()
    SWITCH = auto()
    CASE = auto()
    DEFAULT = auto()
    TRY = auto()
    CATCH = auto()
    FINALLY = auto()
    THROW = auto()
    NEW = auto()
    DELETE = auto()
    TYPEOF = auto()
    INSTANCEOF = auto()
    THIS = auto()
    TRUE = auto()
    FALSE = auto()
    NULL = auto()
    VOID = auto()

    # Punctuation
    LPAREN = auto()  # (
    RPAREN = auto()  # )
    LBRACE = auto()  # {
    RBRACE = auto()  # }
    LBRACKET = auto()  # [
    RBRACKET = auto()  # ]
    SEMICOLON = auto()  # ;
    COMMA = auto()  # ,
    DOT = auto()  # .
    COLON = auto()  # :
    QUESTION = auto()  # ?

    # Operators
    PLUS = auto()  # +
    MINUS = auto()  # -
    STAR = auto()  # *
    SLASH = auto()  # /
    PERCENT = auto()  # %
    STARSTAR = auto()  # **
    PLUSPLUS = auto()  # ++
    MINUSMINUS = auto()  # --

    # Comparison
    LT = auto()  # <
    GT = auto()  # >
    LE = auto()  # <=
    GE = auto()  # >=
    EQ = auto()  # ==
    NE = auto()  # !=
    EQEQ = auto()  # ===
    NENE = auto()  # !==

    # Logical
    AND = auto()  # &&
    OR = auto()  # ||
    NOT = auto()  # !

    # Bitwise
    AMPERSAND = auto()  # &
    PIPE = auto()  # |
    CARET = auto()  # ^
    TILDE = auto()  # ~
    LSHIFT = auto()  # <<
    RSHIFT = auto()  # >>
    URSHIFT = auto()  # >>>

    # Assignment
    ASSIGN = auto()  # =
    PLUS_ASSIGN = auto()  # +=
    MINUS_ASSIGN = auto()  # -=
    STAR_ASSIGN = auto()  # *=
    SLASH_ASSIGN = auto()  # /=
    PERCENT_ASSIGN = auto()  # %=
    AND_ASSIGN = auto()  # &=
    OR_ASSIGN = auto()  # |=
    XOR_ASSIGN = auto()  # ^=
    LSHIFT_ASSIGN = auto()  # <<=
    RSHIFT_ASSIGN = auto()  # >>=
    URSHIFT_ASSIGN = auto()  # >>>=

    # Arrow function
    ARROW = auto()  # =>


# Map keywords to token types
KEYWORDS = {
    "var": TokenType.VAR,
    "function": TokenType.FUNCTION,
    "return": TokenType.RETURN,
    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "while": TokenType.WHILE,
    "do": TokenType.DO,
    "for": TokenType.FOR,
    "in": TokenType.IN,
    "of": TokenType.OF,
    "break": TokenType.BREAK,
    "continue": TokenType.CONTINUE,
    "switch": TokenType.SWITCH,
    "case": TokenType.CASE,
    "default": TokenType.DEFAULT,
    "try": TokenType.TRY,
    "catch": TokenType.CATCH,
    "finally": TokenType.FINALLY,
    "throw": TokenType.THROW,
    "new": TokenType.NEW,
    "delete": TokenType.DELETE,
    "typeof": TokenType.TYPEOF,
    "instanceof": TokenType.INSTANCEOF,
    "this": TokenType.THIS,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "null": TokenType.NULL,
    "void": TokenType.VOID,
}


@dataclass
class Token:
    """A token from the JavaScript source."""

    type: TokenType
    value: Any
    line: int
    column: int

    def __repr__(self) -> str:
        if self.value is not None:
            return f"Token({self.type.name}, {self.value!r}, {self.line}:{self.column})"
        return f"Token({self.type.name}, {self.line}:{self.column})"
