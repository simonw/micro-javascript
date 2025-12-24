"""
Regex pattern parser.

Parses JavaScript regex patterns into an AST for compilation.
Grammar (simplified):
    Pattern     ::= Disjunction
    Disjunction ::= Alternative ('|' Alternative)*
    Alternative ::= Term*
    Term        ::= Assertion | Atom Quantifier?
    Assertion   ::= '^' | '$' | '\\b' | '\\B' | Lookahead | Lookbehind
    Atom        ::= PatternChar | '.' | CharClass | '(' Disjunction ')' | Escape
    Quantifier  ::= ('*' | '+' | '?' | '{' n (',' n?)? '}') '?'?
    CharClass   ::= '[' '^'? ClassRanges ']'
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union


class RegExpError(Exception):
    """Exception raised for regex parsing errors."""
    pass


# AST Node Types

@dataclass
class Char:
    """Literal character."""
    char: str


@dataclass
class Dot:
    """Match any character (except newline by default)."""
    pass


@dataclass
class CharClass:
    """Character class like [a-z]."""
    ranges: List[Tuple[str, str]]  # List of (start, end) ranges
    negated: bool = False


@dataclass
class Shorthand:
    """Shorthand character class like \\d, \\w, \\s."""
    type: str  # 'd', 'D', 'w', 'W', 's', 'S'


@dataclass
class Anchor:
    """Anchor like ^, $, \\b, \\B."""
    type: str  # 'start', 'end', 'boundary', 'not_boundary'


@dataclass
class Backref:
    """Backreference like \\1."""
    group: int


@dataclass
class Group:
    """Capturing or non-capturing group."""
    body: 'Node'
    capturing: bool = True
    group_index: int = 0


@dataclass
class Lookahead:
    """Lookahead assertion (?=...) or (?!...)."""
    body: 'Node'
    positive: bool = True


@dataclass
class Lookbehind:
    """Lookbehind assertion (?<=...) or (?<!...)."""
    body: 'Node'
    positive: bool = True


@dataclass
class Quantifier:
    """Quantifier like *, +, ?, {n,m}."""
    body: 'Node'
    min: int
    max: int  # -1 means unlimited
    greedy: bool = True


@dataclass
class Alternative:
    """Sequence of terms (AND)."""
    terms: List['Node']


@dataclass
class Disjunction:
    """Alternation (OR)."""
    alternatives: List['Node']


# Union type for all nodes
Node = Union[Char, Dot, CharClass, Shorthand, Anchor, Backref,
             Group, Lookahead, Lookbehind, Quantifier, Alternative, Disjunction]


class RegexParser:
    """Parser for JavaScript regex patterns."""

    def __init__(self, pattern: str, flags: str = ""):
        self.pattern = pattern
        self.flags = flags
        self.pos = 0
        self.group_count = 0
        self.unicode = 'u' in flags

    def parse(self) -> Tuple[Node, int]:
        """
        Parse the pattern and return (AST, capture_count).
        """
        self.pos = 0
        self.group_count = 0

        if not self.pattern:
            return Alternative([]), 1  # Empty pattern matches empty string

        ast = self._parse_disjunction()

        if self.pos < len(self.pattern):
            raise RegExpError(f"Unexpected character '{self.pattern[self.pos]}' at position {self.pos}")

        return ast, self.group_count + 1  # +1 for group 0 (full match)

    def _peek(self) -> Optional[str]:
        """Look at current character without consuming."""
        if self.pos < len(self.pattern):
            return self.pattern[self.pos]
        return None

    def _advance(self) -> Optional[str]:
        """Consume and return current character."""
        if self.pos < len(self.pattern):
            ch = self.pattern[self.pos]
            self.pos += 1
            return ch
        return None

    def _match(self, ch: str) -> bool:
        """Match and consume specific character."""
        if self._peek() == ch:
            self.pos += 1
            return True
        return False

    def _parse_disjunction(self) -> Node:
        """Parse alternation (a|b|c)."""
        alternatives = [self._parse_alternative()]

        while self._match('|'):
            alternatives.append(self._parse_alternative())

        if len(alternatives) == 1:
            return alternatives[0]
        return Disjunction(alternatives)

    def _parse_alternative(self) -> Node:
        """Parse sequence of terms."""
        terms = []

        while self._peek() is not None and self._peek() not in '|)':
            old_pos = self.pos
            term = self._parse_term()
            if term is not None:
                terms.append(term)
            elif self.pos == old_pos:
                # No progress - check for quantifier at start (error)
                ch = self._peek()
                if ch in '*+?':
                    raise RegExpError(f"Nothing to repeat at position {self.pos}")
                # Unknown character - skip to prevent infinite loop
                break

        if len(terms) == 0:
            return Alternative([])
        if len(terms) == 1:
            return terms[0]
        return Alternative(terms)

    def _parse_term(self) -> Optional[Node]:
        """Parse a single term (assertion or atom with optional quantifier)."""
        # Try assertions first
        assertion = self._try_parse_assertion()
        if assertion is not None:
            return assertion

        # Parse atom
        atom = self._parse_atom()
        if atom is None:
            return None

        # Check for quantifier
        quantifier = self._try_parse_quantifier(atom)
        if quantifier is not None:
            return quantifier

        return atom

    def _try_parse_assertion(self) -> Optional[Node]:
        """Try to parse an assertion (^, $, \\b, \\B)."""
        ch = self._peek()

        if ch == '^':
            self._advance()
            return Anchor('start')
        if ch == '$':
            self._advance()
            return Anchor('end')

        # \b and \B are handled in _parse_escape
        return None

    def _parse_atom(self) -> Optional[Node]:
        """Parse an atom (char, dot, class, group, escape)."""
        ch = self._peek()

        if ch is None:
            return None

        if ch == '.':
            self._advance()
            return Dot()

        if ch == '[':
            return self._parse_char_class()

        if ch == '(':
            return self._parse_group()

        if ch == '\\':
            return self._parse_escape()

        # Regular character (not special)
        special_chars = '.*+?^${}[]()|\\'
        if ch not in special_chars:
            self._advance()
            return Char(ch)

        # Special characters that can appear literally in some contexts
        if ch in '-/':
            # Hyphen and slash outside character class are literal
            self._advance()
            return Char(ch)

        if ch in '{}':
            # Check if it's a valid quantifier
            if not self._is_quantifier_start():
                self._advance()
                return Char(ch)
            return None  # Let quantifier parsing handle it

        return None

    def _is_quantifier_start(self) -> bool:
        """Check if we're at the start of a {n,m} quantifier."""
        if self.pos >= len(self.pattern) or self.pattern[self.pos] != '{':
            return False
        # Look ahead to see if this looks like {n} or {n,} or {n,m}
        i = self.pos + 1
        # Check for empty {} which is invalid
        if i < len(self.pattern) and self.pattern[i] == '}':
            return True  # Will be caught as error in _parse_brace_quantifier
        while i < len(self.pattern) and self.pattern[i].isdigit():
            i += 1
        if i == self.pos + 1:  # No digits after {
            return False
        if i >= len(self.pattern):
            return False
        if self.pattern[i] == '}':
            return True
        if self.pattern[i] == ',':
            i += 1
            while i < len(self.pattern) and self.pattern[i].isdigit():
                i += 1
            if i < len(self.pattern) and self.pattern[i] == '}':
                return True
        return False

    def _parse_char_class(self) -> CharClass:
        """Parse character class [...]."""
        self._advance()  # consume '['

        negated = self._match('^')
        ranges = []

        while self._peek() is not None and self._peek() != ']':
            start = self._parse_class_char()
            if start is None:
                break

            if self._peek() == '-' and self.pos + 1 < len(self.pattern) and self.pattern[self.pos + 1] != ']':
                self._advance()  # consume '-'
                end = self._parse_class_char()
                if end is None:
                    # Treat '-' as literal at end
                    ranges.append((start, start))
                    ranges.append(('-', '-'))
                else:
                    ranges.append((start, end))
            else:
                ranges.append((start, start))

        if not self._match(']'):
            raise RegExpError("Unterminated character class")

        return CharClass(ranges, negated)

    def _parse_class_char(self) -> Optional[str]:
        """Parse a character inside a character class."""
        ch = self._peek()
        if ch is None or ch == ']':
            return None

        if ch == '\\':
            self._advance()
            escaped = self._peek()
            if escaped is None:
                raise RegExpError("Trailing backslash in character class")

            self._advance()

            # Handle escape sequences
            escape_map = {
                'n': '\n', 't': '\t', 'r': '\r', 'f': '\f', 'v': '\v',
                '0': '\0', 'b': '\b',
            }
            if escaped in escape_map:
                return escape_map[escaped]
            if escaped in 'dDwWsS':
                # These need special handling - return as-is for now
                # The compiler will expand them
                return '\\' + escaped
            # Literal escape
            return escaped

        self._advance()
        return ch

    def _parse_group(self) -> Node:
        """Parse group (...), (?:...), (?=...), (?!...), (?<=...), (?<!...)."""
        self._advance()  # consume '('

        capturing = True
        group_index = 0
        is_lookahead = False
        is_lookbehind = False
        positive = True

        if self._peek() == '?':
            self._advance()
            next_ch = self._peek()

            if next_ch == ':':
                # Non-capturing group (?:...)
                self._advance()
                capturing = False
            elif next_ch == '=':
                # Positive lookahead (?=...)
                self._advance()
                is_lookahead = True
                capturing = False  # Lookahead itself is not a capturing group
                positive = True
            elif next_ch == '!':
                # Negative lookahead (?!...)
                self._advance()
                is_lookahead = True
                capturing = False  # Lookahead itself is not a capturing group
                positive = False
            elif next_ch == '<':
                self._advance()
                next_ch2 = self._peek()
                if next_ch2 == '=':
                    # Positive lookbehind (?<=...)
                    self._advance()
                    is_lookbehind = True
                    capturing = False  # Lookbehind itself is not a capturing group
                    positive = True
                elif next_ch2 == '!':
                    # Negative lookbehind (?<!...)
                    self._advance()
                    is_lookbehind = True
                    capturing = False  # Lookbehind itself is not a capturing group
                    positive = False
                else:
                    raise RegExpError("Invalid group syntax")
            else:
                raise RegExpError(f"Invalid group syntax: (?{next_ch}")

        if capturing:
            self.group_count += 1
            group_index = self.group_count

        body = self._parse_disjunction()

        if not self._match(')'):
            raise RegExpError("Unterminated group")

        if is_lookahead:
            return Lookahead(body, positive)
        if is_lookbehind:
            return Lookbehind(body, positive)

        return Group(body, capturing, group_index)

    def _parse_escape(self) -> Node:
        """Parse escape sequence."""
        self._advance()  # consume '\\'
        ch = self._peek()

        if ch is None:
            raise RegExpError("Trailing backslash")

        self._advance()

        # Shorthand character classes
        if ch in 'dDwWsS':
            return Shorthand(ch)

        # Word boundary
        if ch == 'b':
            return Anchor('boundary')
        if ch == 'B':
            return Anchor('not_boundary')

        # Backreference
        if ch.isdigit() and ch != '0':
            # Parse multi-digit backreference
            num = ch
            while self._peek() is not None and self._peek().isdigit():
                num += self._advance()
            group_num = int(num)
            if group_num > self.group_count:
                # Might be octal or invalid - treat as literal for now
                raise RegExpError(f"Invalid backreference \\{group_num}")
            return Backref(group_num)

        # Unicode escape
        if ch == 'u':
            return self._parse_unicode_escape()

        # Hex escape
        if ch == 'x':
            return self._parse_hex_escape()

        # Control character
        if ch == 'c':
            ctrl = self._peek()
            if ctrl is not None and (ctrl.isalpha()):
                self._advance()
                return Char(chr(ord(ctrl.upper()) - 64))
            # Non-letter after \c: treat as literal \c (backslash + c)
            return Alternative([Char('\\'), Char('c')])

        # Simple escapes
        escape_map = {
            'n': '\n', 't': '\t', 'r': '\r', 'f': '\f', 'v': '\v',
            '0': '\0',
        }
        if ch in escape_map:
            return Char(escape_map[ch])

        # Identity escape (literal)
        return Char(ch)

    def _parse_unicode_escape(self) -> Char:
        """Parse \\uXXXX or \\u{XXXX} escape."""
        if self._peek() == '{':
            # \u{XXXX} form
            self._advance()
            hex_digits = ''
            while self._peek() is not None and self._peek() != '}':
                hex_digits += self._advance()
            if not self._match('}'):
                raise RegExpError("Unterminated unicode escape")
            if not hex_digits:
                raise RegExpError("Empty unicode escape")
            try:
                return Char(chr(int(hex_digits, 16)))
            except ValueError:
                raise RegExpError(f"Invalid unicode escape: {hex_digits}")
        else:
            # \uXXXX form
            hex_digits = ''
            for _ in range(4):
                ch = self._peek()
                if ch is not None and ch in '0123456789abcdefABCDEF':
                    hex_digits += self._advance()
                else:
                    break
            if len(hex_digits) != 4:
                raise RegExpError("Invalid unicode escape")
            return Char(chr(int(hex_digits, 16)))

    def _parse_hex_escape(self) -> Char:
        """Parse \\xXX escape."""
        hex_digits = ''
        for _ in range(2):
            ch = self._peek()
            if ch is not None and ch in '0123456789abcdefABCDEF':
                hex_digits += self._advance()
            else:
                break
        if len(hex_digits) != 2:
            raise RegExpError("Invalid hex escape")
        return Char(chr(int(hex_digits, 16)))

    def _try_parse_quantifier(self, atom: Node) -> Optional[Quantifier]:
        """Try to parse a quantifier after an atom."""
        ch = self._peek()

        min_count = 0
        max_count = -1  # -1 = unlimited

        if ch == '*':
            self._advance()
            min_count, max_count = 0, -1
        elif ch == '+':
            self._advance()
            min_count, max_count = 1, -1
        elif ch == '?':
            self._advance()
            min_count, max_count = 0, 1
        elif ch == '{':
            result = self._parse_brace_quantifier()
            if result is None:
                return None
            min_count, max_count = result
        else:
            return None

        # Check for lazy modifier
        greedy = not self._match('?')

        return Quantifier(atom, min_count, max_count, greedy)

    def _parse_brace_quantifier(self) -> Optional[Tuple[int, int]]:
        """Parse {n}, {n,}, or {n,m} quantifier."""
        if not self._is_quantifier_start():
            return None

        self._advance()  # consume '{'

        # Parse min
        min_str = ''
        while self._peek() is not None and self._peek().isdigit():
            min_str += self._advance()

        if not min_str:
            raise RegExpError("Invalid quantifier")

        min_count = int(min_str)
        max_count = min_count

        if self._match(','):
            # Check for max
            max_str = ''
            while self._peek() is not None and self._peek().isdigit():
                max_str += self._advance()

            if max_str:
                max_count = int(max_str)
            else:
                max_count = -1  # Unlimited

        if not self._match('}'):
            raise RegExpError("Unterminated quantifier")

        if max_count != -1 and max_count < min_count:
            raise RegExpError("Quantifier max less than min")

        return min_count, max_count


def parse(pattern: str, flags: str = "") -> Tuple[Node, int]:
    """
    Parse a regex pattern.

    Args:
        pattern: The regex pattern string
        flags: Optional flags string

    Returns:
        Tuple of (AST root node, capture count)
    """
    parser = RegexParser(pattern, flags)
    return parser.parse()
