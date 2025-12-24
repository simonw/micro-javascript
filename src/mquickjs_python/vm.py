"""Virtual machine for executing JavaScript bytecode."""

import math
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from .opcodes import OpCode
from .compiler import CompiledFunction
from .values import (
    UNDEFINED, NULL, JSUndefined, JSNull, JSValue,
    JSObject, JSArray, JSFunction,
    to_boolean, to_number, to_string, js_typeof,
)
from .errors import (
    JSError, JSTypeError, JSReferenceError,
    MemoryLimitError, TimeLimitError,
)


@dataclass
class ClosureCell:
    """A cell for closure variable - allows sharing between scopes."""
    value: JSValue


@dataclass
class CallFrame:
    """Call frame on the call stack."""
    func: CompiledFunction
    ip: int  # Instruction pointer
    bp: int  # Base pointer (stack base for this frame)
    locals: List[JSValue]
    this_value: JSValue
    closure_cells: List[ClosureCell] = None  # Cells for captured variables (from outer function)
    cell_storage: List[ClosureCell] = None  # Cells for variables captured by inner functions


class ForInIterator:
    """Iterator for for-in loops."""
    def __init__(self, keys: List[str]):
        self.keys = keys
        self.index = 0

    def next(self) -> Tuple[Optional[str], bool]:
        """Return (key, done)."""
        if self.index >= len(self.keys):
            return None, True
        key = self.keys[self.index]
        self.index += 1
        return key, False


class VM:
    """JavaScript virtual machine."""

    def __init__(
        self,
        memory_limit: Optional[int] = None,
        time_limit: Optional[float] = None,
    ):
        self.memory_limit = memory_limit
        self.time_limit = time_limit

        self.stack: List[JSValue] = []
        self.call_stack: List[CallFrame] = []
        self.globals: Dict[str, JSValue] = {}

        self.start_time: Optional[float] = None
        self.instruction_count = 0

        # Exception handling
        self.exception: Optional[JSValue] = None
        self.exception_handlers: List[Tuple[int, int]] = []  # (frame_idx, catch_ip)

    def run(self, compiled: CompiledFunction) -> JSValue:
        """Run compiled bytecode and return result."""
        self.start_time = time.time()

        # Create initial call frame
        frame = CallFrame(
            func=compiled,
            ip=0,
            bp=0,
            locals=[UNDEFINED] * compiled.num_locals,
            this_value=UNDEFINED,
        )
        self.call_stack.append(frame)

        try:
            return self._execute()
        except Exception as e:
            raise

    def _check_limits(self) -> None:
        """Check memory and time limits."""
        self.instruction_count += 1

        # Check time limit every 1000 instructions
        if self.time_limit and self.instruction_count % 1000 == 0:
            if time.time() - self.start_time > self.time_limit:
                raise TimeLimitError("Execution timeout")

        # Check memory limit (approximate)
        if self.memory_limit:
            # Rough estimate: 100 bytes per stack item
            mem_used = len(self.stack) * 100 + len(self.call_stack) * 200
            if mem_used > self.memory_limit:
                raise MemoryLimitError("Memory limit exceeded")

    def _execute(self) -> JSValue:
        """Main execution loop."""
        while self.call_stack:
            self._check_limits()

            frame = self.call_stack[-1]
            func = frame.func
            bytecode = func.bytecode

            if frame.ip >= len(bytecode):
                # End of function
                return self.stack.pop() if self.stack else UNDEFINED

            op = OpCode(bytecode[frame.ip])
            frame.ip += 1

            # Get argument if needed
            arg = None
            if op in (OpCode.JUMP, OpCode.JUMP_IF_FALSE, OpCode.JUMP_IF_TRUE, OpCode.TRY_START):
                # 16-bit little-endian argument for jumps
                low = bytecode[frame.ip]
                high = bytecode[frame.ip + 1]
                arg = low | (high << 8)
                frame.ip += 2
            elif op in (
                OpCode.LOAD_CONST, OpCode.LOAD_NAME, OpCode.STORE_NAME,
                OpCode.LOAD_LOCAL, OpCode.STORE_LOCAL,
                OpCode.LOAD_CLOSURE, OpCode.STORE_CLOSURE,
                OpCode.LOAD_CELL, OpCode.STORE_CELL,
                OpCode.CALL, OpCode.CALL_METHOD, OpCode.NEW,
                OpCode.BUILD_ARRAY, OpCode.BUILD_OBJECT,
                OpCode.MAKE_CLOSURE,
            ):
                arg = bytecode[frame.ip]
                frame.ip += 1

            # Execute opcode
            self._execute_opcode(op, arg, frame)

            # Check if frame was popped (return)
            if not self.call_stack:
                break

        return self.stack.pop() if self.stack else UNDEFINED

    def _execute_opcode(self, op: OpCode, arg: Optional[int], frame: CallFrame) -> None:
        """Execute a single opcode."""

        # Stack operations
        if op == OpCode.POP:
            if self.stack:
                self.stack.pop()

        elif op == OpCode.DUP:
            self.stack.append(self.stack[-1])

        elif op == OpCode.SWAP:
            self.stack[-1], self.stack[-2] = self.stack[-2], self.stack[-1]

        elif op == OpCode.ROT3:
            # Rotate 3 items: a, b, c -> b, c, a
            a = self.stack[-3]
            b = self.stack[-2]
            c = self.stack[-1]
            self.stack[-3] = b
            self.stack[-2] = c
            self.stack[-1] = a

        # Constants
        elif op == OpCode.LOAD_CONST:
            self.stack.append(frame.func.constants[arg])

        elif op == OpCode.LOAD_UNDEFINED:
            self.stack.append(UNDEFINED)

        elif op == OpCode.LOAD_NULL:
            self.stack.append(NULL)

        elif op == OpCode.LOAD_TRUE:
            self.stack.append(True)

        elif op == OpCode.LOAD_FALSE:
            self.stack.append(False)

        # Variables
        elif op == OpCode.LOAD_LOCAL:
            self.stack.append(frame.locals[arg])

        elif op == OpCode.STORE_LOCAL:
            frame.locals[arg] = self.stack[-1]

        elif op == OpCode.LOAD_NAME:
            name = frame.func.constants[arg]
            if name in self.globals:
                self.stack.append(self.globals[name])
            else:
                raise JSReferenceError(f"{name} is not defined")

        elif op == OpCode.STORE_NAME:
            name = frame.func.constants[arg]
            self.globals[name] = self.stack[-1]

        elif op == OpCode.LOAD_CLOSURE:
            if frame.closure_cells and arg < len(frame.closure_cells):
                self.stack.append(frame.closure_cells[arg].value)
            else:
                raise JSReferenceError("Closure variable not found")

        elif op == OpCode.STORE_CLOSURE:
            if frame.closure_cells and arg < len(frame.closure_cells):
                frame.closure_cells[arg].value = self.stack[-1]
            else:
                raise JSReferenceError("Closure variable not found")

        elif op == OpCode.LOAD_CELL:
            if frame.cell_storage and arg < len(frame.cell_storage):
                self.stack.append(frame.cell_storage[arg].value)
            else:
                raise JSReferenceError("Cell variable not found")

        elif op == OpCode.STORE_CELL:
            if frame.cell_storage and arg < len(frame.cell_storage):
                frame.cell_storage[arg].value = self.stack[-1]
            else:
                raise JSReferenceError("Cell variable not found")

        # Properties
        elif op == OpCode.GET_PROP:
            key = self.stack.pop()
            obj = self.stack.pop()
            self.stack.append(self._get_property(obj, key))

        elif op == OpCode.SET_PROP:
            value = self.stack.pop()
            key = self.stack.pop()
            obj = self.stack.pop()
            self._set_property(obj, key, value)
            self.stack.append(value)

        elif op == OpCode.DELETE_PROP:
            key = self.stack.pop()
            obj = self.stack.pop()
            result = self._delete_property(obj, key)
            self.stack.append(result)

        # Arrays/Objects
        elif op == OpCode.BUILD_ARRAY:
            elements = []
            for _ in range(arg):
                elements.insert(0, self.stack.pop())
            arr = JSArray()
            arr._elements = elements
            self.stack.append(arr)

        elif op == OpCode.BUILD_OBJECT:
            obj = JSObject()
            pairs = []
            for _ in range(arg):
                value = self.stack.pop()
                key = self.stack.pop()
                pairs.insert(0, (key, value))
            for key, value in pairs:
                key_str = to_string(key) if not isinstance(key, str) else key
                obj.set(key_str, value)
            self.stack.append(obj)

        # Arithmetic
        elif op == OpCode.ADD:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(self._add(a, b))

        elif op == OpCode.SUB:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(to_number(a) - to_number(b))

        elif op == OpCode.MUL:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(to_number(a) * to_number(b))

        elif op == OpCode.DIV:
            b = self.stack.pop()
            a = self.stack.pop()
            b_num = to_number(b)
            a_num = to_number(a)
            if b_num == 0:
                if a_num == 0:
                    self.stack.append(float('nan'))
                elif a_num > 0:
                    self.stack.append(float('inf'))
                else:
                    self.stack.append(float('-inf'))
            else:
                self.stack.append(a_num / b_num)

        elif op == OpCode.MOD:
            b = self.stack.pop()
            a = self.stack.pop()
            b_num = to_number(b)
            a_num = to_number(a)
            if b_num == 0:
                self.stack.append(float('nan'))
            else:
                self.stack.append(a_num % b_num)

        elif op == OpCode.POW:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(to_number(a) ** to_number(b))

        elif op == OpCode.NEG:
            a = self.stack.pop()
            self.stack.append(-to_number(a))

        elif op == OpCode.POS:
            a = self.stack.pop()
            self.stack.append(to_number(a))

        # Bitwise
        elif op == OpCode.BAND:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(self._to_int32(a) & self._to_int32(b))

        elif op == OpCode.BOR:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(self._to_int32(a) | self._to_int32(b))

        elif op == OpCode.BXOR:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(self._to_int32(a) ^ self._to_int32(b))

        elif op == OpCode.BNOT:
            a = self.stack.pop()
            self.stack.append(~self._to_int32(a))

        elif op == OpCode.SHL:
            b = self.stack.pop()
            a = self.stack.pop()
            shift = self._to_uint32(b) & 0x1F
            self.stack.append(self._to_int32(a) << shift)

        elif op == OpCode.SHR:
            b = self.stack.pop()
            a = self.stack.pop()
            shift = self._to_uint32(b) & 0x1F
            self.stack.append(self._to_int32(a) >> shift)

        elif op == OpCode.USHR:
            b = self.stack.pop()
            a = self.stack.pop()
            shift = self._to_uint32(b) & 0x1F
            result = self._to_uint32(a) >> shift
            self.stack.append(result)

        # Comparison
        elif op == OpCode.LT:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(self._compare(a, b) < 0)

        elif op == OpCode.LE:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(self._compare(a, b) <= 0)

        elif op == OpCode.GT:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(self._compare(a, b) > 0)

        elif op == OpCode.GE:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(self._compare(a, b) >= 0)

        elif op == OpCode.EQ:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(self._abstract_equals(a, b))

        elif op == OpCode.NE:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(not self._abstract_equals(a, b))

        elif op == OpCode.SEQ:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(self._strict_equals(a, b))

        elif op == OpCode.SNE:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(not self._strict_equals(a, b))

        # Logical
        elif op == OpCode.NOT:
            a = self.stack.pop()
            self.stack.append(not to_boolean(a))

        # Type operations
        elif op == OpCode.TYPEOF:
            a = self.stack.pop()
            self.stack.append(js_typeof(a))

        elif op == OpCode.INSTANCEOF:
            constructor = self.stack.pop()
            obj = self.stack.pop()
            # Simplified instanceof
            if not isinstance(constructor, JSFunction):
                raise JSTypeError("Right-hand side of instanceof is not callable")
            self.stack.append(isinstance(obj, JSObject))

        elif op == OpCode.IN:
            obj = self.stack.pop()
            key = self.stack.pop()
            if not isinstance(obj, JSObject):
                raise JSTypeError("Cannot use 'in' operator on non-object")
            key_str = to_string(key)
            self.stack.append(obj.has(key_str))

        # Control flow
        elif op == OpCode.JUMP:
            frame.ip = arg

        elif op == OpCode.JUMP_IF_FALSE:
            if not to_boolean(self.stack.pop()):
                frame.ip = arg

        elif op == OpCode.JUMP_IF_TRUE:
            if to_boolean(self.stack.pop()):
                frame.ip = arg

        # Function operations
        elif op == OpCode.CALL:
            self._call_function(arg, None)

        elif op == OpCode.CALL_METHOD:
            # Stack: this, method, arg1, arg2, ...
            # Rearrange: this is before method
            args = []
            for _ in range(arg):
                args.insert(0, self.stack.pop())
            method = self.stack.pop()
            this_val = self.stack.pop()
            self._call_method(method, this_val, args)

        elif op == OpCode.RETURN:
            result = self.stack.pop() if self.stack else UNDEFINED
            self.call_stack.pop()
            if self.call_stack:
                self.stack.append(result)
            else:
                self.stack.append(result)

        elif op == OpCode.RETURN_UNDEFINED:
            self.call_stack.pop()
            if self.call_stack:
                self.stack.append(UNDEFINED)
            else:
                self.stack.append(UNDEFINED)

        # Object operations
        elif op == OpCode.NEW:
            self._new_object(arg)

        elif op == OpCode.THIS:
            self.stack.append(frame.this_value)

        # Exception handling
        elif op == OpCode.THROW:
            exc = self.stack.pop()
            self._throw(exc)

        elif op == OpCode.TRY_START:
            # arg is the catch handler offset
            self.exception_handlers.append((len(self.call_stack) - 1, arg))

        elif op == OpCode.TRY_END:
            if self.exception_handlers:
                self.exception_handlers.pop()

        elif op == OpCode.CATCH:
            # Exception is on stack
            pass

        # Iteration
        elif op == OpCode.FOR_IN_INIT:
            obj = self.stack.pop()
            if obj is UNDEFINED or obj is NULL:
                keys = []
            elif isinstance(obj, JSArray):
                # For arrays, iterate over numeric indices as strings
                keys = [str(i) for i in range(len(obj._elements))]
                # Also include any non-numeric properties
                keys.extend(obj.keys())
            elif isinstance(obj, JSObject):
                keys = obj.keys()
            else:
                keys = []
            self.stack.append(ForInIterator(keys))

        elif op == OpCode.FOR_IN_NEXT:
            iterator = self.stack[-1]
            if isinstance(iterator, ForInIterator):
                key, done = iterator.next()
                if done:
                    self.stack.append(True)
                else:
                    self.stack.append(key)
                    self.stack.append(False)
            else:
                self.stack.append(True)

        # Increment/Decrement
        elif op == OpCode.INC:
            a = self.stack.pop()
            self.stack.append(to_number(a) + 1)

        elif op == OpCode.DEC:
            a = self.stack.pop()
            self.stack.append(to_number(a) - 1)

        # Closures
        elif op == OpCode.MAKE_CLOSURE:
            compiled_func = self.stack.pop()
            if isinstance(compiled_func, CompiledFunction):
                js_func = JSFunction(
                    name=compiled_func.name,
                    params=compiled_func.params,
                    bytecode=compiled_func.bytecode,
                )
                js_func._compiled = compiled_func

                # Capture closure cells for free variables
                if compiled_func.free_vars:
                    closure_cells = []
                    for var_name in compiled_func.free_vars:
                        # First check if it's in our cell_storage (cell var)
                        if frame.cell_storage and var_name in getattr(frame.func, 'cell_vars', []):
                            idx = frame.func.cell_vars.index(var_name)
                            # Share the same cell!
                            closure_cells.append(frame.cell_storage[idx])
                        elif frame.closure_cells and var_name in getattr(frame.func, 'free_vars', []):
                            # Variable is in our own closure
                            idx = frame.func.free_vars.index(var_name)
                            closure_cells.append(frame.closure_cells[idx])
                        elif var_name in frame.func.locals:
                            # Regular local - shouldn't happen if cell_vars is working
                            slot = frame.func.locals.index(var_name)
                            cell = ClosureCell(frame.locals[slot])
                            closure_cells.append(cell)
                        else:
                            closure_cells.append(ClosureCell(UNDEFINED))
                    js_func._closure_cells = closure_cells

                self.stack.append(js_func)
            else:
                self.stack.append(compiled_func)

        else:
            raise NotImplementedError(f"Opcode not implemented: {op.name}")

    def _get_name(self, frame: CallFrame, index: int) -> str:
        """Get a name from the name table."""
        # Names are stored in constants for simplicity
        if index < len(frame.func.constants):
            name = frame.func.constants[index]
            if isinstance(name, str):
                return name
        return f"<name_{index}>"

    def _add(self, a: JSValue, b: JSValue) -> JSValue:
        """JavaScript + operator."""
        # String concatenation if either is string
        if isinstance(a, str) or isinstance(b, str):
            return to_string(a) + to_string(b)
        # Numeric addition
        return to_number(a) + to_number(b)

    def _to_int32(self, value: JSValue) -> int:
        """Convert to 32-bit signed integer."""
        n = to_number(value)
        if math.isnan(n) or math.isinf(n) or n == 0:
            return 0
        n = int(n)
        n = n & 0xFFFFFFFF
        if n >= 0x80000000:
            n -= 0x100000000
        return n

    def _to_uint32(self, value: JSValue) -> int:
        """Convert to 32-bit unsigned integer."""
        n = to_number(value)
        if math.isnan(n) or math.isinf(n) or n == 0:
            return 0
        n = int(n)
        return n & 0xFFFFFFFF

    def _compare(self, a: JSValue, b: JSValue) -> int:
        """Compare two values. Returns -1, 0, or 1."""
        # Handle NaN
        a_num = to_number(a)
        b_num = to_number(b)
        if math.isnan(a_num) or math.isnan(b_num):
            return 1  # NaN comparisons are always false
        if a_num < b_num:
            return -1
        if a_num > b_num:
            return 1
        return 0

    def _strict_equals(self, a: JSValue, b: JSValue) -> bool:
        """JavaScript === operator."""
        # Different types are never equal
        if type(a) != type(b):
            # Special case: int and float
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                return a == b
            return False
        # NaN is not equal to itself
        if isinstance(a, float) and math.isnan(a):
            return False
        # Object identity
        if isinstance(a, JSObject):
            return a is b
        return a == b

    def _abstract_equals(self, a: JSValue, b: JSValue) -> bool:
        """JavaScript == operator."""
        # Same type: use strict equals
        if type(a) == type(b):
            return self._strict_equals(a, b)

        # null == undefined
        if (a is NULL and b is UNDEFINED) or (a is UNDEFINED and b is NULL):
            return True

        # Number comparisons
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return a == b

        # String to number
        if isinstance(a, str) and isinstance(b, (int, float)):
            return to_number(a) == b
        if isinstance(a, (int, float)) and isinstance(b, str):
            return a == to_number(b)

        # Boolean to number
        if isinstance(a, bool):
            return self._abstract_equals(1 if a else 0, b)
        if isinstance(b, bool):
            return self._abstract_equals(a, 1 if b else 0)

        return False

    def _get_property(self, obj: JSValue, key: JSValue) -> JSValue:
        """Get property from object."""
        if obj is UNDEFINED or obj is NULL:
            raise JSTypeError(f"Cannot read property of {obj}")

        key_str = to_string(key) if not isinstance(key, str) else key

        if isinstance(obj, JSArray):
            # Array index access
            try:
                idx = int(key_str)
                if idx >= 0:
                    return obj.get_index(idx)
            except ValueError:
                pass
            if key_str == "length":
                return obj.length
            # Built-in array methods
            if key_str == "push":
                return self._make_array_method(obj, "push")
            if key_str == "pop":
                return self._make_array_method(obj, "pop")
            if key_str == "toString":
                return self._make_array_method(obj, "toString")
            if key_str == "join":
                return self._make_array_method(obj, "join")
            return obj.get(key_str)

        if isinstance(obj, JSObject):
            # Built-in Object methods
            if key_str == "toString":
                return self._make_object_method(obj, "toString")
            return obj.get(key_str)

        if isinstance(obj, str):
            # String character access
            try:
                idx = int(key_str)
                if 0 <= idx < len(obj):
                    return obj[idx]
            except ValueError:
                pass
            if key_str == "length":
                return len(obj)
            # String methods
            string_methods = [
                "charAt", "charCodeAt", "indexOf", "lastIndexOf",
                "substring", "slice", "split", "toLowerCase", "toUpperCase",
                "trim", "concat", "repeat", "startsWith", "endsWith",
                "includes", "replace", "toString",
            ]
            if key_str in string_methods:
                return self._make_string_method(obj, key_str)
            return UNDEFINED

        return UNDEFINED

    def _make_array_method(self, arr: JSArray, method: str) -> Any:
        """Create a bound array method."""
        def push_fn(*args):
            for arg in args:
                arr.push(arg)
            return arr.length

        def pop_fn(*args):
            return arr.pop()

        def toString_fn(*args):
            return ",".join(to_string(elem) for elem in arr._elements)

        def join_fn(*args):
            sep = "," if not args else to_string(args[0])
            return sep.join(to_string(elem) for elem in arr._elements)

        methods = {
            "push": push_fn,
            "pop": pop_fn,
            "toString": toString_fn,
            "join": join_fn,
        }
        return methods.get(method, lambda *args: UNDEFINED)

    def _make_object_method(self, obj: JSObject, method: str) -> Any:
        """Create a bound object method."""
        def toString_fn(*args):
            return "[object Object]"

        methods = {
            "toString": toString_fn,
        }
        return methods.get(method, lambda *args: UNDEFINED)

    def _make_string_method(self, s: str, method: str) -> Any:
        """Create a bound string method."""
        def charAt(*args):
            idx = int(to_number(args[0])) if args else 0
            if 0 <= idx < len(s):
                return s[idx]
            return ""

        def charCodeAt(*args):
            idx = int(to_number(args[0])) if args else 0
            if 0 <= idx < len(s):
                return ord(s[idx])
            return float('nan')

        def indexOf(*args):
            search = to_string(args[0]) if args else ""
            start = int(to_number(args[1])) if len(args) > 1 else 0
            if start < 0:
                start = 0
            return s.find(search, start)

        def lastIndexOf(*args):
            search = to_string(args[0]) if args else ""
            end = int(to_number(args[1])) if len(args) > 1 else len(s)
            # Python's rfind with end position
            return s.rfind(search, 0, end + len(search))

        def substring(*args):
            start = int(to_number(args[0])) if args else 0
            end = int(to_number(args[1])) if len(args) > 1 else len(s)
            # Clamp and swap if needed
            if start < 0:
                start = 0
            if end < 0:
                end = 0
            if start > end:
                start, end = end, start
            return s[start:end]

        def slice_fn(*args):
            start = int(to_number(args[0])) if args else 0
            end = int(to_number(args[1])) if len(args) > 1 else len(s)
            # Handle negative indices
            if start < 0:
                start = max(0, len(s) + start)
            if end < 0:
                end = max(0, len(s) + end)
            return s[start:end]

        def split(*args):
            sep = to_string(args[0]) if args else UNDEFINED
            limit = int(to_number(args[1])) if len(args) > 1 else -1
            if sep is UNDEFINED:
                parts = [s]
            elif sep == "":
                parts = list(s)
            else:
                parts = s.split(sep)
            if limit >= 0:
                parts = parts[:limit]
            arr = JSArray()
            arr._elements = parts
            return arr

        def toLowerCase(*args):
            return s.lower()

        def toUpperCase(*args):
            return s.upper()

        def trim(*args):
            return s.strip()

        def concat(*args):
            result = s
            for arg in args:
                result += to_string(arg)
            return result

        def repeat(*args):
            count = int(to_number(args[0])) if args else 0
            if count < 0:
                raise JSReferenceError("Invalid count value")
            return s * count

        def startsWith(*args):
            search = to_string(args[0]) if args else ""
            pos = int(to_number(args[1])) if len(args) > 1 else 0
            return s[pos:].startswith(search)

        def endsWith(*args):
            search = to_string(args[0]) if args else ""
            length = int(to_number(args[1])) if len(args) > 1 else len(s)
            return s[:length].endswith(search)

        def includes(*args):
            search = to_string(args[0]) if args else ""
            pos = int(to_number(args[1])) if len(args) > 1 else 0
            return search in s[pos:]

        def replace(*args):
            search = to_string(args[0]) if args else ""
            replacement = to_string(args[1]) if len(args) > 1 else "undefined"
            # Only replace first occurrence
            return s.replace(search, replacement, 1)

        def toString(*args):
            return s

        methods = {
            "charAt": charAt,
            "charCodeAt": charCodeAt,
            "indexOf": indexOf,
            "lastIndexOf": lastIndexOf,
            "substring": substring,
            "slice": slice_fn,
            "split": split,
            "toLowerCase": toLowerCase,
            "toUpperCase": toUpperCase,
            "trim": trim,
            "concat": concat,
            "repeat": repeat,
            "startsWith": startsWith,
            "endsWith": endsWith,
            "includes": includes,
            "replace": replace,
            "toString": toString,
        }
        return methods.get(method, lambda *args: UNDEFINED)

    def _set_property(self, obj: JSValue, key: JSValue, value: JSValue) -> None:
        """Set property on object."""
        if obj is UNDEFINED or obj is NULL:
            raise JSTypeError(f"Cannot set property of {obj}")

        key_str = to_string(key) if not isinstance(key, str) else key

        if isinstance(obj, JSArray):
            try:
                idx = int(key_str)
                if idx >= 0:
                    obj.set_index(idx, value)
                    return
            except (ValueError, IndexError):
                pass
            obj.set(key_str, value)
        elif isinstance(obj, JSObject):
            obj.set(key_str, value)

    def _delete_property(self, obj: JSValue, key: JSValue) -> bool:
        """Delete property from object."""
        if isinstance(obj, JSObject):
            key_str = to_string(key) if not isinstance(key, str) else key
            return obj.delete(key_str)
        return False

    def _call_function(self, arg_count: int, this_val: Optional[JSValue]) -> None:
        """Call a function."""
        args = []
        for _ in range(arg_count):
            args.insert(0, self.stack.pop())
        callee = self.stack.pop()

        if isinstance(callee, JSFunction):
            self._invoke_js_function(callee, args, this_val or UNDEFINED)
        elif callable(callee):
            # Native function
            result = callee(*args)
            self.stack.append(result if result is not None else UNDEFINED)
        else:
            raise JSTypeError(f"{callee} is not a function")

    def _call_method(self, method: JSValue, this_val: JSValue, args: List[JSValue]) -> None:
        """Call a method."""
        if isinstance(method, JSFunction):
            self._invoke_js_function(method, args, this_val)
        elif callable(method):
            result = method(*args)
            self.stack.append(result if result is not None else UNDEFINED)
        else:
            raise JSTypeError(f"{method} is not a function")

    def _invoke_js_function(
        self,
        func: JSFunction,
        args: List[JSValue],
        this_val: JSValue,
    ) -> None:
        """Invoke a JavaScript function."""
        compiled = getattr(func, '_compiled', None)
        if compiled is None:
            raise JSTypeError("Function has no bytecode")

        # Prepare locals (parameters + arguments + local variables)
        locals_list = [UNDEFINED] * compiled.num_locals
        for i, arg in enumerate(args):
            if i < len(compiled.params):
                locals_list[i] = arg

        # Create 'arguments' object (stored after params in locals)
        # The 'arguments' slot is at index len(compiled.params)
        arguments_slot = len(compiled.params)
        if arguments_slot < compiled.num_locals:
            arguments_obj = JSArray()
            arguments_obj._elements = list(args)
            locals_list[arguments_slot] = arguments_obj

        # Get closure cells from the function
        closure_cells = getattr(func, '_closure_cells', None)

        # Create cell storage for variables that will be captured by inner functions
        cell_storage = None
        if compiled.cell_vars:
            cell_storage = []
            for var_name in compiled.cell_vars:
                # Find the initial value from locals
                if var_name in compiled.locals:
                    slot = compiled.locals.index(var_name)
                    cell_storage.append(ClosureCell(locals_list[slot]))
                else:
                    cell_storage.append(ClosureCell(UNDEFINED))

        # Create new call frame
        frame = CallFrame(
            func=compiled,
            ip=0,
            bp=len(self.stack),
            locals=locals_list,
            this_value=this_val,
            closure_cells=closure_cells,
            cell_storage=cell_storage,
        )
        self.call_stack.append(frame)

    def _new_object(self, arg_count: int) -> None:
        """Create a new object with constructor."""
        args = []
        for _ in range(arg_count):
            args.insert(0, self.stack.pop())
        constructor = self.stack.pop()

        if isinstance(constructor, JSFunction):
            # Create new object
            obj = JSObject()
            # Call constructor with new object as 'this'
            self._invoke_js_function(constructor, args, obj)
            # Result is the new object (or returned value if object)
            self.stack.append(obj)
        else:
            raise JSTypeError(f"{constructor} is not a constructor")

    def _throw(self, exc: JSValue) -> None:
        """Throw an exception."""
        if self.exception_handlers:
            frame_idx, catch_ip = self.exception_handlers.pop()

            # Unwind call stack
            while len(self.call_stack) > frame_idx + 1:
                self.call_stack.pop()

            # Jump to catch handler
            frame = self.call_stack[-1]
            frame.ip = catch_ip

            # Push exception value
            self.stack.append(exc)
        else:
            # Uncaught exception
            if isinstance(exc, str):
                raise JSError(exc)
            elif isinstance(exc, JSObject):
                msg = exc.get("message")
                raise JSError(to_string(msg) if msg else "Error")
            else:
                raise JSError(to_string(exc))
