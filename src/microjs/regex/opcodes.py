"""
Regex bytecode opcodes - based on mquickjs libregexp design.

This module defines all opcodes for the regex bytecode VM.
"""

from enum import IntEnum, auto


class RegexOpCode(IntEnum):
    """Regex bytecode opcodes."""

    # Character matching
    CHAR = auto()  # Match literal character(s)
    DOT = auto()  # Match any char except newline
    ANY = auto()  # Match any char including newline (dotall mode)

    # Character classes
    RANGE = auto()  # Match character in ranges [a-z]
    RANGE_NEG = auto()  # Match character NOT in ranges [^a-z]

    # Shorthand character classes
    DIGIT = auto()  # \d - match digit [0-9]
    NOT_DIGIT = auto()  # \D - match non-digit
    WORD = auto()  # \w - match word char [a-zA-Z0-9_]
    NOT_WORD = auto()  # \W - match non-word char
    SPACE = auto()  # \s - match whitespace
    NOT_SPACE = auto()  # \S - match non-whitespace

    # Anchors
    LINE_START = auto()  # ^ - match start of string
    LINE_START_M = auto()  # ^ with multiline flag
    LINE_END = auto()  # $ - match end of string
    LINE_END_M = auto()  # $ with multiline flag
    WORD_BOUNDARY = auto()  # \b - match word boundary
    NOT_WORD_BOUNDARY = auto()  # \B - match non-word boundary

    # Control flow
    JUMP = auto()  # Unconditional jump
    SPLIT_FIRST = auto()  # Split: try first path first, backup second
    SPLIT_NEXT = auto()  # Split: try second path first, backup first

    # Loops with zero-advance checking (ReDoS protection)
    LOOP = auto()  # Decrement counter, jump if non-zero
    LOOP_SPLIT_FIRST = auto()  # Loop with split (try first)
    LOOP_SPLIT_NEXT = auto()  # Loop with split (try second)
    LOOP_CHECK_ADV_FIRST = auto()  # Loop with zero-advance check (try first)
    LOOP_CHECK_ADV_NEXT = auto()  # Loop with zero-advance check (try second)

    # Capture groups
    SAVE_START = auto()  # Save capture group start position
    SAVE_END = auto()  # Save capture group end position
    SAVE_RESET = auto()  # Reset capture groups to unmatched

    # Backreferences
    BACKREF = auto()  # Match previously captured group
    BACKREF_I = auto()  # Match captured group (case-insensitive)

    # Lookahead assertions
    LOOKAHEAD = auto()  # Positive lookahead (?=...)
    LOOKAHEAD_NEG = auto()  # Negative lookahead (?!...)
    LOOKAHEAD_END = auto()  # End of lookahead

    # Lookbehind assertions
    LOOKBEHIND = auto()  # Positive lookbehind (?<=...)
    LOOKBEHIND_NEG = auto()  # Negative lookbehind (?<!...)
    LOOKBEHIND_END = auto()  # End of lookbehind

    # State management (for ReDoS protection)
    SET_POS = auto()  # Save current position to register
    CHECK_ADVANCE = auto()  # Check that position advanced
    RESET_IF_NO_ADV = auto()  # Reset captures if position didn't advance

    # Terminal
    MATCH = auto()  # Successful match


# Instruction format documentation
OPCODE_INFO = {
    # opcode: (name, arg_count, description)
    RegexOpCode.CHAR: ("CHAR", 1, "Match literal char (arg: char codepoint)"),
    RegexOpCode.DOT: ("DOT", 0, "Match any char except newline"),
    RegexOpCode.ANY: ("ANY", 0, "Match any char including newline"),
    RegexOpCode.RANGE: ("RANGE", 1, "Match char in ranges (arg: ranges list)"),
    RegexOpCode.RANGE_NEG: ("RANGE_NEG", 1, "Match char NOT in ranges"),
    RegexOpCode.DIGIT: ("DIGIT", 0, "Match digit [0-9]"),
    RegexOpCode.NOT_DIGIT: ("NOT_DIGIT", 0, "Match non-digit"),
    RegexOpCode.WORD: ("WORD", 0, "Match word char [a-zA-Z0-9_]"),
    RegexOpCode.NOT_WORD: ("NOT_WORD", 0, "Match non-word char"),
    RegexOpCode.SPACE: ("SPACE", 0, "Match whitespace"),
    RegexOpCode.NOT_SPACE: ("NOT_SPACE", 0, "Match non-whitespace"),
    RegexOpCode.LINE_START: ("LINE_START", 0, "Match start of string"),
    RegexOpCode.LINE_START_M: ("LINE_START_M", 0, "Match start of line (multiline)"),
    RegexOpCode.LINE_END: ("LINE_END", 0, "Match end of string"),
    RegexOpCode.LINE_END_M: ("LINE_END_M", 0, "Match end of line (multiline)"),
    RegexOpCode.WORD_BOUNDARY: ("WORD_BOUNDARY", 0, "Match word boundary"),
    RegexOpCode.NOT_WORD_BOUNDARY: ("NOT_WORD_BOUNDARY", 0, "Match non-word boundary"),
    RegexOpCode.JUMP: ("JUMP", 1, "Jump to offset (arg: offset)"),
    RegexOpCode.SPLIT_FIRST: ("SPLIT_FIRST", 1, "Split: try first, backup offset"),
    RegexOpCode.SPLIT_NEXT: ("SPLIT_NEXT", 1, "Split: try offset, backup first"),
    RegexOpCode.LOOP: ("LOOP", 2, "Loop (args: counter_reg, offset)"),
    RegexOpCode.LOOP_SPLIT_FIRST: ("LOOP_SPLIT_FIRST", 2, "Loop with split"),
    RegexOpCode.LOOP_SPLIT_NEXT: ("LOOP_SPLIT_NEXT", 2, "Loop with split"),
    RegexOpCode.LOOP_CHECK_ADV_FIRST: (
        "LOOP_CHECK_ADV_FIRST",
        2,
        "Loop with zero-advance check",
    ),
    RegexOpCode.LOOP_CHECK_ADV_NEXT: (
        "LOOP_CHECK_ADV_NEXT",
        2,
        "Loop with zero-advance check",
    ),
    RegexOpCode.SAVE_START: ("SAVE_START", 1, "Save capture start (arg: group_idx)"),
    RegexOpCode.SAVE_END: ("SAVE_END", 1, "Save capture end (arg: group_idx)"),
    RegexOpCode.SAVE_RESET: (
        "SAVE_RESET",
        2,
        "Reset captures (args: start_idx, end_idx)",
    ),
    RegexOpCode.BACKREF: ("BACKREF", 1, "Match captured group (arg: group_idx)"),
    RegexOpCode.BACKREF_I: ("BACKREF_I", 1, "Match captured group case-insensitive"),
    RegexOpCode.LOOKAHEAD: ("LOOKAHEAD", 1, "Positive lookahead (arg: end_offset)"),
    RegexOpCode.LOOKAHEAD_NEG: (
        "LOOKAHEAD_NEG",
        1,
        "Negative lookahead (arg: end_offset)",
    ),
    RegexOpCode.LOOKAHEAD_END: ("LOOKAHEAD_END", 0, "End of lookahead"),
    RegexOpCode.LOOKBEHIND: ("LOOKBEHIND", 1, "Positive lookbehind (arg: end_offset)"),
    RegexOpCode.LOOKBEHIND_NEG: (
        "LOOKBEHIND_NEG",
        1,
        "Negative lookbehind (arg: end_offset)",
    ),
    RegexOpCode.LOOKBEHIND_END: ("LOOKBEHIND_END", 0, "End of lookbehind"),
    RegexOpCode.SET_POS: ("SET_POS", 1, "Save position to register (arg: reg_idx)"),
    RegexOpCode.CHECK_ADVANCE: (
        "CHECK_ADVANCE",
        1,
        "Check position advanced (arg: reg_idx)",
    ),
    RegexOpCode.RESET_IF_NO_ADV: (
        "RESET_IF_NO_ADV",
        3,
        "Reset captures if position unchanged (args: reg_idx, start_group, end_group)",
    ),
    RegexOpCode.MATCH: ("MATCH", 0, "Successful match"),
}


def disassemble(bytecode: list) -> str:
    """
    Disassemble bytecode to human-readable format.

    Args:
        bytecode: List of (opcode, *args) tuples

    Returns:
        Disassembled string representation
    """
    lines = []
    for i, instr in enumerate(bytecode):
        opcode = instr[0]
        args = instr[1:] if len(instr) > 1 else []
        info = OPCODE_INFO.get(opcode, (str(opcode), 0, "Unknown"))
        name = info[0]

        if args:
            arg_str = ", ".join(repr(a) for a in args)
            lines.append(f"{i:4d}: {name} {arg_str}")
        else:
            lines.append(f"{i:4d}: {name}")

    return "\n".join(lines)
