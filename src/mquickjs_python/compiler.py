"""Bytecode compiler - compiles AST to bytecode."""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
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
    FunctionDeclaration, FunctionExpression, ArrowFunctionExpression,
)
from .opcodes import OpCode
from .values import UNDEFINED


@dataclass
class CompiledFunction:
    """A compiled function."""
    name: str
    params: List[str]
    bytecode: bytes
    constants: List[Any]
    locals: List[str]
    num_locals: int
    free_vars: List[str] = field(default_factory=list)  # Variables captured from outer scope
    cell_vars: List[str] = field(default_factory=list)  # Local variables that are captured by inner functions
    source_map: Dict[int, Tuple[int, int]] = field(default_factory=dict)  # bytecode_pos -> (line, column)


@dataclass
class LoopContext:
    """Context for loops (for break/continue)."""
    break_jumps: List[int] = field(default_factory=list)
    continue_jumps: List[int] = field(default_factory=list)
    label: Optional[str] = None
    is_loop: bool = True  # False for switch statements (break only, no continue)


@dataclass
class TryContext:
    """Context for try-finally blocks (for break/continue/return)."""
    finalizer: Any = None  # The finally block AST node


class Compiler:
    """Compiles AST to bytecode."""

    def __init__(self):
        self.bytecode: List[int] = []
        self.constants: List[Any] = []
        self.names: List[str] = []
        self.locals: List[str] = []
        self.loop_stack: List[LoopContext] = []
        self.try_stack: List[TryContext] = []  # Track try-finally for break/continue/return
        self.functions: List[CompiledFunction] = []
        self._in_function: bool = False  # Track if we're compiling inside a function
        self._outer_locals: List[List[str]] = []  # Stack of outer scope locals
        self._free_vars: List[str] = []  # Free variables captured from outer scopes
        self._cell_vars: List[str] = []  # Local variables captured by inner functions
        self.source_map: Dict[int, Tuple[int, int]] = {}  # bytecode_pos -> (line, column)
        self._current_loc: Optional[Tuple[int, int]] = None  # Current source location

    def compile(self, node: Program) -> CompiledFunction:
        """Compile a program to bytecode."""
        body = node.body

        # Compile all statements except the last one
        for stmt in body[:-1] if body else []:
            self._compile_statement(stmt)

        # For the last statement, compile with completion value semantics
        if body:
            self._compile_statement_for_value(body[-1])
            self._emit(OpCode.RETURN)
        else:
            # Empty program returns undefined
            self._emit(OpCode.LOAD_UNDEFINED)
            self._emit(OpCode.RETURN)

        return CompiledFunction(
            name="<program>",
            params=[],
            bytecode=bytes(self.bytecode),
            constants=self.constants,
            locals=self.locals,
            num_locals=len(self.locals),
            source_map=self.source_map,
        )

    # Opcodes that use 16-bit arguments (jumps and jump-like)
    _JUMP_OPCODES = frozenset([OpCode.JUMP, OpCode.JUMP_IF_FALSE, OpCode.JUMP_IF_TRUE, OpCode.TRY_START])

    def _emit(self, opcode: OpCode, arg: Optional[int] = None) -> int:
        """Emit an opcode, return its position."""
        pos = len(self.bytecode)
        # Record source location for this bytecode position
        if self._current_loc is not None:
            self.source_map[pos] = self._current_loc
        self.bytecode.append(opcode)
        if arg is not None:
            if opcode in self._JUMP_OPCODES:
                # 16-bit little-endian for jump targets
                self.bytecode.append(arg & 0xFF)
                self.bytecode.append((arg >> 8) & 0xFF)
            else:
                self.bytecode.append(arg)
        return pos

    def _set_loc(self, node: Node) -> None:
        """Set current source location from an AST node."""
        if node.loc is not None:
            self._current_loc = (node.loc.line, node.loc.column)

    def _emit_jump(self, opcode: OpCode) -> int:
        """Emit a jump instruction, return position for patching.

        Uses 16-bit (2 byte) little-endian offset.
        """
        pos = len(self.bytecode)
        self.bytecode.append(opcode)
        self.bytecode.append(0)  # Low byte placeholder
        self.bytecode.append(0)  # High byte placeholder
        return pos

    def _patch_jump(self, pos: int, target: Optional[int] = None) -> None:
        """Patch a jump instruction to jump to target (or current position).

        Uses 16-bit (2 byte) little-endian offset.
        """
        if target is None:
            target = len(self.bytecode)
        self.bytecode[pos + 1] = target & 0xFF  # Low byte
        self.bytecode[pos + 2] = (target >> 8) & 0xFF  # High byte

    def _emit_pending_finally_blocks(self) -> None:
        """Emit all pending finally blocks (for break/continue/return)."""
        # Emit finally blocks in reverse order (innermost first)
        for try_ctx in reversed(self.try_stack):
            if try_ctx.finalizer:
                self._compile_statement(try_ctx.finalizer)

    def _add_constant(self, value: Any) -> int:
        """Add a constant and return its index."""
        if value in self.constants:
            return self.constants.index(value)
        self.constants.append(value)
        return len(self.constants) - 1

    def _add_name(self, name: str) -> int:
        """Add a name and return its index (stored in constants)."""
        # Store names in constants so VM can look them up
        return self._add_constant(name)

    def _add_local(self, name: str) -> int:
        """Add a local variable and return its slot."""
        if name in self.locals:
            return self.locals.index(name)
        self.locals.append(name)
        return len(self.locals) - 1

    def _get_local(self, name: str) -> Optional[int]:
        """Get local variable slot, or None if not local."""
        if name in self.locals:
            return self.locals.index(name)
        return None

    def _get_free_var(self, name: str) -> Optional[int]:
        """Get free variable slot, or None if not in outer scope."""
        if name in self._free_vars:
            return self._free_vars.index(name)
        # Check if it's in any outer scope
        for outer_locals in reversed(self._outer_locals):
            if name in outer_locals:
                # Add to free vars
                self._free_vars.append(name)
                return len(self._free_vars) - 1
        return None

    def _is_in_outer_scope(self, name: str) -> bool:
        """Check if name exists in any outer scope."""
        for outer_locals in self._outer_locals:
            if name in outer_locals:
                return True
        return False

    def _get_cell_var(self, name: str) -> Optional[int]:
        """Get cell variable slot, or None if not a cell var."""
        if name in self._cell_vars:
            return self._cell_vars.index(name)
        return None

    def _find_captured_vars(self, body: Node, locals_set: set) -> set:
        """Find all variables captured by inner functions."""
        captured = set()

        def visit(node):
            if isinstance(node, (FunctionDeclaration, FunctionExpression, ArrowFunctionExpression)):
                # Found inner function - check what variables it uses
                inner_captured = self._find_free_vars_in_function(node, locals_set)
                captured.update(inner_captured)
            elif isinstance(node, BlockStatement):
                for stmt in node.body:
                    visit(stmt)
            elif isinstance(node, IfStatement):
                visit(node.consequent)
                if node.alternate:
                    visit(node.alternate)
            elif isinstance(node, WhileStatement):
                visit(node.body)
            elif isinstance(node, DoWhileStatement):
                visit(node.body)
            elif isinstance(node, ForStatement):
                visit(node.body)
            elif isinstance(node, ForInStatement):
                visit(node.body)
            elif isinstance(node, TryStatement):
                visit(node.block)
                if node.handler:
                    visit(node.handler.body)
                if node.finalizer:
                    visit(node.finalizer)
            elif isinstance(node, SwitchStatement):
                for case in node.cases:
                    for stmt in case.consequent:
                        visit(stmt)
            elif isinstance(node, LabeledStatement):
                visit(node.body)
            elif hasattr(node, '__dict__'):
                # For expression nodes (e.g., arrow function expression body)
                for value in node.__dict__.values():
                    if isinstance(value, Node):
                        visit(value)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, Node):
                                visit(item)

        if isinstance(body, BlockStatement):
            for stmt in body.body:
                visit(stmt)
        else:
            # Expression body (e.g., arrow function with expression)
            visit(body)

        return captured

    def _find_free_vars_in_function(self, func_node, outer_locals: set) -> set:
        """Find variables used in function that come from outer scope.

        Also recursively checks nested functions - if a nested function needs
        a variable from outer scope, this function needs to capture it too.
        """
        free_vars = set()
        # Get function's own locals (params and declared vars)
        if isinstance(func_node, FunctionDeclaration):
            params = {p.name for p in func_node.params}
            body = func_node.body
        else:  # FunctionExpression
            params = {p.name for p in func_node.params}
            body = func_node.body

        local_vars = params.copy()
        # Find var declarations in function
        self._collect_var_decls(body, local_vars)

        # Now find identifiers used that are not local but are in outer_locals
        def visit_expr(node):
            if isinstance(node, Identifier):
                if node.name in outer_locals and node.name not in local_vars:
                    free_vars.add(node.name)
            elif isinstance(node, (FunctionDeclaration, FunctionExpression, ArrowFunctionExpression)):
                # Recursively check nested functions - any outer variable they need
                # must also be captured by this function (unless it's our local)
                nested_free = self._find_free_vars_in_function(node, outer_locals)
                for var in nested_free:
                    if var not in local_vars:
                        free_vars.add(var)
            elif hasattr(node, '__dict__'):
                for value in node.__dict__.values():
                    if isinstance(value, Node):
                        visit_expr(value)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, Node):
                                visit_expr(item)

        visit_expr(body)
        return free_vars

    def _collect_var_decls(self, node, var_set: set):
        """Collect all var declarations in a node."""
        if isinstance(node, VariableDeclaration):
            for decl in node.declarations:
                var_set.add(decl.id.name)
        elif isinstance(node, FunctionDeclaration):
            var_set.add(node.id.name)
            # Don't recurse into function body
        elif isinstance(node, BlockStatement):
            for stmt in node.body:
                self._collect_var_decls(stmt, var_set)
        elif hasattr(node, '__dict__'):
            for key, value in node.__dict__.items():
                if isinstance(value, Node) and not isinstance(value, (FunctionDeclaration, FunctionExpression, ArrowFunctionExpression)):
                    self._collect_var_decls(value, var_set)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, Node) and not isinstance(item, (FunctionDeclaration, FunctionExpression, ArrowFunctionExpression)):
                            self._collect_var_decls(item, var_set)

    # ---- Statements ----

    def _compile_statement(self, node: Node) -> None:
        """Compile a statement."""
        if isinstance(node, ExpressionStatement):
            self._compile_expression(node.expression)
            self._emit(OpCode.POP)

        elif isinstance(node, BlockStatement):
            for stmt in node.body:
                self._compile_statement(stmt)

        elif isinstance(node, EmptyStatement):
            pass

        elif isinstance(node, VariableDeclaration):
            for decl in node.declarations:
                name = decl.id.name
                if decl.init:
                    self._compile_expression(decl.init)
                else:
                    self._emit(OpCode.LOAD_UNDEFINED)

                if self._in_function:
                    # Inside function: use local variable
                    self._add_local(name)
                    # Check if it's a cell var (captured by inner function)
                    cell_slot = self._get_cell_var(name)
                    if cell_slot is not None:
                        self._emit(OpCode.STORE_CELL, cell_slot)
                    else:
                        slot = self._get_local(name)
                        self._emit(OpCode.STORE_LOCAL, slot)
                else:
                    # At program level: use global variable
                    idx = self._add_name(name)
                    self._emit(OpCode.STORE_NAME, idx)
                self._emit(OpCode.POP)

        elif isinstance(node, IfStatement):
            self._compile_expression(node.test)
            jump_false = self._emit_jump(OpCode.JUMP_IF_FALSE)

            self._compile_statement(node.consequent)

            if node.alternate:
                jump_end = self._emit_jump(OpCode.JUMP)
                self._patch_jump(jump_false)
                self._compile_statement(node.alternate)
                self._patch_jump(jump_end)
            else:
                self._patch_jump(jump_false)

        elif isinstance(node, WhileStatement):
            loop_ctx = LoopContext()
            self.loop_stack.append(loop_ctx)

            loop_start = len(self.bytecode)

            self._compile_expression(node.test)
            jump_false = self._emit_jump(OpCode.JUMP_IF_FALSE)

            self._compile_statement(node.body)

            self._emit(OpCode.JUMP, loop_start)
            self._patch_jump(jump_false)

            # Patch break jumps
            for pos in loop_ctx.break_jumps:
                self._patch_jump(pos)
            # Patch continue jumps
            for pos in loop_ctx.continue_jumps:
                self._patch_jump(pos, loop_start)

            self.loop_stack.pop()

        elif isinstance(node, DoWhileStatement):
            loop_ctx = LoopContext()
            self.loop_stack.append(loop_ctx)

            loop_start = len(self.bytecode)

            self._compile_statement(node.body)

            continue_target = len(self.bytecode)
            self._compile_expression(node.test)
            self._emit(OpCode.JUMP_IF_TRUE, loop_start)

            # Patch break jumps
            for pos in loop_ctx.break_jumps:
                self._patch_jump(pos)
            # Patch continue jumps
            for pos in loop_ctx.continue_jumps:
                self._patch_jump(pos, continue_target)

            self.loop_stack.pop()

        elif isinstance(node, ForStatement):
            loop_ctx = LoopContext()
            self.loop_stack.append(loop_ctx)

            # Init
            if node.init:
                if isinstance(node.init, VariableDeclaration):
                    self._compile_statement(node.init)
                else:
                    self._compile_expression(node.init)
                    self._emit(OpCode.POP)

            loop_start = len(self.bytecode)

            # Test
            jump_false = None
            if node.test:
                self._compile_expression(node.test)
                jump_false = self._emit_jump(OpCode.JUMP_IF_FALSE)

            # Body
            self._compile_statement(node.body)

            # Update
            continue_target = len(self.bytecode)
            if node.update:
                self._compile_expression(node.update)
                self._emit(OpCode.POP)

            self._emit(OpCode.JUMP, loop_start)

            if jump_false:
                self._patch_jump(jump_false)

            # Patch break/continue
            for pos in loop_ctx.break_jumps:
                self._patch_jump(pos)
            for pos in loop_ctx.continue_jumps:
                self._patch_jump(pos, continue_target)

            self.loop_stack.pop()

        elif isinstance(node, ForInStatement):
            loop_ctx = LoopContext()
            self.loop_stack.append(loop_ctx)

            # Compile object expression
            self._compile_expression(node.right)
            self._emit(OpCode.FOR_IN_INIT)

            loop_start = len(self.bytecode)
            self._emit(OpCode.FOR_IN_NEXT)
            jump_done = self._emit_jump(OpCode.JUMP_IF_TRUE)

            # Store key in variable
            if isinstance(node.left, VariableDeclaration):
                decl = node.left.declarations[0]
                name = decl.id.name
                if self._in_function:
                    self._add_local(name)
                    slot = self._get_local(name)
                    self._emit(OpCode.STORE_LOCAL, slot)
                else:
                    idx = self._add_name(name)
                    self._emit(OpCode.STORE_NAME, idx)
                self._emit(OpCode.POP)
            elif isinstance(node.left, Identifier):
                name = node.left.name
                slot = self._get_local(name)
                if slot is not None:
                    self._emit(OpCode.STORE_LOCAL, slot)
                else:
                    idx = self._add_name(name)
                    self._emit(OpCode.STORE_NAME, idx)
                self._emit(OpCode.POP)
            elif isinstance(node.left, MemberExpression):
                # for (obj.prop in ...) or for (obj[key] in ...)
                # After FOR_IN_NEXT: stack has [..., iterator, key]
                # We need for SET_PROP: obj, prop, key -> value (leaves value on stack)
                # Compile obj and prop first, then rotate key to top
                self._compile_expression(node.left.object)
                if node.left.computed:
                    self._compile_expression(node.left.property)
                else:
                    idx = self._add_constant(node.left.property.name)
                    self._emit(OpCode.LOAD_CONST, idx)
                # Stack is now: [..., iterator, key, obj, prop]
                # We need: [..., iterator, obj, prop, key]
                # ROT3 on (key, obj, prop) gives (obj, prop, key)
                self._emit(OpCode.ROT3)
                self._emit(OpCode.SET_PROP)
                self._emit(OpCode.POP)  # Pop the result of SET_PROP
            else:
                raise NotImplementedError(f"Unsupported for-in left: {type(node.left).__name__}")

            self._compile_statement(node.body)

            self._emit(OpCode.JUMP, loop_start)
            self._patch_jump(jump_done)
            self._emit(OpCode.POP)  # Pop iterator

            # Patch break and continue jumps
            for pos in loop_ctx.break_jumps:
                self._patch_jump(pos)
            for pos in loop_ctx.continue_jumps:
                self._patch_jump(pos, loop_start)

            self.loop_stack.pop()

        elif isinstance(node, ForOfStatement):
            loop_ctx = LoopContext()
            self.loop_stack.append(loop_ctx)

            # Compile iterable expression
            self._compile_expression(node.right)
            self._emit(OpCode.FOR_OF_INIT)

            loop_start = len(self.bytecode)
            self._emit(OpCode.FOR_OF_NEXT)
            jump_done = self._emit_jump(OpCode.JUMP_IF_TRUE)

            # Store value in variable
            if isinstance(node.left, VariableDeclaration):
                decl = node.left.declarations[0]
                name = decl.id.name
                if self._in_function:
                    self._add_local(name)
                    slot = self._get_local(name)
                    self._emit(OpCode.STORE_LOCAL, slot)
                else:
                    idx = self._add_name(name)
                    self._emit(OpCode.STORE_NAME, idx)
                self._emit(OpCode.POP)
            elif isinstance(node.left, Identifier):
                name = node.left.name
                slot = self._get_local(name)
                if slot is not None:
                    self._emit(OpCode.STORE_LOCAL, slot)
                else:
                    idx = self._add_name(name)
                    self._emit(OpCode.STORE_NAME, idx)
                self._emit(OpCode.POP)
            else:
                raise NotImplementedError(f"Unsupported for-of left: {type(node.left).__name__}")

            self._compile_statement(node.body)

            self._emit(OpCode.JUMP, loop_start)
            self._patch_jump(jump_done)
            self._emit(OpCode.POP)  # Pop iterator

            # Patch break and continue jumps
            for pos in loop_ctx.break_jumps:
                self._patch_jump(pos)
            for pos in loop_ctx.continue_jumps:
                self._patch_jump(pos, loop_start)

            self.loop_stack.pop()

        elif isinstance(node, BreakStatement):
            if not self.loop_stack:
                raise SyntaxError("'break' outside of loop")

            # Find the right loop context (labeled or innermost loop/switch)
            target_label = node.label.name if node.label else None
            ctx = None
            for loop_ctx in reversed(self.loop_stack):
                if target_label is not None:
                    # Labeled break - find the matching label
                    if loop_ctx.label == target_label:
                        ctx = loop_ctx
                        break
                else:
                    # Unlabeled break - find innermost loop or switch
                    # is_loop=True means it's a loop, is_loop=False with no label means switch
                    # Skip labeled statements (is_loop=False with label) for unlabeled break
                    if loop_ctx.is_loop or loop_ctx.label is None:
                        ctx = loop_ctx
                        break

            if ctx is None:
                if target_label:
                    raise SyntaxError(f"label '{target_label}' not found")
                else:
                    raise SyntaxError("'break' outside of loop")

            # Emit pending finally blocks before the break
            self._emit_pending_finally_blocks()

            pos = self._emit_jump(OpCode.JUMP)
            ctx.break_jumps.append(pos)

        elif isinstance(node, ContinueStatement):
            if not self.loop_stack:
                raise SyntaxError("'continue' outside of loop")

            # Find the right loop context (labeled or innermost loop, not switch)
            target_label = node.label.name if node.label else None
            ctx = None
            for loop_ctx in reversed(self.loop_stack):
                # Skip non-loop contexts (like switch) unless specifically labeled
                if not loop_ctx.is_loop and target_label is None:
                    continue
                if target_label is None or loop_ctx.label == target_label:
                    ctx = loop_ctx
                    break

            if ctx is None:
                raise SyntaxError(f"label '{target_label}' not found")

            # Emit pending finally blocks before the continue
            self._emit_pending_finally_blocks()

            pos = self._emit_jump(OpCode.JUMP)
            ctx.continue_jumps.append(pos)

        elif isinstance(node, ReturnStatement):
            # Emit pending finally blocks before the return
            self._emit_pending_finally_blocks()

            if node.argument:
                self._compile_expression(node.argument)
                self._emit(OpCode.RETURN)
            else:
                self._emit(OpCode.RETURN_UNDEFINED)

        elif isinstance(node, ThrowStatement):
            self._set_loc(node)  # Record location of throw statement
            self._compile_expression(node.argument)
            self._emit(OpCode.THROW)

        elif isinstance(node, TryStatement):
            # Push TryContext if there's a finally block so break/continue/return
            # can inline the finally code
            if node.finalizer:
                self.try_stack.append(TryContext(finalizer=node.finalizer))

            # Try block
            try_start = self._emit_jump(OpCode.TRY_START)

            self._compile_statement(node.block)
            self._emit(OpCode.TRY_END)

            # Jump past exception handler to normal finally
            jump_to_finally = self._emit_jump(OpCode.JUMP)

            # Exception handler
            self._patch_jump(try_start)
            if node.handler:
                # Has catch block
                self._emit(OpCode.CATCH)
                # Store exception in catch variable
                name = node.handler.param.name
                self._add_local(name)
                slot = self._get_local(name)
                self._emit(OpCode.STORE_LOCAL, slot)
                self._emit(OpCode.POP)
                self._compile_statement(node.handler.body)
                # Fall through to finally
            elif node.finalizer:
                # No catch, only finally - exception is on stack
                # Run finally then rethrow
                self._compile_statement(node.finalizer)
                self._emit(OpCode.THROW)  # Rethrow the exception

            # Pop TryContext before compiling normal finally
            if node.finalizer:
                self.try_stack.pop()

            # Normal finally block (after try completes normally or after catch)
            self._patch_jump(jump_to_finally)
            if node.finalizer:
                self._compile_statement(node.finalizer)

        elif isinstance(node, SwitchStatement):
            self._compile_expression(node.discriminant)

            jump_to_body: List[Tuple[int, int]] = []
            default_jump = None

            # Compile case tests
            for i, case in enumerate(node.cases):
                if case.test:
                    self._emit(OpCode.DUP)
                    self._compile_expression(case.test)
                    self._emit(OpCode.SEQ)
                    pos = self._emit_jump(OpCode.JUMP_IF_TRUE)
                    jump_to_body.append((pos, i))
                else:
                    default_jump = (self._emit_jump(OpCode.JUMP), i)

            # Jump to end if no match
            jump_end = self._emit_jump(OpCode.JUMP)

            # Case bodies
            case_positions = []
            loop_ctx = LoopContext(is_loop=False)  # For break statements only
            self.loop_stack.append(loop_ctx)

            for i, case in enumerate(node.cases):
                case_positions.append(len(self.bytecode))
                for stmt in case.consequent:
                    self._compile_statement(stmt)

            self._patch_jump(jump_end)
            self._emit(OpCode.POP)  # Pop discriminant

            # Patch jumps to case bodies
            for pos, idx in jump_to_body:
                self._patch_jump(pos, case_positions[idx])
            if default_jump:
                pos, idx = default_jump
                self._patch_jump(pos, case_positions[idx])

            # Patch break jumps
            for pos in loop_ctx.break_jumps:
                self._patch_jump(pos)

            self.loop_stack.pop()

        elif isinstance(node, FunctionDeclaration):
            # Compile function
            func = self._compile_function(node.id.name, node.params, node.body)
            func_idx = len(self.functions)
            self.functions.append(func)

            const_idx = self._add_constant(func)
            self._emit(OpCode.LOAD_CONST, const_idx)
            self._emit(OpCode.MAKE_CLOSURE, func_idx)

            name = node.id.name
            if self._in_function:
                # Inside function: use local or cell variable
                cell_idx = self._get_cell_var(name)
                if cell_idx is not None:
                    # Variable is captured - store in cell
                    self._emit(OpCode.STORE_CELL, cell_idx)
                else:
                    # Regular local
                    self._add_local(name)
                    slot = self._get_local(name)
                    self._emit(OpCode.STORE_LOCAL, slot)
            else:
                # At program level: use global variable
                idx = self._add_name(name)
                self._emit(OpCode.STORE_NAME, idx)
            self._emit(OpCode.POP)

        elif isinstance(node, LabeledStatement):
            # Create a loop context for the label
            # is_loop=False so unlabeled break/continue skip this context
            loop_ctx = LoopContext(label=node.label.name, is_loop=False)
            self.loop_stack.append(loop_ctx)

            # Compile the labeled body
            self._compile_statement(node.body)

            # Patch break jumps that target this label
            for pos in loop_ctx.break_jumps:
                self._patch_jump(pos)

            self.loop_stack.pop()

        else:
            raise NotImplementedError(f"Cannot compile statement: {type(node).__name__}")

    def _compile_statement_for_value(self, node: Node) -> None:
        """Compile a statement leaving its completion value on the stack.

        This is used for eval semantics where the last statement's value is returned.
        """
        if isinstance(node, ExpressionStatement):
            # Expression statement: value is the expression's value
            self._compile_expression(node.expression)

        elif isinstance(node, BlockStatement):
            # Block statement: value is the last statement's value
            if not node.body:
                self._emit(OpCode.LOAD_UNDEFINED)
            else:
                # Compile all but last normally
                for stmt in node.body[:-1]:
                    self._compile_statement(stmt)
                # Compile last for value
                self._compile_statement_for_value(node.body[-1])

        elif isinstance(node, IfStatement):
            # If statement: value is the chosen branch's value
            self._compile_expression(node.test)
            jump_false = self._emit_jump(OpCode.JUMP_IF_FALSE)

            self._compile_statement_for_value(node.consequent)

            if node.alternate:
                jump_end = self._emit_jump(OpCode.JUMP)
                self._patch_jump(jump_false)
                self._compile_statement_for_value(node.alternate)
                self._patch_jump(jump_end)
            else:
                jump_end = self._emit_jump(OpCode.JUMP)
                self._patch_jump(jump_false)
                self._emit(OpCode.LOAD_UNDEFINED)  # No else branch returns undefined
                self._patch_jump(jump_end)

        elif isinstance(node, EmptyStatement):
            # Empty statement: value is undefined
            self._emit(OpCode.LOAD_UNDEFINED)

        else:
            # Other statements: compile normally, then push undefined
            self._compile_statement(node)
            self._emit(OpCode.LOAD_UNDEFINED)

    def _find_required_free_vars(self, body: Node, local_vars: set) -> set:
        """Find all free variables required by this function including pass-through.

        This scans the function body for:
        1. Direct identifier references to outer scope variables
        2. Nested functions that need outer scope variables (pass-through)
        """
        free_vars = set()

        def visit(node):
            if isinstance(node, Identifier):
                if node.name not in local_vars and self._is_in_outer_scope(node.name):
                    free_vars.add(node.name)
            elif isinstance(node, (FunctionDeclaration, FunctionExpression, ArrowFunctionExpression)):
                # Check nested function's free vars - we need to pass through
                # any outer scope vars that aren't our locals
                nested_params = {p.name for p in node.params}
                nested_locals = nested_params.copy()
                nested_locals.add("arguments")
                if isinstance(node.body, BlockStatement):
                    self._collect_var_decls(node.body, nested_locals)
                nested_free = self._find_required_free_vars(node.body, nested_locals)
                for var in nested_free:
                    if var not in local_vars and self._is_in_outer_scope(var):
                        free_vars.add(var)
            elif isinstance(node, BlockStatement):
                for stmt in node.body:
                    visit(stmt)
            elif hasattr(node, '__dict__'):
                for value in node.__dict__.values():
                    if isinstance(value, Node):
                        visit(value)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, Node):
                                visit(item)

        if isinstance(body, BlockStatement):
            for stmt in body.body:
                visit(stmt)
        else:
            # Expression body
            visit(body)

        return free_vars

    def _compile_arrow_function(self, node: ArrowFunctionExpression) -> CompiledFunction:
        """Compile an arrow function."""
        # Save current state
        old_bytecode = self.bytecode
        old_constants = self.constants
        old_locals = self.locals
        old_loop_stack = self.loop_stack
        old_in_function = self._in_function
        old_free_vars = self._free_vars
        old_cell_vars = self._cell_vars

        # Push current locals to outer scope stack (for closure resolution)
        if self._in_function:
            self._outer_locals.append(old_locals[:])

        # New state for function
        self.bytecode = []
        self.constants = []
        self.locals = [p.name for p in node.params] + ["arguments"]
        self.loop_stack = []
        self._in_function = True

        # Collect all var declarations to know the full locals set
        local_vars_set = set(self.locals)
        if isinstance(node.body, BlockStatement):
            self._collect_var_decls(node.body, local_vars_set)

        # Find variables captured by inner functions
        captured = self._find_captured_vars(node.body, local_vars_set)
        self._cell_vars = list(captured)

        # Find all free variables needed
        required_free = self._find_required_free_vars(node.body, local_vars_set)
        self._free_vars = list(required_free)

        if node.expression:
            # Expression body: compile expression and return it
            self._compile_expression(node.body)
            self._emit(OpCode.RETURN)
        else:
            # Block body: compile statements
            for stmt in node.body.body:
                self._compile_statement(stmt)
            # Implicit return undefined
            self._emit(OpCode.RETURN_UNDEFINED)

        func = CompiledFunction(
            name="",  # Arrow functions are anonymous
            params=[p.name for p in node.params],
            bytecode=bytes(self.bytecode),
            constants=self.constants,
            locals=self.locals,
            num_locals=len(self.locals),
            free_vars=self._free_vars[:],
            cell_vars=self._cell_vars[:],
        )

        # Pop outer scope if we pushed it
        if old_in_function:
            self._outer_locals.pop()

        # Restore state
        self.bytecode = old_bytecode
        self.constants = old_constants
        self.locals = old_locals
        self.loop_stack = old_loop_stack
        self._in_function = old_in_function
        self._free_vars = old_free_vars
        self._cell_vars = old_cell_vars

        return func

    def _compile_function(
        self, name: str, params: List[Identifier], body: BlockStatement,
        is_expression: bool = False
    ) -> CompiledFunction:
        """Compile a function.

        Args:
            name: Function name (empty for anonymous)
            params: Parameter list
            body: Function body
            is_expression: If True and name is provided, make name available inside body
        """
        # Save current state
        old_bytecode = self.bytecode
        old_constants = self.constants
        old_locals = self.locals
        old_loop_stack = self.loop_stack
        old_in_function = self._in_function
        old_free_vars = self._free_vars
        old_cell_vars = self._cell_vars

        # Push current locals to outer scope stack (for closure resolution)
        if self._in_function:
            self._outer_locals.append(old_locals[:])

        # New state for function
        # Locals: params first, then 'arguments' reserved slot
        self.bytecode = []
        self.constants = []
        self.locals = [p.name for p in params] + ["arguments"]

        # For named function expressions, add the function name as a local
        # This allows recursive calls like: var f = function fact(n) { return n <= 1 ? 1 : n * fact(n-1); }
        if is_expression and name:
            self.locals.append(name)

        self.loop_stack = []
        self._in_function = True

        # Collect all var declarations to know the full locals set
        local_vars_set = set(self.locals)
        self._collect_var_decls(body, local_vars_set)
        # Update locals list with collected vars
        for var in local_vars_set:
            if var not in self.locals:
                self.locals.append(var)

        # Push current locals to outer scope stack BEFORE finding free vars
        # This is needed so nested functions can find their outer variables
        self._outer_locals.append(self.locals[:])

        # Find variables captured by inner functions
        captured = self._find_captured_vars(body, local_vars_set)
        self._cell_vars = list(captured)

        # Find all free variables needed (including pass-through for nested functions)
        required_free = self._find_required_free_vars(body, local_vars_set)
        self._free_vars = list(required_free)

        # Pop the outer scope we pushed
        self._outer_locals.pop()

        # Compile function body
        for stmt in body.body:
            self._compile_statement(stmt)

        # Implicit return undefined
        self._emit(OpCode.RETURN_UNDEFINED)

        func = CompiledFunction(
            name=name,
            params=[p.name for p in params],
            bytecode=bytes(self.bytecode),
            constants=self.constants,
            locals=self.locals,
            num_locals=len(self.locals),
            free_vars=self._free_vars[:],
            cell_vars=self._cell_vars[:],
        )

        # Pop outer scope if we pushed it
        if old_in_function:
            self._outer_locals.pop()

        # Restore state
        self.bytecode = old_bytecode
        self.constants = old_constants
        self.locals = old_locals
        self.loop_stack = old_loop_stack
        self._in_function = old_in_function
        self._free_vars = old_free_vars
        self._cell_vars = old_cell_vars

        return func

    # ---- Expressions ----

    def _compile_expression(self, node: Node) -> None:
        """Compile an expression."""
        if isinstance(node, NumericLiteral):
            idx = self._add_constant(node.value)
            self._emit(OpCode.LOAD_CONST, idx)

        elif isinstance(node, StringLiteral):
            idx = self._add_constant(node.value)
            self._emit(OpCode.LOAD_CONST, idx)

        elif isinstance(node, BooleanLiteral):
            if node.value:
                self._emit(OpCode.LOAD_TRUE)
            else:
                self._emit(OpCode.LOAD_FALSE)

        elif isinstance(node, NullLiteral):
            self._emit(OpCode.LOAD_NULL)

        elif isinstance(node, RegexLiteral):
            # Store (pattern, flags) tuple as constant
            idx = self._add_constant((node.pattern, node.flags))
            self._emit(OpCode.BUILD_REGEX, idx)

        elif isinstance(node, Identifier):
            name = node.name
            # Check if it's a cell var (local that's captured by inner function)
            cell_slot = self._get_cell_var(name)
            if cell_slot is not None:
                self._emit(OpCode.LOAD_CELL, cell_slot)
            else:
                slot = self._get_local(name)
                if slot is not None:
                    self._emit(OpCode.LOAD_LOCAL, slot)
                else:
                    # Check if it's a free variable (from outer scope)
                    closure_slot = self._get_free_var(name)
                    if closure_slot is not None:
                        self._emit(OpCode.LOAD_CLOSURE, closure_slot)
                    else:
                        idx = self._add_name(name)
                        self._emit(OpCode.LOAD_NAME, idx)

        elif isinstance(node, ThisExpression):
            self._emit(OpCode.THIS)

        elif isinstance(node, ArrayExpression):
            for elem in node.elements:
                self._compile_expression(elem)
            self._emit(OpCode.BUILD_ARRAY, len(node.elements))

        elif isinstance(node, ObjectExpression):
            for prop in node.properties:
                # Key
                if isinstance(prop.key, Identifier):
                    idx = self._add_constant(prop.key.name)
                    self._emit(OpCode.LOAD_CONST, idx)
                else:
                    self._compile_expression(prop.key)
                # Kind (for getters/setters)
                kind_idx = self._add_constant(prop.kind)
                self._emit(OpCode.LOAD_CONST, kind_idx)
                # Value
                self._compile_expression(prop.value)
            self._emit(OpCode.BUILD_OBJECT, len(node.properties))

        elif isinstance(node, UnaryExpression):
            # Special case for typeof with identifier - must not throw for undeclared vars
            if node.operator == "typeof" and isinstance(node.argument, Identifier):
                name = node.argument.name
                # Check for local, cell, or closure vars first
                local_slot = self._get_local(name)
                cell_slot = self._get_cell_var(name)
                closure_slot = self._get_free_var(name)
                if local_slot is not None:
                    self._emit(OpCode.LOAD_LOCAL, local_slot)
                    self._emit(OpCode.TYPEOF)
                elif cell_slot is not None:
                    self._emit(OpCode.LOAD_CELL, cell_slot)
                    self._emit(OpCode.TYPEOF)
                elif closure_slot is not None:
                    self._emit(OpCode.LOAD_CLOSURE, closure_slot)
                    self._emit(OpCode.TYPEOF)
                else:
                    # Use TYPEOF_NAME for global lookup - won't throw if undefined
                    idx = self._add_constant(name)
                    self._emit(OpCode.TYPEOF_NAME, idx)
            elif node.operator == "delete":
                # Handle delete specially - don't compile argument normally
                if isinstance(node.argument, MemberExpression):
                    # Compile as delete operation
                    self._compile_expression(node.argument.object)
                    if node.argument.computed:
                        self._compile_expression(node.argument.property)
                    else:
                        idx = self._add_constant(node.argument.property.name)
                        self._emit(OpCode.LOAD_CONST, idx)
                    self._emit(OpCode.DELETE_PROP)
                else:
                    self._emit(OpCode.LOAD_TRUE)  # delete on non-property returns true
            elif node.operator == "void":
                # void evaluates argument for side effects, returns undefined
                self._compile_expression(node.argument)
                self._emit(OpCode.POP)  # Discard the argument value
                self._emit(OpCode.LOAD_UNDEFINED)
            else:
                self._compile_expression(node.argument)
                op_map = {
                    "-": OpCode.NEG,
                    "+": OpCode.POS,
                    "!": OpCode.NOT,
                    "~": OpCode.BNOT,
                    "typeof": OpCode.TYPEOF,
                }
                if node.operator in op_map:
                    self._emit(op_map[node.operator])
                else:
                    raise NotImplementedError(f"Unary operator: {node.operator}")

        elif isinstance(node, UpdateExpression):
            # ++x or x++
            if isinstance(node.argument, Identifier):
                name = node.argument.name
                inc_op = OpCode.INC if node.operator == "++" else OpCode.DEC

                # Check if it's a cell var (local that's captured by inner function)
                cell_slot = self._get_cell_var(name)
                if cell_slot is not None:
                    self._emit(OpCode.LOAD_CELL, cell_slot)
                    if node.prefix:
                        self._emit(inc_op)
                        self._emit(OpCode.DUP)
                        self._emit(OpCode.STORE_CELL, cell_slot)
                        self._emit(OpCode.POP)
                    else:
                        self._emit(OpCode.DUP)
                        self._emit(inc_op)
                        self._emit(OpCode.STORE_CELL, cell_slot)
                        self._emit(OpCode.POP)
                else:
                    slot = self._get_local(name)
                    if slot is not None:
                        self._emit(OpCode.LOAD_LOCAL, slot)
                        if node.prefix:
                            self._emit(inc_op)
                            self._emit(OpCode.DUP)
                            self._emit(OpCode.STORE_LOCAL, slot)
                            self._emit(OpCode.POP)
                        else:
                            self._emit(OpCode.DUP)
                            self._emit(inc_op)
                            self._emit(OpCode.STORE_LOCAL, slot)
                            self._emit(OpCode.POP)
                    else:
                        # Check if it's a free variable (from outer scope)
                        closure_slot = self._get_free_var(name)
                        if closure_slot is not None:
                            self._emit(OpCode.LOAD_CLOSURE, closure_slot)
                            if node.prefix:
                                self._emit(inc_op)
                                self._emit(OpCode.DUP)
                                self._emit(OpCode.STORE_CLOSURE, closure_slot)
                                self._emit(OpCode.POP)
                            else:
                                self._emit(OpCode.DUP)
                                self._emit(inc_op)
                                self._emit(OpCode.STORE_CLOSURE, closure_slot)
                                self._emit(OpCode.POP)
                        else:
                            idx = self._add_name(name)
                            self._emit(OpCode.LOAD_NAME, idx)
                            if node.prefix:
                                self._emit(inc_op)
                                self._emit(OpCode.DUP)
                                self._emit(OpCode.STORE_NAME, idx)
                                self._emit(OpCode.POP)
                            else:
                                self._emit(OpCode.DUP)
                                self._emit(inc_op)
                                self._emit(OpCode.STORE_NAME, idx)
                                self._emit(OpCode.POP)
            elif isinstance(node.argument, MemberExpression):
                # a.x++ or arr[i]++
                inc_op = OpCode.INC if node.operator == "++" else OpCode.DEC

                # Compile object
                self._compile_expression(node.argument.object)
                # Compile property (or load constant)
                if node.argument.computed:
                    self._compile_expression(node.argument.property)
                else:
                    idx = self._add_constant(node.argument.property.name)
                    self._emit(OpCode.LOAD_CONST, idx)

                # Stack: [obj, prop]
                self._emit(OpCode.DUP2)  # [obj, prop, obj, prop]
                self._emit(OpCode.GET_PROP)  # [obj, prop, old_value]

                if node.prefix:
                    # ++a.x: return new value
                    self._emit(inc_op)  # [obj, prop, new_value]
                    self._emit(OpCode.DUP)  # [obj, prop, new_value, new_value]
                    # Rearrange: [obj, prop, nv, nv] -> [nv, obj, prop, nv]
                    self._emit(OpCode.ROT4)  # [prop, nv, nv, obj]
                    self._emit(OpCode.ROT4)  # [nv, nv, obj, prop]
                    self._emit(OpCode.ROT4)  # [nv, obj, prop, nv]
                    self._emit(OpCode.SET_PROP)  # [nv, nv]
                    self._emit(OpCode.POP)  # [nv]
                else:
                    # a.x++: return old value
                    self._emit(OpCode.DUP)  # [obj, prop, old_value, old_value]
                    self._emit(inc_op)  # [obj, prop, old_value, new_value]
                    # Rearrange: [obj, prop, old_value, new_value] -> [old_value, obj, prop, new_value]
                    self._emit(OpCode.SWAP)  # [obj, prop, new_value, old_value]
                    self._emit(OpCode.ROT4)  # [prop, new_value, old_value, obj]
                    self._emit(OpCode.ROT4)  # [new_value, old_value, obj, prop]
                    self._emit(OpCode.ROT4)  # [old_value, obj, prop, new_value]
                    self._emit(OpCode.SET_PROP)  # [old_value, new_value]
                    self._emit(OpCode.POP)  # [old_value]
            else:
                raise NotImplementedError("Update expression on non-identifier")

        elif isinstance(node, BinaryExpression):
            self._compile_expression(node.left)
            self._compile_expression(node.right)
            op_map = {
                "+": OpCode.ADD,
                "-": OpCode.SUB,
                "*": OpCode.MUL,
                "/": OpCode.DIV,
                "%": OpCode.MOD,
                "**": OpCode.POW,
                "&": OpCode.BAND,
                "|": OpCode.BOR,
                "^": OpCode.BXOR,
                "<<": OpCode.SHL,
                ">>": OpCode.SHR,
                ">>>": OpCode.USHR,
                "<": OpCode.LT,
                "<=": OpCode.LE,
                ">": OpCode.GT,
                ">=": OpCode.GE,
                "==": OpCode.EQ,
                "!=": OpCode.NE,
                "===": OpCode.SEQ,
                "!==": OpCode.SNE,
                "in": OpCode.IN,
                "instanceof": OpCode.INSTANCEOF,
            }
            if node.operator in op_map:
                self._emit(op_map[node.operator])
            else:
                raise NotImplementedError(f"Binary operator: {node.operator}")

        elif isinstance(node, LogicalExpression):
            self._compile_expression(node.left)
            if node.operator == "&&":
                # Short-circuit AND
                self._emit(OpCode.DUP)
                jump_false = self._emit_jump(OpCode.JUMP_IF_FALSE)
                self._emit(OpCode.POP)
                self._compile_expression(node.right)
                self._patch_jump(jump_false)
            elif node.operator == "||":
                # Short-circuit OR
                self._emit(OpCode.DUP)
                jump_true = self._emit_jump(OpCode.JUMP_IF_TRUE)
                self._emit(OpCode.POP)
                self._compile_expression(node.right)
                self._patch_jump(jump_true)

        elif isinstance(node, ConditionalExpression):
            self._compile_expression(node.test)
            jump_false = self._emit_jump(OpCode.JUMP_IF_FALSE)
            self._compile_expression(node.consequent)
            jump_end = self._emit_jump(OpCode.JUMP)
            self._patch_jump(jump_false)
            self._compile_expression(node.alternate)
            self._patch_jump(jump_end)

        elif isinstance(node, AssignmentExpression):
            if isinstance(node.left, Identifier):
                name = node.left.name
                if node.operator == "=":
                    self._compile_expression(node.right)
                else:
                    # Compound assignment - load current value first
                    cell_slot = self._get_cell_var(name)
                    if cell_slot is not None:
                        self._emit(OpCode.LOAD_CELL, cell_slot)
                    else:
                        slot = self._get_local(name)
                        if slot is not None:
                            self._emit(OpCode.LOAD_LOCAL, slot)
                        else:
                            closure_slot = self._get_free_var(name)
                            if closure_slot is not None:
                                self._emit(OpCode.LOAD_CLOSURE, closure_slot)
                            else:
                                idx = self._add_name(name)
                                self._emit(OpCode.LOAD_NAME, idx)
                    self._compile_expression(node.right)
                    op = node.operator[:-1]  # Remove '='
                    op_map = {
                        "+": OpCode.ADD, "-": OpCode.SUB,
                        "*": OpCode.MUL, "/": OpCode.DIV,
                        "%": OpCode.MOD, "&": OpCode.BAND,
                        "|": OpCode.BOR, "^": OpCode.BXOR,
                        "<<": OpCode.SHL, ">>": OpCode.SHR,
                        ">>>": OpCode.USHR,
                    }
                    self._emit(op_map[op])

                self._emit(OpCode.DUP)
                cell_slot = self._get_cell_var(name)
                if cell_slot is not None:
                    self._emit(OpCode.STORE_CELL, cell_slot)
                else:
                    slot = self._get_local(name)
                    if slot is not None:
                        self._emit(OpCode.STORE_LOCAL, slot)
                    else:
                        closure_slot = self._get_free_var(name)
                        if closure_slot is not None:
                            self._emit(OpCode.STORE_CLOSURE, closure_slot)
                        else:
                            idx = self._add_name(name)
                            self._emit(OpCode.STORE_NAME, idx)
                self._emit(OpCode.POP)

            elif isinstance(node.left, MemberExpression):
                # obj.prop = value or obj[key] = value
                self._compile_expression(node.left.object)
                if node.left.computed:
                    self._compile_expression(node.left.property)
                else:
                    idx = self._add_constant(node.left.property.name)
                    self._emit(OpCode.LOAD_CONST, idx)
                self._compile_expression(node.right)
                self._emit(OpCode.SET_PROP)

        elif isinstance(node, SequenceExpression):
            for i, expr in enumerate(node.expressions):
                self._compile_expression(expr)
                if i < len(node.expressions) - 1:
                    self._emit(OpCode.POP)

        elif isinstance(node, MemberExpression):
            self._compile_expression(node.object)
            if node.computed:
                self._compile_expression(node.property)
            else:
                idx = self._add_constant(node.property.name)
                self._emit(OpCode.LOAD_CONST, idx)
            self._emit(OpCode.GET_PROP)

        elif isinstance(node, CallExpression):
            if isinstance(node.callee, MemberExpression):
                # Method call: obj.method(args)
                self._compile_expression(node.callee.object)
                self._emit(OpCode.DUP)  # For 'this'
                if node.callee.computed:
                    self._compile_expression(node.callee.property)
                else:
                    idx = self._add_constant(node.callee.property.name)
                    self._emit(OpCode.LOAD_CONST, idx)
                self._emit(OpCode.GET_PROP)
                for arg in node.arguments:
                    self._compile_expression(arg)
                self._emit(OpCode.CALL_METHOD, len(node.arguments))
            else:
                # Regular call: f(args)
                self._compile_expression(node.callee)
                for arg in node.arguments:
                    self._compile_expression(arg)
                self._emit(OpCode.CALL, len(node.arguments))

        elif isinstance(node, NewExpression):
            self._compile_expression(node.callee)
            for arg in node.arguments:
                self._compile_expression(arg)
            self._emit(OpCode.NEW, len(node.arguments))

        elif isinstance(node, FunctionExpression):
            name = node.id.name if node.id else ""
            func = self._compile_function(name, node.params, node.body, is_expression=True)
            func_idx = len(self.functions)
            self.functions.append(func)

            const_idx = self._add_constant(func)
            self._emit(OpCode.LOAD_CONST, const_idx)
            self._emit(OpCode.MAKE_CLOSURE, func_idx)

        elif isinstance(node, ArrowFunctionExpression):
            func = self._compile_arrow_function(node)
            func_idx = len(self.functions)
            self.functions.append(func)

            const_idx = self._add_constant(func)
            self._emit(OpCode.LOAD_CONST, const_idx)
            self._emit(OpCode.MAKE_CLOSURE, func_idx)

        else:
            raise NotImplementedError(f"Cannot compile expression: {type(node).__name__}")
