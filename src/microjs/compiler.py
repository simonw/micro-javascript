"""Bytecode compiler - compiles AST to bytecode."""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from .ast_nodes import (
    Node, Program, NumericLiteral, StringLiteral, BooleanLiteral, NullLiteral,
    Identifier, ThisExpression, ArrayExpression, ObjectExpression, Property,
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


@dataclass
class LoopContext:
    """Context for loops (for break/continue)."""
    break_jumps: List[int] = field(default_factory=list)
    continue_jumps: List[int] = field(default_factory=list)
    label: Optional[str] = None


class Compiler:
    """Compiles AST to bytecode."""

    def __init__(self):
        self.bytecode: List[int] = []
        self.constants: List[Any] = []
        self.names: List[str] = []
        self.locals: List[str] = []
        self.loop_stack: List[LoopContext] = []
        self.functions: List[CompiledFunction] = []

    def compile(self, node: Program) -> CompiledFunction:
        """Compile a program to bytecode."""
        for stmt in node.body:
            self._compile_statement(stmt)

        # Implicit return undefined
        self._emit(OpCode.LOAD_UNDEFINED)
        self._emit(OpCode.RETURN)

        return CompiledFunction(
            name="<program>",
            params=[],
            bytecode=bytes(self.bytecode),
            constants=self.constants,
            locals=self.locals,
            num_locals=len(self.locals),
        )

    def _emit(self, opcode: OpCode, arg: Optional[int] = None) -> int:
        """Emit an opcode, return its position."""
        pos = len(self.bytecode)
        self.bytecode.append(opcode)
        if arg is not None:
            self.bytecode.append(arg)
        return pos

    def _emit_jump(self, opcode: OpCode) -> int:
        """Emit a jump instruction, return position for patching."""
        pos = len(self.bytecode)
        self.bytecode.append(opcode)
        self.bytecode.append(0)  # Placeholder
        return pos

    def _patch_jump(self, pos: int) -> None:
        """Patch a jump instruction to jump to current position."""
        offset = len(self.bytecode)
        self.bytecode[pos + 1] = offset

    def _add_constant(self, value: Any) -> int:
        """Add a constant and return its index."""
        if value in self.constants:
            return self.constants.index(value)
        self.constants.append(value)
        return len(self.constants) - 1

    def _add_name(self, name: str) -> int:
        """Add a name and return its index."""
        if name in self.names:
            return self.names.index(name)
        self.names.append(name)
        return len(self.names) - 1

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
                self._add_local(name)
                if decl.init:
                    self._compile_expression(decl.init)
                else:
                    self._emit(OpCode.LOAD_UNDEFINED)
                slot = self._get_local(name)
                self._emit(OpCode.STORE_LOCAL, slot)
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
                self.bytecode[pos + 1] = loop_start

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
                self.bytecode[pos + 1] = continue_target

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
                self.bytecode[pos + 1] = continue_target

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
                self._add_local(name)
                slot = self._get_local(name)
                self._emit(OpCode.STORE_LOCAL, slot)
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

            self._compile_statement(node.body)

            self._emit(OpCode.JUMP, loop_start)
            self._patch_jump(jump_done)
            self._emit(OpCode.POP)  # Pop iterator

            for pos in loop_ctx.break_jumps:
                self._patch_jump(pos)

            self.loop_stack.pop()

        elif isinstance(node, BreakStatement):
            if not self.loop_stack:
                raise SyntaxError("'break' outside of loop")
            ctx = self.loop_stack[-1]
            pos = self._emit_jump(OpCode.JUMP)
            ctx.break_jumps.append(pos)

        elif isinstance(node, ContinueStatement):
            if not self.loop_stack:
                raise SyntaxError("'continue' outside of loop")
            ctx = self.loop_stack[-1]
            pos = self._emit_jump(OpCode.JUMP)
            ctx.continue_jumps.append(pos)

        elif isinstance(node, ReturnStatement):
            if node.argument:
                self._compile_expression(node.argument)
                self._emit(OpCode.RETURN)
            else:
                self._emit(OpCode.RETURN_UNDEFINED)

        elif isinstance(node, ThrowStatement):
            self._compile_expression(node.argument)
            self._emit(OpCode.THROW)

        elif isinstance(node, TryStatement):
            # Try block
            try_start = self._emit_jump(OpCode.TRY_START)

            self._compile_statement(node.block)
            self._emit(OpCode.TRY_END)

            # Jump past catch/finally
            jump_end = self._emit_jump(OpCode.JUMP)

            # Catch handler
            self._patch_jump(try_start)
            if node.handler:
                self._emit(OpCode.CATCH)
                # Store exception in catch variable
                name = node.handler.param.name
                self._add_local(name)
                slot = self._get_local(name)
                self._emit(OpCode.STORE_LOCAL, slot)
                self._emit(OpCode.POP)
                self._compile_statement(node.handler.body)

            self._patch_jump(jump_end)

            # Finally block
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
            loop_ctx = LoopContext()  # For break statements
            self.loop_stack.append(loop_ctx)

            for i, case in enumerate(node.cases):
                case_positions.append(len(self.bytecode))
                for stmt in case.consequent:
                    self._compile_statement(stmt)

            self._patch_jump(jump_end)
            self._emit(OpCode.POP)  # Pop discriminant

            # Patch jumps to case bodies
            for pos, idx in jump_to_body:
                self.bytecode[pos + 1] = case_positions[idx]
            if default_jump:
                pos, idx = default_jump
                self.bytecode[pos + 1] = case_positions[idx]

            # Patch break jumps
            for pos in loop_ctx.break_jumps:
                self._patch_jump(pos)

            self.loop_stack.pop()

        elif isinstance(node, FunctionDeclaration):
            # Compile function and add to locals
            func = self._compile_function(node.id.name, node.params, node.body)
            func_idx = len(self.functions)
            self.functions.append(func)

            const_idx = self._add_constant(func)
            self._emit(OpCode.LOAD_CONST, const_idx)
            self._emit(OpCode.MAKE_CLOSURE, func_idx)

            name = node.id.name
            self._add_local(name)
            slot = self._get_local(name)
            self._emit(OpCode.STORE_LOCAL, slot)
            self._emit(OpCode.POP)

        else:
            raise NotImplementedError(f"Cannot compile statement: {type(node).__name__}")

    def _compile_function(
        self, name: str, params: List[Identifier], body: BlockStatement
    ) -> CompiledFunction:
        """Compile a function."""
        # Save current state
        old_bytecode = self.bytecode
        old_constants = self.constants
        old_locals = self.locals
        old_loop_stack = self.loop_stack

        # New state for function
        self.bytecode = []
        self.constants = []
        self.locals = [p.name for p in params]
        self.loop_stack = []

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
        )

        # Restore state
        self.bytecode = old_bytecode
        self.constants = old_constants
        self.locals = old_locals
        self.loop_stack = old_loop_stack

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

        elif isinstance(node, Identifier):
            name = node.name
            slot = self._get_local(name)
            if slot is not None:
                self._emit(OpCode.LOAD_LOCAL, slot)
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
                # Value
                self._compile_expression(prop.value)
            self._emit(OpCode.BUILD_OBJECT, len(node.properties))

        elif isinstance(node, UnaryExpression):
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
            elif node.operator == "delete":
                # Handle delete specially
                if isinstance(node.argument, MemberExpression):
                    # Recompile as delete operation
                    self._compile_expression(node.argument.object)
                    if node.argument.computed:
                        self._compile_expression(node.argument.property)
                    else:
                        idx = self._add_constant(node.argument.property.name)
                        self._emit(OpCode.LOAD_CONST, idx)
                    self._emit(OpCode.DELETE_PROP)
                else:
                    self._emit(OpCode.LOAD_TRUE)  # delete on non-property returns true
            else:
                raise NotImplementedError(f"Unary operator: {node.operator}")

        elif isinstance(node, UpdateExpression):
            # ++x or x++
            if isinstance(node.argument, Identifier):
                name = node.argument.name
                slot = self._get_local(name)
                if slot is not None:
                    self._emit(OpCode.LOAD_LOCAL, slot)
                    if node.prefix:
                        self._emit(OpCode.INC if node.operator == "++" else OpCode.DEC)
                        self._emit(OpCode.DUP)
                        self._emit(OpCode.STORE_LOCAL, slot)
                        self._emit(OpCode.POP)
                    else:
                        self._emit(OpCode.DUP)
                        self._emit(OpCode.INC if node.operator == "++" else OpCode.DEC)
                        self._emit(OpCode.STORE_LOCAL, slot)
                        self._emit(OpCode.POP)
                else:
                    idx = self._add_name(name)
                    self._emit(OpCode.LOAD_NAME, idx)
                    if node.prefix:
                        self._emit(OpCode.INC if node.operator == "++" else OpCode.DEC)
                        self._emit(OpCode.DUP)
                        self._emit(OpCode.STORE_NAME, idx)
                        self._emit(OpCode.POP)
                    else:
                        self._emit(OpCode.DUP)
                        self._emit(OpCode.INC if node.operator == "++" else OpCode.DEC)
                        self._emit(OpCode.STORE_NAME, idx)
                        self._emit(OpCode.POP)
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
                    # Compound assignment
                    slot = self._get_local(name)
                    if slot is not None:
                        self._emit(OpCode.LOAD_LOCAL, slot)
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
                slot = self._get_local(name)
                if slot is not None:
                    self._emit(OpCode.STORE_LOCAL, slot)
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
            func = self._compile_function(name, node.params, node.body)
            func_idx = len(self.functions)
            self.functions.append(func)

            const_idx = self._add_constant(func)
            self._emit(OpCode.LOAD_CONST, const_idx)
            self._emit(OpCode.MAKE_CLOSURE, func_idx)

        else:
            raise NotImplementedError(f"Cannot compile expression: {type(node).__name__}")
