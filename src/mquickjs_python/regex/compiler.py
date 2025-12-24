"""
Regex bytecode compiler.

Compiles AST to bytecode for the regex VM.
Includes ReDoS protection via zero-advance detection.
"""

from typing import List, Tuple, Optional
from .opcodes import RegexOpCode as Op
from .parser import (
    Node, Char, Dot, CharClass, Shorthand, Anchor, Backref,
    Group, Lookahead, Lookbehind, Quantifier, Alternative, Disjunction,
    RegExpError
)


class RegexCompiler:
    """Compiles regex AST to bytecode."""

    def __init__(self, flags: str = ""):
        self.flags = flags
        self.bytecode: List[Tuple] = []
        self.register_count = 0
        self.multiline = 'm' in flags
        self.ignorecase = 'i' in flags
        self.dotall = 's' in flags

    def compile(self, ast: Node, capture_count: int) -> List[Tuple]:
        """
        Compile AST to bytecode.

        Args:
            ast: The AST root node
            capture_count: Number of capture groups

        Returns:
            List of bytecode instructions
        """
        self.bytecode = []
        self.register_count = 0

        # Save group 0 start (full match)
        self._emit(Op.SAVE_START, 0)

        # Compile the pattern
        self._compile_node(ast)

        # Save group 0 end
        self._emit(Op.SAVE_END, 0)

        # Emit match
        self._emit(Op.MATCH)

        return self.bytecode

    def _emit(self, opcode: Op, *args) -> int:
        """Emit an instruction and return its index."""
        idx = len(self.bytecode)
        self.bytecode.append((opcode, *args))
        return idx

    def _patch(self, idx: int, opcode: Op, *args):
        """Patch an instruction at index."""
        self.bytecode[idx] = (opcode, *args)

    def _current_offset(self) -> int:
        """Get current bytecode offset."""
        return len(self.bytecode)

    def _compile_node(self, node: Node):
        """Compile a single AST node."""
        if isinstance(node, Char):
            self._compile_char(node)
        elif isinstance(node, Dot):
            self._compile_dot(node)
        elif isinstance(node, CharClass):
            self._compile_char_class(node)
        elif isinstance(node, Shorthand):
            self._compile_shorthand(node)
        elif isinstance(node, Anchor):
            self._compile_anchor(node)
        elif isinstance(node, Backref):
            self._compile_backref(node)
        elif isinstance(node, Group):
            self._compile_group(node)
        elif isinstance(node, Lookahead):
            self._compile_lookahead(node)
        elif isinstance(node, Lookbehind):
            self._compile_lookbehind(node)
        elif isinstance(node, Quantifier):
            self._compile_quantifier(node)
        elif isinstance(node, Alternative):
            self._compile_alternative(node)
        elif isinstance(node, Disjunction):
            self._compile_disjunction(node)
        else:
            raise RegExpError(f"Unknown node type: {type(node)}")

    def _compile_char(self, node: Char):
        """Compile literal character."""
        self._emit(Op.CHAR, ord(node.char))

    def _compile_dot(self, node: Dot):
        """Compile dot (any char)."""
        if self.dotall:
            self._emit(Op.ANY)
        else:
            self._emit(Op.DOT)

    def _compile_char_class(self, node: CharClass):
        """Compile character class."""
        # Convert ranges to (start_ord, end_ord) pairs
        ranges = []
        for start, end in node.ranges:
            # Handle shorthand escapes in character classes
            if len(start) == 2 and start[0] == '\\':
                # Expand shorthand
                shorthand_ranges = self._expand_shorthand(start[1])
                ranges.extend(shorthand_ranges)
            else:
                ranges.append((ord(start), ord(end)))

        if node.negated:
            self._emit(Op.RANGE_NEG, ranges)
        else:
            self._emit(Op.RANGE, ranges)

    def _expand_shorthand(self, ch: str) -> List[Tuple[int, int]]:
        """Expand shorthand character class to ranges."""
        if ch == 'd':
            return [(ord('0'), ord('9'))]
        elif ch == 'D':
            # Non-digit: everything except 0-9
            return [(0, ord('0') - 1), (ord('9') + 1, 0x10FFFF)]
        elif ch == 'w':
            return [
                (ord('0'), ord('9')),
                (ord('A'), ord('Z')),
                (ord('a'), ord('z')),
                (ord('_'), ord('_'))
            ]
        elif ch == 'W':
            # Non-word: complex negation
            return [
                (0, ord('0') - 1),
                (ord('9') + 1, ord('A') - 1),
                (ord('Z') + 1, ord('_') - 1),
                (ord('_') + 1, ord('a') - 1),
                (ord('z') + 1, 0x10FFFF)
            ]
        elif ch == 's':
            # Whitespace
            return [
                (ord(' '), ord(' ')),
                (ord('\t'), ord('\r')),  # \t, \n, \v, \f, \r
                (0x00A0, 0x00A0),  # NBSP
                (0x1680, 0x1680),  # Other Unicode spaces
                (0x2000, 0x200A),
                (0x2028, 0x2029),
                (0x202F, 0x202F),
                (0x205F, 0x205F),
                (0x3000, 0x3000),
                (0xFEFF, 0xFEFF)
            ]
        elif ch == 'S':
            # Non-whitespace - simplified
            return [(ord('!'), ord('~'))]  # Printable ASCII
        else:
            raise RegExpError(f"Unknown shorthand: \\{ch}")

    def _compile_shorthand(self, node: Shorthand):
        """Compile shorthand character class."""
        shorthand_ops = {
            'd': Op.DIGIT,
            'D': Op.NOT_DIGIT,
            'w': Op.WORD,
            'W': Op.NOT_WORD,
            's': Op.SPACE,
            'S': Op.NOT_SPACE,
        }
        self._emit(shorthand_ops[node.type])

    def _compile_anchor(self, node: Anchor):
        """Compile anchor."""
        if node.type == 'start':
            if self.multiline:
                self._emit(Op.LINE_START_M)
            else:
                self._emit(Op.LINE_START)
        elif node.type == 'end':
            if self.multiline:
                self._emit(Op.LINE_END_M)
            else:
                self._emit(Op.LINE_END)
        elif node.type == 'boundary':
            self._emit(Op.WORD_BOUNDARY)
        elif node.type == 'not_boundary':
            self._emit(Op.NOT_WORD_BOUNDARY)

    def _compile_backref(self, node: Backref):
        """Compile backreference."""
        if self.ignorecase:
            self._emit(Op.BACKREF_I, node.group)
        else:
            self._emit(Op.BACKREF, node.group)

    def _compile_group(self, node: Group):
        """Compile capturing/non-capturing group."""
        if node.capturing:
            self._emit(Op.SAVE_START, node.group_index)

        self._compile_node(node.body)

        if node.capturing:
            self._emit(Op.SAVE_END, node.group_index)

    def _compile_lookahead(self, node: Lookahead):
        """Compile lookahead assertion."""
        if node.positive:
            split_idx = self._emit(Op.LOOKAHEAD, 0)  # Placeholder for end
        else:
            split_idx = self._emit(Op.LOOKAHEAD_NEG, 0)

        self._compile_node(node.body)
        self._emit(Op.LOOKAHEAD_END)

        # Patch the jump target
        end_offset = self._current_offset()
        instr = self.bytecode[split_idx]
        self._patch(split_idx, instr[0], end_offset)

    def _compile_lookbehind(self, node: Lookbehind):
        """Compile lookbehind assertion."""
        if node.positive:
            split_idx = self._emit(Op.LOOKBEHIND, 0)
        else:
            split_idx = self._emit(Op.LOOKBEHIND_NEG, 0)

        self._compile_node(node.body)
        self._emit(Op.LOOKBEHIND_END)

        # Patch the jump target
        end_offset = self._current_offset()
        instr = self.bytecode[split_idx]
        self._patch(split_idx, instr[0], end_offset)

    def _compile_alternative(self, node: Alternative):
        """Compile sequence of terms."""
        for term in node.terms:
            self._compile_node(term)

    def _compile_disjunction(self, node: Disjunction):
        """Compile alternation."""
        if len(node.alternatives) == 1:
            self._compile_node(node.alternatives[0])
            return

        # For a|b|c, we generate:
        # SPLIT_FIRST -> alt2
        # <alt1>
        # JUMP -> end
        # alt2: SPLIT_FIRST -> alt3
        # <alt2>
        # JUMP -> end
        # alt3: <alt3>
        # end:

        jump_patches = []

        for i, alt in enumerate(node.alternatives):
            if i < len(node.alternatives) - 1:
                # Not last alternative - emit split
                split_idx = self._emit(Op.SPLIT_FIRST, 0)

            self._compile_node(alt)

            if i < len(node.alternatives) - 1:
                # Jump to end
                jump_idx = self._emit(Op.JUMP, 0)
                jump_patches.append(jump_idx)

                # Patch the split to point here
                self._patch(split_idx, Op.SPLIT_FIRST, self._current_offset())

        # Patch all jumps to end
        end_offset = self._current_offset()
        for jump_idx in jump_patches:
            self._patch(jump_idx, Op.JUMP, end_offset)

    def _compile_quantifier(self, node: Quantifier):
        """Compile quantifier with ReDoS protection."""
        min_count = node.min
        max_count = node.max
        greedy = node.greedy

        # Check if we need zero-advance detection
        need_advance_check = self._needs_advance_check(node.body)

        # Handle specific cases
        if min_count == 0 and max_count == 1:
            # ? quantifier
            self._compile_optional(node.body, greedy)
        elif min_count == 0 and max_count == -1:
            # * quantifier
            self._compile_star(node.body, greedy, need_advance_check)
        elif min_count == 1 and max_count == -1:
            # + quantifier
            self._compile_plus(node.body, greedy, need_advance_check)
        elif max_count == -1:
            # {n,} quantifier
            self._compile_at_least(node.body, min_count, greedy, need_advance_check)
        else:
            # {n,m} quantifier
            self._compile_range(node.body, min_count, max_count, greedy, need_advance_check)

    def _needs_advance_check(self, node: Node) -> bool:
        """
        Check if a node might match without advancing position.
        Used for ReDoS protection.
        """
        if isinstance(node, (Char, Dot, Shorthand)):
            return False  # Always advances
        if isinstance(node, CharClass):
            return False  # Always advances
        if isinstance(node, Anchor):
            return True  # Never advances
        if isinstance(node, (Lookahead, Lookbehind)):
            return True  # Never advances
        if isinstance(node, Backref):
            return True  # Might match empty
        if isinstance(node, Group):
            return self._needs_advance_check(node.body)
        if isinstance(node, Quantifier):
            if node.min == 0:
                return True  # Can match empty
            return self._needs_advance_check(node.body)
        if isinstance(node, Alternative):
            if not node.terms:
                return True  # Empty alternative
            return all(self._needs_advance_check(t) for t in node.terms)
        if isinstance(node, Disjunction):
            return any(self._needs_advance_check(a) for a in node.alternatives)
        return True  # Unknown - be safe

    def _compile_optional(self, body: Node, greedy: bool):
        """Compile ? quantifier."""
        if greedy:
            # Try match first
            split_idx = self._emit(Op.SPLIT_FIRST, 0)
            self._compile_node(body)
            self._patch(split_idx, Op.SPLIT_FIRST, self._current_offset())
        else:
            # Try skip first
            split_idx = self._emit(Op.SPLIT_NEXT, 0)
            self._compile_node(body)
            self._patch(split_idx, Op.SPLIT_NEXT, self._current_offset())

    def _compile_star(self, body: Node, greedy: bool, need_advance_check: bool):
        """Compile * quantifier."""
        if need_advance_check:
            reg = self._allocate_register()
            loop_start = self._current_offset()

            if greedy:
                self._emit(Op.SET_POS, reg)
                split_idx = self._emit(Op.SPLIT_FIRST, 0)
                self._compile_node(body)
                self._emit(Op.CHECK_ADVANCE, reg)
                self._emit(Op.JUMP, loop_start)
                self._patch(split_idx, Op.SPLIT_FIRST, self._current_offset())
            else:
                self._emit(Op.SET_POS, reg)
                split_idx = self._emit(Op.SPLIT_NEXT, 0)
                self._compile_node(body)
                self._emit(Op.CHECK_ADVANCE, reg)
                self._emit(Op.JUMP, loop_start)
                self._patch(split_idx, Op.SPLIT_NEXT, self._current_offset())
        else:
            loop_start = self._current_offset()
            if greedy:
                split_idx = self._emit(Op.SPLIT_FIRST, 0)
            else:
                split_idx = self._emit(Op.SPLIT_NEXT, 0)

            self._compile_node(body)
            self._emit(Op.JUMP, loop_start)

            if greedy:
                self._patch(split_idx, Op.SPLIT_FIRST, self._current_offset())
            else:
                self._patch(split_idx, Op.SPLIT_NEXT, self._current_offset())

    def _compile_plus(self, body: Node, greedy: bool, need_advance_check: bool):
        """Compile + quantifier."""
        if need_advance_check:
            reg = self._allocate_register()
            loop_start = self._current_offset()

            self._emit(Op.SET_POS, reg)
            self._compile_node(body)

            if greedy:
                split_idx = self._emit(Op.SPLIT_FIRST, 0)
                self._emit(Op.CHECK_ADVANCE, reg)
                self._emit(Op.JUMP, loop_start)
                self._patch(split_idx, Op.SPLIT_FIRST, self._current_offset())
            else:
                split_idx = self._emit(Op.SPLIT_NEXT, 0)
                self._emit(Op.CHECK_ADVANCE, reg)
                self._emit(Op.JUMP, loop_start)
                self._patch(split_idx, Op.SPLIT_NEXT, self._current_offset())
        else:
            loop_start = self._current_offset()
            self._compile_node(body)

            if greedy:
                split_idx = self._emit(Op.SPLIT_FIRST, 0)
            else:
                split_idx = self._emit(Op.SPLIT_NEXT, 0)

            self._emit(Op.JUMP, loop_start)

            if greedy:
                self._patch(split_idx, Op.SPLIT_FIRST, self._current_offset())
            else:
                self._patch(split_idx, Op.SPLIT_NEXT, self._current_offset())

    def _compile_at_least(self, body: Node, min_count: int, greedy: bool, need_advance_check: bool):
        """Compile {n,} quantifier."""
        # Emit body min_count times
        for _ in range(min_count):
            self._compile_node(body)

        # Then emit * for the rest
        self._compile_star(body, greedy, need_advance_check)

    def _compile_range(self, body: Node, min_count: int, max_count: int, greedy: bool, need_advance_check: bool):
        """Compile {n,m} quantifier."""
        # Emit body min_count times (required)
        for _ in range(min_count):
            self._compile_node(body)

        # Emit body (max_count - min_count) times (optional)
        for _ in range(max_count - min_count):
            self._compile_optional(body, greedy)

    def _allocate_register(self) -> int:
        """Allocate a register for position tracking."""
        reg = self.register_count
        self.register_count += 1
        if self.register_count > 255:
            raise RegExpError("Too many regex registers")
        return reg


def compile(ast: Node, capture_count: int, flags: str = "") -> List[Tuple]:
    """
    Compile regex AST to bytecode.

    Args:
        ast: The AST root node
        capture_count: Number of capture groups
        flags: Regex flags string

    Returns:
        List of bytecode instructions
    """
    compiler = RegexCompiler(flags)
    return compiler.compile(ast, capture_count)
