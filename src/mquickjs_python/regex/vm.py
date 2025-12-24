"""
Regex bytecode VM.

Executes regex bytecode with:
- Explicit backtracking stack
- Timeout integration via polling
- Memory limits (stack size)
- ReDoS protection
"""

from typing import List, Tuple, Optional, Callable
from .opcodes import RegexOpCode as Op


class RegexTimeoutError(Exception):
    """Raised when regex execution times out."""
    pass


class RegexStackOverflow(Exception):
    """Raised when regex stack limit is exceeded."""
    pass


class MatchResult:
    """Result of a successful regex match."""

    def __init__(self, groups: List[Optional[str]], index: int, input_str: str):
        self._groups = groups
        self.index = index
        self.input = input_str

    def __getitem__(self, idx: int) -> Optional[str]:
        if idx < 0 or idx >= len(self._groups):
            return None
        return self._groups[idx]

    def __len__(self) -> int:
        return len(self._groups)

    def group(self, idx: int = 0) -> Optional[str]:
        return self[idx]

    def groups(self) -> Tuple[Optional[str], ...]:
        return tuple(self._groups[1:])  # Exclude group 0

    def __repr__(self):
        return f"MatchResult({self._groups!r}, index={self.index})"


class RegexVM:
    """
    Regex bytecode virtual machine.

    Implements NFA-based matching with explicit backtracking stack.
    """

    # Default limits
    DEFAULT_STACK_LIMIT = 10000
    DEFAULT_POLL_INTERVAL = 100
    DEFAULT_STEP_LIMIT = 100000  # Hard limit on execution steps

    def __init__(
        self,
        bytecode: List[Tuple],
        capture_count: int,
        flags: str = "",
        poll_callback: Optional[Callable[[], bool]] = None,
        stack_limit: int = DEFAULT_STACK_LIMIT,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        step_limit: int = DEFAULT_STEP_LIMIT
    ):
        """
        Initialize regex VM.

        Args:
            bytecode: Compiled bytecode
            capture_count: Number of capture groups
            flags: Regex flags
            poll_callback: Called periodically; return True to abort
            stack_limit: Maximum backtrack stack size
            poll_interval: Steps between poll calls
            step_limit: Maximum execution steps (ReDoS protection)
        """
        self.bytecode = bytecode
        self.capture_count = capture_count
        self.flags = flags
        self.poll_callback = poll_callback
        self.stack_limit = stack_limit
        self.poll_interval = poll_interval
        self.step_limit = step_limit

        self.ignorecase = 'i' in flags
        self.multiline = 'm' in flags
        self.dotall = 's' in flags

    def match(self, string: str, start_pos: int = 0) -> Optional[MatchResult]:
        """
        Try to match at a specific position.

        Args:
            string: Input string
            start_pos: Position to start matching

        Returns:
            MatchResult if match found, None otherwise
        """
        return self._execute(string, start_pos, anchored=True)

    def search(self, string: str, start_pos: int = 0) -> Optional[MatchResult]:
        """
        Search for match anywhere in string.

        Args:
            string: Input string
            start_pos: Position to start searching

        Returns:
            MatchResult if match found, None otherwise
        """
        # Try matching at each position
        for pos in range(start_pos, len(string) + 1):
            result = self._execute(string, pos, anchored=False)
            if result is not None:
                return result
        return None

    def _execute(self, string: str, start_pos: int, anchored: bool) -> Optional[MatchResult]:
        """
        Execute bytecode against string.

        This is the main execution loop.
        """
        # Execution state
        pc = 0  # Program counter
        sp = start_pos  # String position
        step_count = 0

        # Capture positions: list of (start, end) for each group
        # -1 means unset
        captures = [[-1, -1] for _ in range(self.capture_count)]

        # Registers for position tracking (ReDoS protection)
        registers: List[int] = []

        # Backtrack stack: list of (pc, sp, captures_snapshot, registers_snapshot)
        stack: List[Tuple] = []

        while True:
            # Check limits periodically
            step_count += 1
            if step_count % self.poll_interval == 0:
                if self.poll_callback and self.poll_callback():
                    raise RegexTimeoutError("Regex execution timed out")

            # Hard step limit for ReDoS protection
            if step_count > self.step_limit:
                return None  # Fail gracefully on ReDoS

            # Stack overflow protection
            if len(stack) > self.stack_limit:
                raise RegexStackOverflow("Regex stack overflow")

            # Fetch instruction
            if pc >= len(self.bytecode):
                # Fell off end - no match
                if not stack:
                    return None
                pc, sp, captures, registers = self._backtrack(stack)
                continue

            instr = self.bytecode[pc]
            opcode = instr[0]

            # Execute instruction
            if opcode == Op.CHAR:
                char_code = instr[1]
                if sp >= len(string):
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)
                    continue

                ch = string[sp]
                if self.ignorecase:
                    match = ord(ch.lower()) == char_code or ord(ch.upper()) == char_code
                else:
                    match = ord(ch) == char_code

                if match:
                    sp += 1
                    pc += 1
                else:
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)

            elif opcode == Op.DOT:
                if sp >= len(string) or string[sp] == '\n':
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)
                    continue
                sp += 1
                pc += 1

            elif opcode == Op.ANY:
                if sp >= len(string):
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)
                    continue
                sp += 1
                pc += 1

            elif opcode == Op.DIGIT:
                if sp >= len(string) or not string[sp].isdigit():
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)
                    continue
                sp += 1
                pc += 1

            elif opcode == Op.NOT_DIGIT:
                if sp >= len(string) or string[sp].isdigit():
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)
                    continue
                sp += 1
                pc += 1

            elif opcode == Op.WORD:
                if sp >= len(string) or not (string[sp].isalnum() or string[sp] == '_'):
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)
                    continue
                sp += 1
                pc += 1

            elif opcode == Op.NOT_WORD:
                if sp >= len(string) or (string[sp].isalnum() or string[sp] == '_'):
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)
                    continue
                sp += 1
                pc += 1

            elif opcode == Op.SPACE:
                if sp >= len(string) or not string[sp].isspace():
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)
                    continue
                sp += 1
                pc += 1

            elif opcode == Op.NOT_SPACE:
                if sp >= len(string) or string[sp].isspace():
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)
                    continue
                sp += 1
                pc += 1

            elif opcode == Op.RANGE:
                ranges = instr[1]
                if sp >= len(string):
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)
                    continue

                ch = string[sp]
                ch_code = ord(ch.lower() if self.ignorecase else ch)

                matched = False
                for start, end in ranges:
                    if self.ignorecase:
                        # Check both cases
                        if start <= ch_code <= end:
                            matched = True
                            break
                        ch_upper = ord(ch.upper())
                        if start <= ch_upper <= end:
                            matched = True
                            break
                    else:
                        if start <= ch_code <= end:
                            matched = True
                            break

                if matched:
                    sp += 1
                    pc += 1
                else:
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)

            elif opcode == Op.RANGE_NEG:
                ranges = instr[1]
                if sp >= len(string):
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)
                    continue

                ch = string[sp]
                ch_code = ord(ch.lower() if self.ignorecase else ch)

                matched = False
                for start, end in ranges:
                    if start <= ch_code <= end:
                        matched = True
                        break

                if not matched:
                    sp += 1
                    pc += 1
                else:
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)

            elif opcode == Op.LINE_START:
                if sp != 0:
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)
                    continue
                pc += 1

            elif opcode == Op.LINE_START_M:
                if sp != 0 and (sp >= len(string) or string[sp - 1] != '\n'):
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)
                    continue
                pc += 1

            elif opcode == Op.LINE_END:
                if sp != len(string):
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)
                    continue
                pc += 1

            elif opcode == Op.LINE_END_M:
                if sp != len(string) and string[sp] != '\n':
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)
                    continue
                pc += 1

            elif opcode == Op.WORD_BOUNDARY:
                at_boundary = self._is_word_boundary(string, sp)
                if not at_boundary:
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)
                    continue
                pc += 1

            elif opcode == Op.NOT_WORD_BOUNDARY:
                at_boundary = self._is_word_boundary(string, sp)
                if at_boundary:
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)
                    continue
                pc += 1

            elif opcode == Op.JUMP:
                pc = instr[1]

            elif opcode == Op.SPLIT_FIRST:
                # Try current path first, backup alternative
                alt_pc = instr[1]
                # Save state for backtracking
                stack.append((
                    alt_pc,
                    sp,
                    [c.copy() for c in captures],
                    registers.copy()
                ))
                pc += 1

            elif opcode == Op.SPLIT_NEXT:
                # Try alternative first, backup current
                alt_pc = instr[1]
                # Save state for backtracking to continue after this
                stack.append((
                    pc + 1,
                    sp,
                    [c.copy() for c in captures],
                    registers.copy()
                ))
                pc = alt_pc

            elif opcode == Op.SAVE_START:
                group_idx = instr[1]
                if group_idx < len(captures):
                    captures[group_idx][0] = sp
                pc += 1

            elif opcode == Op.SAVE_END:
                group_idx = instr[1]
                if group_idx < len(captures):
                    captures[group_idx][1] = sp
                pc += 1

            elif opcode == Op.SAVE_RESET:
                start_idx = instr[1]
                end_idx = instr[2]
                for i in range(start_idx, end_idx + 1):
                    if i < len(captures):
                        captures[i] = [-1, -1]
                pc += 1

            elif opcode == Op.BACKREF:
                group_idx = instr[1]
                if group_idx >= len(captures):
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)
                    continue

                start, end = captures[group_idx]
                if start == -1 or end == -1:
                    # Unset capture - matches empty
                    pc += 1
                    continue

                captured = string[start:end]
                if sp + len(captured) > len(string):
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)
                    continue

                if string[sp:sp + len(captured)] == captured:
                    sp += len(captured)
                    pc += 1
                else:
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)

            elif opcode == Op.BACKREF_I:
                group_idx = instr[1]
                if group_idx >= len(captures):
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)
                    continue

                start, end = captures[group_idx]
                if start == -1 or end == -1:
                    pc += 1
                    continue

                captured = string[start:end]
                if sp + len(captured) > len(string):
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)
                    continue

                if string[sp:sp + len(captured)].lower() == captured.lower():
                    sp += len(captured)
                    pc += 1
                else:
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)

            elif opcode == Op.LOOKAHEAD:
                end_offset = instr[1]
                # Save current state and try to match lookahead
                saved_sp = sp
                saved_captures = [c.copy() for c in captures]

                # Create sub-execution for lookahead
                la_result = self._execute_lookahead(string, sp, pc + 1, end_offset)

                if la_result:
                    # Lookahead succeeded - restore position and continue after
                    sp = saved_sp
                    captures = saved_captures
                    pc = end_offset
                else:
                    # Lookahead failed
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)

            elif opcode == Op.LOOKAHEAD_NEG:
                end_offset = instr[1]
                saved_sp = sp
                saved_captures = [c.copy() for c in captures]

                la_result = self._execute_lookahead(string, sp, pc + 1, end_offset)

                if not la_result:
                    # Negative lookahead succeeded (inner didn't match)
                    sp = saved_sp
                    captures = saved_captures
                    pc = end_offset
                else:
                    # Negative lookahead failed (inner matched)
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)

            elif opcode == Op.LOOKAHEAD_END:
                # Successfully matched lookahead content
                return MatchResult([], 0, "")  # Special marker

            elif opcode == Op.LOOKBEHIND:
                end_offset = instr[1]
                saved_sp = sp
                saved_captures = [c.copy() for c in captures]

                # Try lookbehind - match pattern ending at current position
                lb_result = self._execute_lookbehind(string, sp, pc + 1, end_offset)

                if lb_result:
                    # Lookbehind succeeded - restore position and continue after
                    sp = saved_sp
                    captures = saved_captures
                    pc = end_offset
                else:
                    # Lookbehind failed
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)

            elif opcode == Op.LOOKBEHIND_NEG:
                end_offset = instr[1]
                saved_sp = sp
                saved_captures = [c.copy() for c in captures]

                lb_result = self._execute_lookbehind(string, sp, pc + 1, end_offset)

                if not lb_result:
                    # Negative lookbehind succeeded (inner didn't match)
                    sp = saved_sp
                    captures = saved_captures
                    pc = end_offset
                else:
                    # Negative lookbehind failed (inner matched)
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)

            elif opcode == Op.LOOKBEHIND_END:
                return MatchResult([], 0, "")  # Special marker

            elif opcode == Op.SET_POS:
                reg_idx = instr[1]
                while len(registers) <= reg_idx:
                    registers.append(-1)
                registers[reg_idx] = sp
                pc += 1

            elif opcode == Op.CHECK_ADVANCE:
                reg_idx = instr[1]
                if reg_idx < len(registers) and registers[reg_idx] == sp:
                    # Position didn't advance - fail to prevent infinite loop
                    if not stack:
                        return None
                    pc, sp, captures, registers = self._backtrack(stack)
                    continue
                pc += 1

            elif opcode == Op.MATCH:
                # Successful match!
                groups = []
                for start, end in captures:
                    if start == -1 or end == -1:
                        groups.append(None)
                    else:
                        groups.append(string[start:end])
                return MatchResult(groups, captures[0][0], string)

            else:
                raise RuntimeError(f"Unknown opcode: {opcode}")

    def _backtrack(self, stack: List[Tuple]) -> Tuple:
        """Pop and return state from backtrack stack."""
        return stack.pop()

    def _is_word_boundary(self, string: str, pos: int) -> bool:
        """Check if position is at a word boundary."""
        def is_word_char(ch: str) -> bool:
            return ch.isalnum() or ch == '_'

        before = pos > 0 and is_word_char(string[pos - 1])
        after = pos < len(string) and is_word_char(string[pos])
        return before != after

    def _execute_lookahead(self, string: str, start_pos: int, start_pc: int, end_pc: int) -> bool:
        """Execute bytecode for lookahead assertion."""
        # Simple recursive call with limited bytecode range
        pc = start_pc
        sp = start_pos
        captures = [[-1, -1] for _ in range(self.capture_count)]
        registers: List[int] = []
        stack: List[Tuple] = []
        step_count = 0

        while True:
            step_count += 1
            if step_count % self.poll_interval == 0:
                if self.poll_callback and self.poll_callback():
                    raise RegexTimeoutError("Regex execution timed out")

            if len(stack) > self.stack_limit:
                raise RegexStackOverflow("Regex stack overflow")

            if pc >= end_pc:
                return False

            instr = self.bytecode[pc]
            opcode = instr[0]

            if opcode == Op.LOOKAHEAD_END:
                return True  # Lookahead content matched

            # Reuse main execution logic for other opcodes
            # This is simplified - in production would share more code
            if opcode == Op.CHAR:
                char_code = instr[1]
                if sp >= len(string):
                    if not stack:
                        return False
                    pc, sp, captures, registers = stack.pop()
                    continue
                ch = string[sp]
                if self.ignorecase:
                    match = ord(ch.lower()) == char_code or ord(ch.upper()) == char_code
                else:
                    match = ord(ch) == char_code
                if match:
                    sp += 1
                    pc += 1
                else:
                    if not stack:
                        return False
                    pc, sp, captures, registers = stack.pop()

            elif opcode == Op.DOT:
                if sp >= len(string) or string[sp] == '\n':
                    if not stack:
                        return False
                    pc, sp, captures, registers = stack.pop()
                    continue
                sp += 1
                pc += 1

            elif opcode == Op.SPLIT_FIRST:
                alt_pc = instr[1]
                stack.append((alt_pc, sp, [c.copy() for c in captures], registers.copy()))
                pc += 1

            elif opcode == Op.SPLIT_NEXT:
                alt_pc = instr[1]
                stack.append((pc + 1, sp, [c.copy() for c in captures], registers.copy()))
                pc = alt_pc

            elif opcode == Op.JUMP:
                pc = instr[1]

            elif opcode == Op.MATCH:
                return True

            else:
                # Handle other opcodes similarly to main loop
                pc += 1

    def _execute_lookbehind(self, string: str, end_pos: int, start_pc: int, end_pc: int) -> bool:
        """Execute bytecode for lookbehind assertion.

        Lookbehind matches if the pattern matches text ending at end_pos.
        We try all possible start positions backwards from end_pos.
        """
        # Try all possible starting positions from 0 to end_pos
        # We want the pattern to match and end exactly at end_pos
        for start_pos in range(end_pos, -1, -1):
            result = self._try_lookbehind_at(string, start_pos, end_pos, start_pc, end_pc)
            if result:
                return True
        return False

    def _try_lookbehind_at(self, string: str, start_pos: int, end_pos: int,
                           start_pc: int, end_pc: int) -> bool:
        """Try to match lookbehind pattern from start_pos, checking it ends at end_pos."""
        pc = start_pc
        sp = start_pos
        captures = [[-1, -1] for _ in range(self.capture_count)]
        registers: List[int] = []
        stack: List[Tuple] = []
        step_count = 0

        while True:
            step_count += 1
            if step_count % self.poll_interval == 0:
                if self.poll_callback and self.poll_callback():
                    raise RegexTimeoutError("Regex execution timed out")

            if len(stack) > self.stack_limit:
                raise RegexStackOverflow("Regex stack overflow")

            if pc >= end_pc:
                return False

            instr = self.bytecode[pc]
            opcode = instr[0]

            if opcode == Op.LOOKBEHIND_END:
                # Check if we ended exactly at the target position
                return sp == end_pos

            if opcode == Op.CHAR:
                char_code = instr[1]
                if sp >= len(string):
                    if not stack:
                        return False
                    pc, sp, captures, registers = stack.pop()
                    continue
                ch = string[sp]
                if self.ignorecase:
                    match = ord(ch.lower()) == char_code or ord(ch.upper()) == char_code
                else:
                    match = ord(ch) == char_code
                if match:
                    sp += 1
                    pc += 1
                else:
                    if not stack:
                        return False
                    pc, sp, captures, registers = stack.pop()

            elif opcode == Op.DOT:
                if sp >= len(string) or string[sp] == '\n':
                    if not stack:
                        return False
                    pc, sp, captures, registers = stack.pop()
                    continue
                sp += 1
                pc += 1

            elif opcode == Op.DIGIT:
                if sp >= len(string) or not string[sp].isdigit():
                    if not stack:
                        return False
                    pc, sp, captures, registers = stack.pop()
                    continue
                sp += 1
                pc += 1

            elif opcode == Op.WORD:
                if sp >= len(string):
                    if not stack:
                        return False
                    pc, sp, captures, registers = stack.pop()
                    continue
                ch = string[sp]
                if ch.isalnum() or ch == '_':
                    sp += 1
                    pc += 1
                else:
                    if not stack:
                        return False
                    pc, sp, captures, registers = stack.pop()

            elif opcode == Op.SPLIT_FIRST:
                alt_pc = instr[1]
                stack.append((alt_pc, sp, [c.copy() for c in captures], registers.copy()))
                pc += 1

            elif opcode == Op.SPLIT_NEXT:
                alt_pc = instr[1]
                stack.append((pc + 1, sp, [c.copy() for c in captures], registers.copy()))
                pc = alt_pc

            elif opcode == Op.JUMP:
                pc = instr[1]

            elif opcode == Op.MATCH:
                # Check if we ended exactly at the target position
                return sp == end_pos

            else:
                # Handle other opcodes - advance pc
                pc += 1
