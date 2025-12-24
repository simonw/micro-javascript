"""Virtual machine for executing JavaScript bytecode."""

import math
import time
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass

from .opcodes import OpCode
from .compiler import CompiledFunction
from .values import (
    UNDEFINED, NULL, JSUndefined, JSNull, JSValue,
    JSObject, JSArray, JSFunction, JSRegExp,
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
    is_constructor_call: bool = False  # True if this frame is from a "new" call
    new_target: JSValue = None  # The new object for constructor calls


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


class ForOfIterator:
    """Iterator for for-of loops."""
    def __init__(self, values: List):
        self.values = values
        self.index = 0

    def next(self) -> Tuple[Any, bool]:
        """Return (value, done)."""
        if self.index >= len(self.values):
            return None, True
        value = self.values[self.index]
        self.index += 1
        return value, False


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
                OpCode.BUILD_ARRAY, OpCode.BUILD_OBJECT, OpCode.BUILD_REGEX,
                OpCode.MAKE_CLOSURE, OpCode.TYPEOF_NAME,
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

        elif op == OpCode.DUP2:
            # Duplicate top two items: a, b -> a, b, a, b
            self.stack.append(self.stack[-2])
            self.stack.append(self.stack[-2])

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

        elif op == OpCode.ROT4:
            # Rotate 4 items: a, b, c, d -> b, c, d, a
            a = self.stack[-4]
            b = self.stack[-3]
            c = self.stack[-2]
            d = self.stack[-1]
            self.stack[-4] = b
            self.stack[-3] = c
            self.stack[-2] = d
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
            # Set prototype from Array constructor
            array_constructor = self.globals.get("Array")
            if array_constructor and hasattr(array_constructor, '_prototype'):
                arr._prototype = array_constructor._prototype
            self.stack.append(arr)

        elif op == OpCode.BUILD_OBJECT:
            obj = JSObject()
            # Set prototype from Object constructor
            object_constructor = self.globals.get("Object")
            if object_constructor and hasattr(object_constructor, '_prototype'):
                obj._prototype = object_constructor._prototype
            props = []
            for _ in range(arg):
                value = self.stack.pop()
                kind = self.stack.pop()
                key = self.stack.pop()
                props.insert(0, (key, kind, value))
            for key, kind, value in props:
                key_str = to_string(key) if not isinstance(key, str) else key
                if kind == "get":
                    obj.define_getter(key_str, value)
                elif kind == "set":
                    obj.define_setter(key_str, value)
                elif key_str == "__proto__" and kind == "init":
                    # __proto__ in object literal sets the prototype
                    if value is NULL or value is None:
                        obj._prototype = None
                    elif isinstance(value, JSObject):
                        obj._prototype = value
                else:
                    obj.set(key_str, value)
            self.stack.append(obj)

        elif op == OpCode.BUILD_REGEX:
            pattern, flags = frame.func.constants[arg]
            regex = JSRegExp(pattern, flags)
            self.stack.append(regex)

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
            a_num = float(self._to_number(a))  # Use float for proper -0 handling
            b_num = float(self._to_number(b))
            self.stack.append(a_num * b_num)

        elif op == OpCode.DIV:
            b = self.stack.pop()
            a = self.stack.pop()
            b_num = to_number(b)
            a_num = to_number(a)
            if b_num == 0:
                # Check sign of zero using copysign
                b_sign = math.copysign(1, b_num)
                if a_num == 0:
                    self.stack.append(float('nan'))
                elif (a_num > 0) == (b_sign > 0):  # Same sign
                    self.stack.append(float('inf'))
                else:  # Different signs
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
            n = to_number(a)
            # Ensure -0 produces -0.0 (float)
            if n == 0:
                self.stack.append(-0.0 if math.copysign(1, n) > 0 else 0.0)
            else:
                self.stack.append(-n)

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
            result = self._to_int32(a) << shift
            # Convert result back to signed 32-bit
            result = result & 0xFFFFFFFF
            if result >= 0x80000000:
                result -= 0x100000000
            self.stack.append(result)

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

        elif op == OpCode.TYPEOF_NAME:
            # Special typeof that returns "undefined" for undeclared variables
            name = frame.func.constants[arg]
            if name in self.globals:
                self.stack.append(js_typeof(self.globals[name]))
            else:
                self.stack.append("undefined")

        elif op == OpCode.INSTANCEOF:
            constructor = self.stack.pop()
            obj = self.stack.pop()
            # Check if constructor is callable
            if not (isinstance(constructor, JSFunction) or
                    (isinstance(constructor, JSObject) and hasattr(constructor, '_call_fn'))):
                raise JSTypeError("Right-hand side of instanceof is not callable")

            # Check prototype chain
            if not isinstance(obj, JSObject):
                self.stack.append(False)
            else:
                # Get constructor's prototype property
                if isinstance(constructor, JSFunction) and hasattr(constructor, '_prototype'):
                    proto = constructor._prototype
                elif isinstance(constructor, JSObject) and hasattr(constructor, '_prototype'):
                    proto = constructor._prototype
                else:
                    proto = constructor.get("prototype") if isinstance(constructor, JSObject) else None

                # Walk the prototype chain
                result = False
                current = getattr(obj, '_prototype', None)
                while current is not None:
                    if current is proto:
                        result = True
                        break
                    current = getattr(current, '_prototype', None)
                self.stack.append(result)

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
            popped_frame = self.call_stack.pop()
            # For constructor calls, return the new object unless result is an object
            if popped_frame.is_constructor_call:
                if not isinstance(result, JSObject):
                    result = popped_frame.new_target
            self.stack.append(result)

        elif op == OpCode.RETURN_UNDEFINED:
            popped_frame = self.call_stack.pop()
            # For constructor calls, return the new object
            if popped_frame.is_constructor_call:
                self.stack.append(popped_frame.new_target)
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

        elif op == OpCode.FOR_OF_INIT:
            iterable = self.stack.pop()
            if iterable is UNDEFINED or iterable is NULL:
                values = []
            elif isinstance(iterable, JSArray):
                values = list(iterable._elements)
            elif isinstance(iterable, str):
                # Strings iterate over characters
                values = list(iterable)
            elif isinstance(iterable, list):
                values = list(iterable)
            else:
                values = []
            self.stack.append(ForOfIterator(values))

        elif op == OpCode.FOR_OF_NEXT:
            iterator = self.stack[-1]
            if isinstance(iterator, ForOfIterator):
                value, done = iterator.next()
                if done:
                    self.stack.append(True)
                else:
                    self.stack.append(value)
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

                # Create prototype object for the function
                # In JavaScript, every function has a prototype property
                prototype = JSObject()
                prototype.set("constructor", js_func)
                js_func._prototype = prototype

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

    def _to_primitive(self, value: JSValue, hint: str = "default") -> JSValue:
        """Convert an object to a primitive value (ToPrimitive).

        hint can be "default", "number", or "string"
        """
        if not isinstance(value, JSObject):
            return value

        # For default hint, try valueOf first (like number), then toString
        if hint == "string":
            method_order = ["toString", "valueOf"]
        else:  # default or number
            method_order = ["valueOf", "toString"]

        for method_name in method_order:
            method = value.get(method_name)
            if method is UNDEFINED or method is NULL:
                continue
            if isinstance(method, JSFunction):
                result = self._call_callback(method, [], value)
                if not isinstance(result, JSObject):
                    return result
            elif callable(method):
                result = method()
                if not isinstance(result, JSObject):
                    return result

        # If we get here, conversion failed
        raise JSTypeError("Cannot convert object to primitive value")

    def _to_number(self, value: JSValue) -> Union[int, float]:
        """Convert to number, with ToPrimitive for objects."""
        if isinstance(value, JSObject):
            value = self._to_primitive(value, "number")
        return to_number(value)

    def _add(self, a: JSValue, b: JSValue) -> JSValue:
        """JavaScript + operator."""
        # First convert objects to primitives
        if isinstance(a, JSObject):
            a = self._to_primitive(a, "default")
        if isinstance(b, JSObject):
            b = self._to_primitive(b, "default")

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
            array_methods = [
                "push", "pop", "shift", "unshift", "toString", "join",
                "map", "filter", "reduce", "forEach", "indexOf", "lastIndexOf",
                "find", "findIndex", "some", "every", "concat", "slice",
                "reverse", "includes",
            ]
            if key_str in array_methods:
                return self._make_array_method(obj, key_str)
            return obj.get(key_str)

        if isinstance(obj, JSRegExp):
            # RegExp methods and properties
            if key_str in ("test", "exec"):
                return self._make_regexp_method(obj, key_str)
            # RegExp properties
            if key_str in ("source", "flags", "global", "ignoreCase", "multiline",
                          "dotAll", "unicode", "sticky", "lastIndex"):
                return obj.get(key_str)
            return UNDEFINED

        if isinstance(obj, JSFunction):
            # Function methods
            if key_str in ("bind", "call", "apply", "toString"):
                return self._make_function_method(obj, key_str)
            if key_str == "length":
                return len(obj.params)
            if key_str == "name":
                return obj.name
            if key_str == "prototype":
                return getattr(obj, '_prototype', UNDEFINED) or UNDEFINED
            return UNDEFINED

        if isinstance(obj, JSObject):
            # Check for getter first
            getter = obj.get_getter(key_str)
            if getter is not None:
                return self._invoke_getter(getter, obj)
            # Check own property
            if obj.has(key_str):
                return obj.get(key_str)
            # Check prototype chain
            proto = getattr(obj, '_prototype', None)
            while proto is not None:
                if isinstance(proto, JSObject) and proto.has(key_str):
                    return proto.get(key_str)
                proto = getattr(proto, '_prototype', None)
            # Built-in Object methods as fallback
            if key_str in ("toString", "hasOwnProperty"):
                return self._make_object_method(obj, key_str)
            return UNDEFINED

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
                "includes", "replace", "match", "search", "toString",
            ]
            if key_str in string_methods:
                return self._make_string_method(obj, key_str)
            return UNDEFINED

        if isinstance(obj, (int, float)):
            # Number methods
            if key_str in ("toFixed", "toString"):
                return self._make_number_method(obj, key_str)
            return UNDEFINED

        # Python callable (including JSBoundMethod)
        if callable(obj):
            if key_str in ("call", "apply", "bind"):
                return self._make_callable_method(obj, key_str)
            return UNDEFINED

        return UNDEFINED

    def _make_array_method(self, arr: JSArray, method: str) -> Any:
        """Create a bound array method."""
        vm = self  # Reference for closures

        def push_fn(*args):
            for arg in args:
                arr.push(arg)
            return arr.length

        def pop_fn(*args):
            return arr.pop()

        def shift_fn(*args):
            if not arr._elements:
                return UNDEFINED
            return arr._elements.pop(0)

        def unshift_fn(*args):
            for i, arg in enumerate(args):
                arr._elements.insert(i, arg)
            return arr.length

        def toString_fn(*args):
            return ",".join(to_string(elem) for elem in arr._elements)

        def join_fn(*args):
            sep = "," if not args else to_string(args[0])
            return sep.join(to_string(elem) for elem in arr._elements)

        def map_fn(*args):
            callback = args[0] if args else None
            if not callback:
                return JSArray()
            result = JSArray()
            result._elements = []
            for i, elem in enumerate(arr._elements):
                val = vm._call_callback(callback, [elem, i, arr])
                result._elements.append(val)
            return result

        def filter_fn(*args):
            callback = args[0] if args else None
            if not callback:
                return JSArray()
            result = JSArray()
            result._elements = []
            for i, elem in enumerate(arr._elements):
                val = vm._call_callback(callback, [elem, i, arr])
                if to_boolean(val):
                    result._elements.append(elem)
            return result

        def reduce_fn(*args):
            callback = args[0] if args else None
            initial = args[1] if len(args) > 1 else UNDEFINED
            if not callback:
                raise JSTypeError("reduce callback is not a function")
            acc = initial
            start_idx = 0
            if acc is UNDEFINED:
                if not arr._elements:
                    raise JSTypeError("Reduce of empty array with no initial value")
                acc = arr._elements[0]
                start_idx = 1
            for i in range(start_idx, len(arr._elements)):
                elem = arr._elements[i]
                acc = vm._call_callback(callback, [acc, elem, i, arr])
            return acc

        def forEach_fn(*args):
            callback = args[0] if args else None
            if not callback:
                return UNDEFINED
            for i, elem in enumerate(arr._elements):
                vm._call_callback(callback, [elem, i, arr])
            return UNDEFINED

        def indexOf_fn(*args):
            search = args[0] if args else UNDEFINED
            start = int(to_number(args[1])) if len(args) > 1 else 0
            if start < 0:
                start = max(0, len(arr._elements) + start)
            for i in range(start, len(arr._elements)):
                if vm._strict_equals(arr._elements[i], search):
                    return i
            return -1

        def lastIndexOf_fn(*args):
            search = args[0] if args else UNDEFINED
            start = int(to_number(args[1])) if len(args) > 1 else len(arr._elements) - 1
            if start < 0:
                start = len(arr._elements) + start
            for i in range(min(start, len(arr._elements) - 1), -1, -1):
                if vm._strict_equals(arr._elements[i], search):
                    return i
            return -1

        def find_fn(*args):
            callback = args[0] if args else None
            if not callback:
                return UNDEFINED
            for i, elem in enumerate(arr._elements):
                val = vm._call_callback(callback, [elem, i, arr])
                if to_boolean(val):
                    return elem
            return UNDEFINED

        def findIndex_fn(*args):
            callback = args[0] if args else None
            if not callback:
                return -1
            for i, elem in enumerate(arr._elements):
                val = vm._call_callback(callback, [elem, i, arr])
                if to_boolean(val):
                    return i
            return -1

        def some_fn(*args):
            callback = args[0] if args else None
            if not callback:
                return False
            for i, elem in enumerate(arr._elements):
                val = vm._call_callback(callback, [elem, i, arr])
                if to_boolean(val):
                    return True
            return False

        def every_fn(*args):
            callback = args[0] if args else None
            if not callback:
                return True
            for i, elem in enumerate(arr._elements):
                val = vm._call_callback(callback, [elem, i, arr])
                if not to_boolean(val):
                    return False
            return True

        def concat_fn(*args):
            result = JSArray()
            result._elements = arr._elements[:]
            for arg in args:
                if isinstance(arg, JSArray):
                    result._elements.extend(arg._elements)
                else:
                    result._elements.append(arg)
            return result

        def slice_fn(*args):
            start = int(to_number(args[0])) if args else 0
            end = int(to_number(args[1])) if len(args) > 1 else len(arr._elements)
            if start < 0:
                start = max(0, len(arr._elements) + start)
            if end < 0:
                end = max(0, len(arr._elements) + end)
            result = JSArray()
            result._elements = arr._elements[start:end]
            return result

        def reverse_fn(*args):
            arr._elements.reverse()
            return arr

        def includes_fn(*args):
            search = args[0] if args else UNDEFINED
            start = int(to_number(args[1])) if len(args) > 1 else 0
            if start < 0:
                start = max(0, len(arr._elements) + start)
            for i in range(start, len(arr._elements)):
                if vm._strict_equals(arr._elements[i], search):
                    return True
            return False

        methods = {
            "push": push_fn,
            "pop": pop_fn,
            "shift": shift_fn,
            "unshift": unshift_fn,
            "toString": toString_fn,
            "join": join_fn,
            "map": map_fn,
            "filter": filter_fn,
            "reduce": reduce_fn,
            "forEach": forEach_fn,
            "indexOf": indexOf_fn,
            "lastIndexOf": lastIndexOf_fn,
            "find": find_fn,
            "findIndex": findIndex_fn,
            "some": some_fn,
            "every": every_fn,
            "concat": concat_fn,
            "slice": slice_fn,
            "reverse": reverse_fn,
            "includes": includes_fn,
        }
        return methods.get(method, lambda *args: UNDEFINED)

    def _make_object_method(self, obj: JSObject, method: str) -> Any:
        """Create a bound object method."""
        def toString_fn(*args):
            return "[object Object]"

        def hasOwnProperty_fn(*args):
            key = to_string(args[0]) if args else ""
            return obj.has(key)

        methods = {
            "toString": toString_fn,
            "hasOwnProperty": hasOwnProperty_fn,
        }
        return methods.get(method, lambda *args: UNDEFINED)

    def _make_function_method(self, func: JSFunction, method: str) -> Any:
        """Create a bound function method (bind, call, apply)."""
        vm = self  # Reference for closures

        def bind_fn(*args):
            """Create a bound function with fixed this and optional partial args."""
            bound_this = args[0] if args else UNDEFINED
            bound_args = list(args[1:]) if len(args) > 1 else []

            # Create a new function that wraps the original
            bound_func = JSFunction(
                name=func.name,
                params=func.params[len(bound_args):],  # Remaining params after bound args
                bytecode=func.bytecode,
            )
            # Copy compiled function reference
            if hasattr(func, '_compiled'):
                bound_func._compiled = func._compiled
            # Copy closure cells
            if hasattr(func, '_closure_cells'):
                bound_func._closure_cells = func._closure_cells
            # Store binding info on the function
            bound_func._bound_this = bound_this
            bound_func._bound_args = bound_args
            bound_func._original_func = func
            return bound_func

        def call_fn(*args):
            """Call function with explicit this and individual arguments."""
            this_val = args[0] if args else UNDEFINED
            call_args = list(args[1:]) if len(args) > 1 else []

            # Call the function with the specified this
            return vm._call_function_internal(func, this_val, call_args)

        def apply_fn(*args):
            """Call function with explicit this and array of arguments."""
            this_val = args[0] if args else UNDEFINED
            arg_array = args[1] if len(args) > 1 and args[1] is not NULL else None

            # Convert array argument to list
            if arg_array is None:
                apply_args = []
            elif isinstance(arg_array, JSArray):
                apply_args = arg_array._elements[:]
            elif isinstance(arg_array, (list, tuple)):
                apply_args = list(arg_array)
            else:
                apply_args = []

            return vm._call_function_internal(func, this_val, apply_args)

        def toString_fn(*args):
            return f"function {func.name}() {{ [native code] }}"

        methods = {
            "bind": bind_fn,
            "call": call_fn,
            "apply": apply_fn,
            "toString": toString_fn,
        }
        return methods.get(method, lambda *args: UNDEFINED)

    def _make_callable_method(self, fn: Any, method: str) -> Any:
        """Create a method for Python callables (including JSBoundMethod)."""
        from .values import JSBoundMethod

        def call_fn(*args):
            """Call with explicit this and individual arguments."""
            this_val = args[0] if args else UNDEFINED
            call_args = list(args[1:]) if len(args) > 1 else []
            # JSBoundMethod expects this as first arg
            if isinstance(fn, JSBoundMethod):
                return fn(this_val, *call_args)
            # Regular Python callable doesn't use this
            return fn(*call_args)

        def apply_fn(*args):
            """Call with explicit this and array of arguments."""
            this_val = args[0] if args else UNDEFINED
            arg_array = args[1] if len(args) > 1 and args[1] is not NULL else None

            if arg_array is None:
                apply_args = []
            elif isinstance(arg_array, JSArray):
                apply_args = arg_array._elements[:]
            elif isinstance(arg_array, (list, tuple)):
                apply_args = list(arg_array)
            else:
                apply_args = []

            if isinstance(fn, JSBoundMethod):
                return fn(this_val, *apply_args)
            return fn(*apply_args)

        def bind_fn(*args):
            """Create a bound function with fixed this."""
            bound_this = args[0] if args else UNDEFINED
            bound_args = list(args[1:]) if len(args) > 1 else []

            if isinstance(fn, JSBoundMethod):
                def bound(*call_args):
                    return fn(bound_this, *bound_args, *call_args)
            else:
                def bound(*call_args):
                    return fn(*bound_args, *call_args)
            return bound

        methods = {
            "call": call_fn,
            "apply": apply_fn,
            "bind": bind_fn,
        }
        return methods.get(method, lambda *args: UNDEFINED)

    def _call_function_internal(
        self, func: JSFunction, this_val: JSValue, args: List[JSValue]
    ) -> JSValue:
        """Internal method to call a function with explicit this and args."""
        # Handle bound functions
        if hasattr(func, '_bound_this'):
            this_val = func._bound_this
        if hasattr(func, '_bound_args'):
            args = list(func._bound_args) + list(args)
        if hasattr(func, '_original_func'):
            func = func._original_func

        # Use existing invoke mechanism
        self._invoke_js_function(func, args, this_val)
        result = self._execute()
        return result

    def _make_regexp_method(self, re: JSRegExp, method: str) -> Any:
        """Create a bound RegExp method."""
        def test_fn(*args):
            string = to_string(args[0]) if args else ""
            return re.test(string)

        def exec_fn(*args):
            string = to_string(args[0]) if args else ""
            return re.exec(string)

        methods = {
            "test": test_fn,
            "exec": exec_fn,
        }
        return methods.get(method, lambda *args: UNDEFINED)

    def _make_number_method(self, n: float, method: str) -> Any:
        """Create a bound number method."""
        def toFixed(*args):
            digits = int(to_number(args[0])) if args else 0
            if digits < 0 or digits > 100:
                raise JSReferenceError("toFixed() digits out of range")
            return f"{n:.{digits}f}"

        def toString(*args):
            radix = int(to_number(args[0])) if args else 10
            if radix < 2 or radix > 36:
                raise JSReferenceError("toString() radix must be between 2 and 36")
            if radix == 10:
                if isinstance(n, float) and n.is_integer():
                    return str(int(n))
                return str(n)
            # Convert to different base
            if n < 0:
                return "-" + self._number_to_base(-n, radix)
            return self._number_to_base(n, radix)

        methods = {
            "toFixed": toFixed,
            "toString": toString,
        }
        return methods.get(method, lambda *args: UNDEFINED)

    def _number_to_base(self, n: float, radix: int) -> str:
        """Convert number to string in given base."""
        if n != int(n):
            # For non-integers, just use base 10
            return str(n)
        n = int(n)
        if n == 0:
            return "0"
        digits = "0123456789abcdefghijklmnopqrstuvwxyz"
        result = []
        while n:
            result.append(digits[n % radix])
            n //= radix
        return "".join(reversed(result))

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
            sep = args[0] if args else UNDEFINED
            limit = int(to_number(args[1])) if len(args) > 1 else -1

            if sep is UNDEFINED:
                parts = [s]
            elif isinstance(sep, JSRegExp):
                # Split with regex
                import re
                flags = 0
                if "i" in sep._flags:
                    flags |= re.IGNORECASE
                if "m" in sep._flags:
                    flags |= re.MULTILINE
                pattern = re.compile(sep._pattern, flags)
                # Python split includes groups, which matches JS behavior
                parts = pattern.split(s)
            elif to_string(sep) == "":
                parts = list(s)
            else:
                parts = s.split(to_string(sep))

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
            pattern = args[0] if args else ""
            replacement = to_string(args[1]) if len(args) > 1 else "undefined"

            if isinstance(pattern, JSRegExp):
                # Replace with regex
                import re
                flags = 0
                if "i" in pattern._flags:
                    flags |= re.IGNORECASE
                if "m" in pattern._flags:
                    flags |= re.MULTILINE
                regex = re.compile(pattern._pattern, flags)

                # Handle special replacement patterns
                def handle_replacement(m):
                    result = replacement
                    # $& - the matched substring
                    result = result.replace("$&", m.group(0))
                    # $` - portion before match (not commonly used, skip for now)
                    # $' - portion after match (not commonly used, skip for now)
                    # $n - nth captured group
                    for i in range(1, 10):
                        if m.lastindex and i <= m.lastindex:
                            result = result.replace(f"${i}", m.group(i) or "")
                        else:
                            result = result.replace(f"${i}", "")
                    return result

                if "g" in pattern._flags:
                    return regex.sub(handle_replacement, s)
                else:
                    return regex.sub(handle_replacement, s, count=1)
            else:
                # String replace - only replace first occurrence
                search = to_string(pattern)
                return s.replace(search, replacement, 1)

        def match(*args):
            pattern = args[0] if args else None
            if pattern is None:
                # Match empty string
                arr = JSArray()
                arr._elements = [""]
                arr.set("index", 0)
                arr.set("input", s)
                return arr

            import re
            if isinstance(pattern, JSRegExp):
                flags = 0
                if "i" in pattern._flags:
                    flags |= re.IGNORECASE
                if "m" in pattern._flags:
                    flags |= re.MULTILINE
                regex = re.compile(pattern._pattern, flags)
                is_global = "g" in pattern._flags
            else:
                # Convert string to regex
                regex = re.compile(to_string(pattern))
                is_global = False

            if is_global:
                # Global flag: return all matches without groups
                matches = [m.group(0) for m in regex.finditer(s)]
                if not matches:
                    return NULL
                arr = JSArray()
                arr._elements = list(matches)
                return arr
            else:
                # Non-global: return first match with groups
                m = regex.search(s)
                if m is None:
                    return NULL
                arr = JSArray()
                arr._elements = [m.group(0)]
                # Add captured groups
                for i in range(1, len(m.groups()) + 1):
                    arr._elements.append(m.group(i))
                arr.set("index", m.start())
                arr.set("input", s)
                return arr

        def search(*args):
            pattern = args[0] if args else None
            if pattern is None:
                return 0  # Match empty string at start

            import re
            if isinstance(pattern, JSRegExp):
                flags = 0
                if "i" in pattern._flags:
                    flags |= re.IGNORECASE
                if "m" in pattern._flags:
                    flags |= re.MULTILINE
                regex = re.compile(pattern._pattern, flags)
            else:
                # Convert string to regex
                regex = re.compile(to_string(pattern))

            m = regex.search(s)
            return m.start() if m else -1

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
            "match": match,
            "search": search,
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
            # Check for setter
            setter = obj.get_setter(key_str)
            if setter is not None:
                self._invoke_setter(setter, obj, value)
            else:
                obj.set(key_str, value)

    def _delete_property(self, obj: JSValue, key: JSValue) -> bool:
        """Delete property from object."""
        if isinstance(obj, JSObject):
            key_str = to_string(key) if not isinstance(key, str) else key
            return obj.delete(key_str)
        return False

    def _invoke_getter(self, getter: Any, this_val: JSValue) -> JSValue:
        """Invoke a getter function and return its result."""
        if isinstance(getter, JSFunction):
            # Use synchronous execution (like _call_callback)
            return self._call_callback(getter, [], this_val)
        elif callable(getter):
            return getter()
        return UNDEFINED

    def _invoke_setter(self, setter: Any, this_val: JSValue, value: JSValue) -> None:
        """Invoke a setter function."""
        if isinstance(setter, JSFunction):
            # Use synchronous execution (like _call_callback)
            self._call_callback(setter, [value], this_val)
        elif callable(setter):
            setter(value)

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
        from .values import JSBoundMethod
        if isinstance(method, JSFunction):
            self._invoke_js_function(method, args, this_val)
        elif isinstance(method, JSBoundMethod):
            # JSBoundMethod expects this_val as first argument
            result = method(this_val, *args)
            self.stack.append(result if result is not None else UNDEFINED)
        elif callable(method):
            result = method(*args)
            self.stack.append(result if result is not None else UNDEFINED)
        else:
            raise JSTypeError(f"{method} is not a function")

    def _call_callback(self, callback: JSValue, args: List[JSValue], this_val: JSValue = None) -> JSValue:
        """Call a callback function synchronously and return the result."""
        if isinstance(callback, JSFunction):
            # Save current stack position AND call stack depth
            stack_len = len(self.stack)
            call_stack_len = len(self.call_stack)

            # Invoke the function
            self._invoke_js_function(callback, args, this_val if this_val is not None else UNDEFINED)

            # Execute until the call returns (back to original call stack depth)
            while len(self.call_stack) > call_stack_len:
                self._check_limits()
                frame = self.call_stack[-1]
                func = frame.func
                bytecode = func.bytecode

                if frame.ip >= len(bytecode):
                    self.call_stack.pop()
                    if len(self.stack) > stack_len:
                        return self.stack.pop()
                    return UNDEFINED

                op = OpCode(bytecode[frame.ip])
                frame.ip += 1

                # Get argument if needed
                arg = None
                if op in (OpCode.JUMP, OpCode.JUMP_IF_FALSE, OpCode.JUMP_IF_TRUE, OpCode.TRY_START):
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
                    OpCode.BUILD_ARRAY, OpCode.BUILD_OBJECT, OpCode.BUILD_REGEX,
                    OpCode.MAKE_CLOSURE,
                ):
                    arg = bytecode[frame.ip]
                    frame.ip += 1

                self._execute_opcode(op, arg, frame)

            # Get result from stack
            if len(self.stack) > stack_len:
                return self.stack.pop()
            return UNDEFINED
        elif callable(callback):
            result = callback(*args)
            return result if result is not None else UNDEFINED
        else:
            raise JSTypeError(f"{callback} is not a function")

    def _invoke_js_function(
        self,
        func: JSFunction,
        args: List[JSValue],
        this_val: JSValue,
        is_constructor: bool = False,
        new_target: JSValue = None,
    ) -> None:
        """Invoke a JavaScript function."""
        # Handle bound functions
        if hasattr(func, '_bound_this'):
            this_val = func._bound_this
        if hasattr(func, '_bound_args'):
            args = list(func._bound_args) + list(args)
        if hasattr(func, '_original_func'):
            func = func._original_func

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

        # For named function expressions, bind the function name to itself
        # This allows recursive calls like: var f = function fact(n) { return fact(n-1); }
        if compiled.name and compiled.name in compiled.locals:
            name_slot = compiled.locals.index(compiled.name)
            if name_slot >= len(compiled.params) + 1:  # After params and arguments
                locals_list[name_slot] = func

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
            is_constructor_call=is_constructor,
            new_target=new_target,
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
            # Set prototype from constructor's prototype property
            if hasattr(constructor, '_prototype'):
                obj._prototype = constructor._prototype
            # Call constructor with new object as 'this'
            # Mark this as a constructor call so RETURN knows to return the object
            self._invoke_js_function(constructor, args, obj, is_constructor=True, new_target=obj)
            # Don't push obj here - RETURN/RETURN_UNDEFINED will handle it
        elif isinstance(constructor, JSObject) and hasattr(constructor, '_call_fn'):
            # Built-in constructor (like Object, Array, RegExp)
            result = constructor._call_fn(*args)
            self.stack.append(result)
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
