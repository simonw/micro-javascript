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
class CallFrame:
    """Call frame on the call stack."""
    func: CompiledFunction
    ip: int  # Instruction pointer
    bp: int  # Base pointer (stack base for this frame)
    locals: List[JSValue]
    this_value: JSValue


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
            if op in (
                OpCode.LOAD_CONST, OpCode.LOAD_NAME, OpCode.STORE_NAME,
                OpCode.LOAD_LOCAL, OpCode.STORE_LOCAL,
                OpCode.JUMP, OpCode.JUMP_IF_FALSE, OpCode.JUMP_IF_TRUE,
                OpCode.CALL, OpCode.CALL_METHOD, OpCode.NEW,
                OpCode.BUILD_ARRAY, OpCode.BUILD_OBJECT,
                OpCode.TRY_START, OpCode.MAKE_CLOSURE,
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
            return obj.get(key_str)

        if isinstance(obj, JSObject):
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
            return UNDEFINED

        return UNDEFINED

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

        # Prepare locals (parameters + local variables)
        locals_list = [UNDEFINED] * compiled.num_locals
        for i, arg in enumerate(args):
            if i < len(compiled.params):
                locals_list[i] = arg

        # Create new call frame
        frame = CallFrame(
            func=compiled,
            ip=0,
            bp=len(self.stack),
            locals=locals_list,
            this_value=this_val,
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
