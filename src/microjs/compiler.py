"""Bytecode compiler - compiles AST to bytecode."""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from .ast_nodes import (
    Node,
    Program,
    NumericLiteral,
    StringLiteral,
    BooleanLiteral,
    NullLiteral,
    RegexLiteral,
    Identifier,
    ThisExpression,
    ArrayExpression,
    ObjectExpression,
    Property,
    UnaryExpression,
    UpdateExpression,
    BinaryExpression,
    LogicalExpression,
    ConditionalExpression,
    AssignmentExpression,
    SequenceExpression,
    MemberExpression,
    CallExpression,
    NewExpression,
    ExpressionStatement,
    BlockStatement,
    EmptyStatement,
    VariableDeclaration,
    VariableDeclarator,
    IfStatement,
    WhileStatement,
    DoWhileStatement,
    ForStatement,
    ForInStatement,
    ForOfStatement,
    BreakStatement,
    ContinueStatement,
    ReturnStatement,
    ThrowStatement,
    TryStatement,
    CatchClause,
    SwitchStatement,
    SwitchCase,
    LabeledStatement,
    FunctionDeclaration,
    FunctionExpression,
    ArrowFunctionExpression,
)
from .errors import JSSyntaxError
from .opcodes import OPCODES_WITH_ARG, OpCode
from .values import UNDEFINED


@dataclass
class CompiledFunction:
    """A compiled function."""

    name: str
    params: List[str]
    bytecode: Tuple[int, ...]
    constants: List[Any]
    locals: List[str]
    num_locals: int
    free_vars: List[str] = field(
        default_factory=list
    )  # Variables captured from outer scope
    cell_vars: List[str] = field(
        default_factory=list
    )  # Local variables that are captured by inner functions
    source_map: Dict[int, Tuple[int, int]] = field(
        default_factory=dict
    )  # bytecode_pos -> (line, column)


@dataclass
class LoopContext:
    """A break/continue target: a loop, a switch or a labelled statement."""

    break_jumps: List[int] = field(default_factory=list)
    continue_jumps: List[int] = field(default_factory=list)
    labels: frozenset = frozenset()
    is_loop: bool = True  # Only loops accept continue
    is_switch: bool = False  # Unlabelled break targets loops and switches
    stack_items: int = 0  # Values kept on the stack inside (iterator, discriminant)


@dataclass
class TryContext:
    """A region needing cleanup when break/continue/return jump out of it."""

    handlers: int = 0  # Active try handlers to pop with TRY_END
    finalizer: Any = None  # finally block to run on the way out
    stack_items: int = 0  # Values to pop (an exception pending a rethrow)


class Compiler:
    """Compiles AST to bytecode."""

    def __init__(self):
        self.bytecode: List[int] = []
        self.constants: List[Any] = []
        self.names: List[str] = []
        self.locals: List[str] = []
        # Enclosing loops, switches, labels and try blocks, innermost last
        self.control_stack: List[Any] = []
        self._pending_labels: frozenset = frozenset()  # Labels for the next loop
        self.functions: List[CompiledFunction] = []
        self._in_function: bool = False  # Track if we're compiling inside a function
        self._outer_locals: List[List[str]] = []  # Stack of outer scope locals
        self._free_vars: List[str] = []  # Free variables captured from outer scopes
        self._cell_vars: List[str] = []  # Local variables captured by inner functions
        self.source_map: Dict[int, Tuple[int, int]] = (
            {}
        )  # bytecode_pos -> (line, column)
        self._current_loc: Optional[Tuple[int, int]] = None  # Current source location

    def compile(self, node: Program) -> CompiledFunction:
        """Compile a program to bytecode."""
        self._catch_count = 0
        self._rename_catch_params(node)
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
            bytecode=tuple(self.bytecode),
            constants=self.constants,
            locals=self.locals,
            num_locals=len(self.locals),
            source_map=self.source_map,
        )

    def _emit(self, opcode: OpCode, arg: Optional[int] = None) -> int:
        """Emit an opcode, return its position."""
        pos = len(self.bytecode)
        # Record source location for this bytecode position
        if self._current_loc is not None:
            self.source_map[pos] = self._current_loc
        self.bytecode.append(int(opcode))
        if opcode in OPCODES_WITH_ARG:
            assert arg is not None, f"{opcode.name} needs an operand"
            self.bytecode.append(arg)
        return pos

    def _set_loc(self, node: Node) -> None:
        """Set current source location from an AST node."""
        if node.loc is not None:
            self._current_loc = (node.loc.line, node.loc.column)

    def _emit_jump(self, opcode: OpCode) -> int:
        """Emit a jump instruction with a placeholder target, return its position."""
        pos = len(self.bytecode)
        self.bytecode.append(int(opcode))
        self.bytecode.append(0)  # Target, set by _patch_jump
        return pos

    def _patch_jump(self, pos: int, target: Optional[int] = None) -> None:
        """Point the jump at pos to target (default: the current position)."""
        if target is None:
            target = len(self.bytecode)
        self.bytecode[pos + 1] = target

    def _syntax_error(self, node: Node, message: str) -> JSSyntaxError:
        """Build a SyntaxError located at node."""
        if node.loc is not None:
            return JSSyntaxError(message, node.loc.line, node.loc.column)
        return JSSyntaxError(message)

    def _take_labels(self) -> frozenset:
        """Claim the labels written directly before the loop being compiled."""
        labels, self._pending_labels = self._pending_labels, frozenset()
        return labels

    def _emit_exit(self, target: int, pop_stack: bool = True) -> None:
        """Emit cleanup for jumping out of control_stack entries above target.

        Pops their try handlers, runs their finally blocks (each compiled in
        the scope outside its try) and, if pop_stack, pops their stack
        values. Returns skip stack pops: RETURN discards the frame's stack.
        """
        saved = self.control_stack
        for i in range(len(saved) - 1, target, -1):
            ctx = saved[i]
            if isinstance(ctx, TryContext):
                for _ in range(ctx.handlers):
                    self._emit(OpCode.TRY_END)
            if pop_stack:
                for _ in range(ctx.stack_items):
                    self._emit(OpCode.POP)
            if isinstance(ctx, TryContext) and ctx.finalizer:
                self.control_stack = saved[:i]
                try:
                    self._compile_statement(ctx.finalizer)
                finally:
                    self.control_stack = saved

    def _emit_store_declared(self, name: str) -> None:
        """Store the top of stack in a declared variable (it stays on the stack)."""
        if self._in_function:
            self._add_local(name)
            cell_slot = self._get_cell_var(name)
            if cell_slot is not None:
                self._emit(OpCode.STORE_CELL, cell_slot)
            else:
                self._emit(OpCode.STORE_LOCAL, self._get_local(name))
        else:
            self._emit(OpCode.STORE_NAME, self._add_name(name))

    def _find_jump_target(self, node: Node, is_continue: bool) -> int:
        """Return the control_stack index that break/continue node targets."""
        keyword = "continue" if is_continue else "break"
        label = node.label.name if node.label else None
        for i in range(len(self.control_stack) - 1, -1, -1):
            ctx = self.control_stack[i]
            if not isinstance(ctx, LoopContext):
                continue
            if label is not None:
                if label in ctx.labels:
                    if is_continue and not ctx.is_loop:
                        raise self._syntax_error(
                            node, f"Label '{label}' does not denote a loop"
                        )
                    return i
            elif ctx.is_loop or (ctx.is_switch and not is_continue):
                return i
        if label is not None:
            raise self._syntax_error(node, f"Undefined label '{label}'")
        raise self._syntax_error(node, f"Illegal {keyword} statement")

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
            if isinstance(
                node, (FunctionDeclaration, FunctionExpression, ArrowFunctionExpression)
            ):
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
            elif hasattr(node, "__dict__"):
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
            elif isinstance(
                node, (FunctionDeclaration, FunctionExpression, ArrowFunctionExpression)
            ):
                # Recursively check nested functions - any outer variable they need
                # must also be captured by this function (unless it's our local)
                nested_free = self._find_free_vars_in_function(node, outer_locals)
                for var in nested_free:
                    if var not in local_vars:
                        free_vars.add(var)
            elif hasattr(node, "__dict__"):
                for value in node.__dict__.values():
                    if isinstance(value, Node):
                        visit_expr(value)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, Node):
                                visit_expr(item)

        visit_expr(body)
        return free_vars

    # ---- Catch parameter scoping ----

    def _rename_catch_params(self, root: Node) -> None:
        """Give every catch parameter in the tree a unique name.

        A catch parameter is scoped to its catch block, but the compiler
        only has function-level locals and globals. Renaming the parameter
        and its references in the catch body (to a name like "e%catch1",
        which no identifier can clash with) lets the existing variable
        machinery handle it without clobbering an outer variable.

        Iterative, like the parser, so deeply nested code cannot overflow
        the Python stack.
        """
        stack = [root]
        while stack:
            node = stack.pop()
            if isinstance(node, TryStatement) and node.handler:
                handler = node.handler
                old = handler.param.name
                self._catch_count += 1
                new = f"{old}%catch{self._catch_count}"
                handler.param = self._renamed(handler.param, new)
                self._rename_refs(handler.body, old, new)
            stack.extend(self._child_nodes(node))

    @staticmethod
    def _child_nodes(node: Node) -> List[Node]:
        """Return the direct child nodes of an AST node."""
        children = []
        for key, value in node.__dict__.items():
            if key.startswith("_"):
                continue
            if isinstance(value, Node):
                children.append(value)
            elif isinstance(value, list):
                children.extend(item for item in value if isinstance(item, Node))
        return children

    @staticmethod
    def _renamed(ident: Identifier, name: str) -> Identifier:
        new = Identifier(name)
        new.loc = ident.loc
        return new

    @staticmethod
    def _is_variable_slot(node: Node, key: str) -> bool:
        """Whether the child at node.key can be a variable reference."""
        if key == "label":
            return False
        if key == "property" and isinstance(node, MemberExpression):
            return node.computed
        if key == "key" and isinstance(node, Property):
            return node.computed
        return True

    def _binds_name(self, node: Node, name: str) -> bool:
        """Whether node introduces its own binding of name for its body."""
        if isinstance(node, CatchClause):
            return node.param.name == name
        if isinstance(
            node, (FunctionDeclaration, FunctionExpression, ArrowFunctionExpression)
        ):
            declared = {p.name for p in node.params}
            if getattr(node, "id", None) is not None:
                declared.add(node.id.name)
            if isinstance(node.body, BlockStatement):
                self._collect_var_decls(node.body, declared)
            return name in declared
        return False

    def _rename_refs(self, root: Node, old: str, new: str) -> None:
        """Rename references to variable old under root to new, in place.

        Identifiers are replaced rather than mutated, since the parser can
        share one Identifier between a shorthand property's key and value.
        """
        stack = [root]
        while stack:
            node = stack.pop()
            for key, value in list(node.__dict__.items()):
                if key.startswith("_") or not self._is_variable_slot(node, key):
                    continue
                if isinstance(value, Node):
                    value = [value]
                    single = True
                elif isinstance(value, list):
                    single = False
                else:
                    continue
                for i, child in enumerate(value):
                    if isinstance(child, Identifier):
                        if child.name == old:
                            value[i] = self._renamed(child, new)
                    elif isinstance(child, Node) and not self._binds_name(child, old):
                        stack.append(child)
                if single:
                    setattr(node, key, value[0])

    def _collect_var_decls(self, node, var_set: set):
        """Collect all var declarations (and catch parameters) in a node."""
        if isinstance(node, CatchClause):
            var_set.add(node.param.name)
            self._collect_var_decls(node.body, var_set)
        elif isinstance(node, VariableDeclaration):
            for decl in node.declarations:
                var_set.add(decl.id.name)
        elif isinstance(node, FunctionDeclaration):
            var_set.add(node.id.name)
            # Don't recurse into function body
        elif isinstance(node, BlockStatement):
            for stmt in node.body:
                self._collect_var_decls(stmt, var_set)
        elif hasattr(node, "__dict__"):
            for key, value in node.__dict__.items():
                if isinstance(value, Node) and not isinstance(
                    value,
                    (FunctionDeclaration, FunctionExpression, ArrowFunctionExpression),
                ):
                    self._collect_var_decls(value, var_set)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, Node) and not isinstance(
                            item,
                            (
                                FunctionDeclaration,
                                FunctionExpression,
                                ArrowFunctionExpression,
                            ),
                        ):
                            self._collect_var_decls(item, var_set)

    # ---- Statements ----

    def _compile_statement(self, node: Node) -> None:
        """Compile a statement."""
        if isinstance(node, ExpressionStatement):
            self._compile_expression(node.expression)
            self._emit(OpCode.POP)

        elif isinstance(node, BlockStatement):
            # Handle nested blocks iteratively to avoid deep recursion
            work_stack = [node]
            while work_stack:
                current = work_stack.pop()
                if isinstance(current, BlockStatement):
                    # Push body statements in reverse order
                    for stmt in reversed(current.body):
                        work_stack.append(stmt)
                else:
                    self._compile_statement(current)

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
            loop_ctx = LoopContext(labels=self._take_labels())
            self.control_stack.append(loop_ctx)

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

            self.control_stack.pop()

        elif isinstance(node, DoWhileStatement):
            loop_ctx = LoopContext(labels=self._take_labels())
            self.control_stack.append(loop_ctx)

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

            self.control_stack.pop()

        elif isinstance(node, ForStatement):
            loop_ctx = LoopContext(labels=self._take_labels())
            self.control_stack.append(loop_ctx)

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

            self.control_stack.pop()

        elif isinstance(node, ForInStatement):
            loop_ctx = LoopContext(labels=self._take_labels(), stack_items=1)
            self.control_stack.append(loop_ctx)

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
                raise NotImplementedError(
                    f"Unsupported for-in left: {type(node.left).__name__}"
                )

            self._compile_statement(node.body)

            self._emit(OpCode.JUMP, loop_start)
            self._patch_jump(jump_done)
            self._emit(OpCode.POP)  # Pop iterator

            # Patch break and continue jumps
            for pos in loop_ctx.break_jumps:
                self._patch_jump(pos)
            for pos in loop_ctx.continue_jumps:
                self._patch_jump(pos, loop_start)

            self.control_stack.pop()

        elif isinstance(node, ForOfStatement):
            loop_ctx = LoopContext(labels=self._take_labels(), stack_items=1)
            self.control_stack.append(loop_ctx)

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
                raise NotImplementedError(
                    f"Unsupported for-of left: {type(node.left).__name__}"
                )

            self._compile_statement(node.body)

            self._emit(OpCode.JUMP, loop_start)
            self._patch_jump(jump_done)
            self._emit(OpCode.POP)  # Pop iterator

            # Patch break and continue jumps
            for pos in loop_ctx.break_jumps:
                self._patch_jump(pos)
            for pos in loop_ctx.continue_jumps:
                self._patch_jump(pos, loop_start)

            self.control_stack.pop()

        elif isinstance(node, BreakStatement):
            target = self._find_jump_target(node, is_continue=False)
            self._emit_exit(target)
            # break also leaves the target itself
            for _ in range(self.control_stack[target].stack_items):
                self._emit(OpCode.POP)
            pos = self._emit_jump(OpCode.JUMP)
            self.control_stack[target].break_jumps.append(pos)

        elif isinstance(node, ContinueStatement):
            target = self._find_jump_target(node, is_continue=True)
            self._emit_exit(target)
            pos = self._emit_jump(OpCode.JUMP)
            self.control_stack[target].continue_jumps.append(pos)

        elif isinstance(node, ReturnStatement):
            # Evaluate the return value first, then run finally blocks
            if node.argument:
                self._compile_expression(node.argument)
            else:
                self._emit(OpCode.LOAD_UNDEFINED)
            self._emit_exit(-1, pop_stack=False)
            self._emit(OpCode.RETURN)

        elif isinstance(node, ThrowStatement):
            self._set_loc(node)  # Record location of throw statement
            self._compile_expression(node.argument)
            self._emit(OpCode.THROW)

        elif isinstance(node, TryStatement):
            finalizer = node.finalizer

            # try block, protected by handler A
            try_start = self._emit_jump(OpCode.TRY_START)
            self.control_stack.append(TryContext(handlers=1, finalizer=finalizer))
            self._compile_statement(node.block)
            self.control_stack.pop()
            self._emit(OpCode.TRY_END)
            normal_exits = [self._emit_jump(OpCode.JUMP)]

            # Handler A: the exception is on the stack
            self._patch_jump(try_start)
            if node.handler:
                if finalizer:
                    # Protect the catch block so finally runs if it throws
                    catch_start = self._emit_jump(OpCode.TRY_START)
                self._emit_store_declared(node.handler.param.name)
                self._emit(OpCode.POP)
                if finalizer:
                    self.control_stack.append(
                        TryContext(handlers=1, finalizer=finalizer)
                    )
                self._compile_statement(node.handler.body)
                if finalizer:
                    self.control_stack.pop()
                    self._emit(OpCode.TRY_END)
                    normal_exits.append(self._emit_jump(OpCode.JUMP))
                    self._patch_jump(catch_start)
            if finalizer:
                # Exceptional path: run finally, then rethrow the exception
                self.control_stack.append(TryContext(stack_items=1))
                self._compile_statement(finalizer)
                self.control_stack.pop()
                self._emit(OpCode.THROW)

            # Normal completion (of the try block or the catch block)
            for pos in normal_exits:
                self._patch_jump(pos)
            if finalizer:
                self._compile_statement(finalizer)

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
            loop_ctx = LoopContext(is_loop=False, is_switch=True, stack_items=1)
            self.control_stack.append(loop_ctx)

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

            self.control_stack.pop()

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
            labels = {node.label.name}
            body = node.body
            while isinstance(body, LabeledStatement):
                labels.add(body.label.name)
                body = body.body
            if isinstance(
                body,
                (
                    WhileStatement,
                    DoWhileStatement,
                    ForStatement,
                    ForInStatement,
                    ForOfStatement,
                ),
            ):
                # The loop owns its labels, so 'continue label' reaches it
                self._pending_labels = frozenset(labels)
                self._compile_statement(body)
            else:
                # Any other statement: a target for 'break label' only
                loop_ctx = LoopContext(labels=frozenset(labels), is_loop=False)
                self.control_stack.append(loop_ctx)
                self._compile_statement(body)
                for pos in loop_ctx.break_jumps:
                    self._patch_jump(pos)
                self.control_stack.pop()

        else:
            raise NotImplementedError(
                f"Cannot compile statement: {type(node).__name__}"
            )

    def _compile_statement_for_value(self, node: Node) -> None:
        """Compile a statement leaving its completion value on the stack.

        This is used for eval semantics where the last statement's value is returned.
        """
        if isinstance(node, ExpressionStatement):
            # Expression statement: value is the expression's value
            self._compile_expression(node.expression)

        elif isinstance(node, BlockStatement):
            # Block statement: value is the last statement's value
            # Handle nested blocks iteratively to avoid deep recursion
            current = node
            intermediate_stmts = []

            # Drill down through nested blocks, collecting intermediate statements
            while isinstance(current, BlockStatement):
                if not current.body:
                    # Empty block returns undefined
                    for stmt in intermediate_stmts:
                        self._compile_statement(stmt)
                    self._emit(OpCode.LOAD_UNDEFINED)
                    return
                # Collect all but last statement
                intermediate_stmts.extend(current.body[:-1])
                # Continue with last statement
                current = current.body[-1]

            # Compile all intermediate statements
            for stmt in intermediate_stmts:
                self._compile_statement(stmt)

            # Compile the innermost last statement for value
            self._compile_statement_for_value(current)

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
            elif isinstance(
                node, (FunctionDeclaration, FunctionExpression, ArrowFunctionExpression)
            ):
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
            elif hasattr(node, "__dict__"):
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

    def _compile_arrow_function(
        self, node: ArrowFunctionExpression
    ) -> CompiledFunction:
        """Compile an arrow function."""
        # Save current state
        old_bytecode = self.bytecode
        old_constants = self.constants
        old_locals = self.locals
        old_control_stack = self.control_stack
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
        self.control_stack = []
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
            bytecode=tuple(self.bytecode),
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
        self.control_stack = old_control_stack
        self._in_function = old_in_function
        self._free_vars = old_free_vars
        self._cell_vars = old_cell_vars

        return func

    def _compile_function(
        self,
        name: str,
        params: List[Identifier],
        body: BlockStatement,
        is_expression: bool = False,
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
        old_control_stack = self.control_stack
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

        self.control_stack = []
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
            bytecode=tuple(self.bytecode),
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
        self.control_stack = old_control_stack
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
            # Handle arrays using a stack-based approach to avoid deep recursion
            # Stack entries: ('ARRAY', array_node, elem_index) or ('BUILD', num_elements)
            work_stack = [("ARRAY", node, 0)]

            while work_stack:
                entry = work_stack.pop()

                if entry[0] == "BUILD":
                    # Build an array with the given number of elements
                    self._emit(OpCode.BUILD_ARRAY, entry[1])

                elif entry[0] == "ARRAY":
                    array_node, idx = entry[1], entry[2]
                    elements = array_node.elements

                    if idx >= len(elements):
                        # All elements compiled, build the array
                        self._emit(OpCode.BUILD_ARRAY, len(elements))
                    else:
                        elem = elements[idx]
                        # Schedule next element
                        work_stack.append(("ARRAY", array_node, idx + 1))

                        if isinstance(elem, ArrayExpression):
                            # Process nested array first
                            work_stack.append(("ARRAY", elem, 0))
                        else:
                            # Compile non-array element directly
                            self._compile_expression(elem)

        elif isinstance(node, ObjectExpression):
            for prop in node.properties:
                # Key: a name, or an expression if computed ({[expr]: value})
                if isinstance(prop.key, Identifier) and not prop.computed:
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
                        "+": OpCode.ADD,
                        "-": OpCode.SUB,
                        "*": OpCode.MUL,
                        "/": OpCode.DIV,
                        "%": OpCode.MOD,
                        "&": OpCode.BAND,
                        "|": OpCode.BOR,
                        "^": OpCode.BXOR,
                        "<<": OpCode.SHL,
                        ">>": OpCode.SHR,
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
            # Handle chained member access iteratively to avoid deep recursion
            # e.g., a[0][0][0][0] creates a chain of MemberExpression nodes
            access_chain = []
            current = node

            # Collect the chain of member accesses
            while isinstance(current, MemberExpression):
                access_chain.append((current.computed, current.property))
                current = current.object

            # Compile the base object
            self._compile_expression(current)

            # Apply each member access in order (chain is reversed)
            for computed, prop in reversed(access_chain):
                if computed:
                    self._compile_expression(prop)
                else:
                    idx = self._add_constant(prop.name)
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
            func = self._compile_function(
                name, node.params, node.body, is_expression=True
            )
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
            raise NotImplementedError(
                f"Cannot compile expression: {type(node).__name__}"
            )
