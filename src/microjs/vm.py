"""Virtual machine for executing JavaScript bytecode."""

import math
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field

from .opcodes import OPCODES_WITH_ARG, OpCode
from .compiler import CompiledFunction
from .values import (
    UNDEFINED,
    NULL,
    JSUndefined,
    JSNull,
    JSValue,
    JSObject,
    JSArray,
    JSFunction,
    JSRegExp,
    JSTypedArray,
    JSArrayBuffer,
    to_boolean,
    to_number,
    to_string,
    js_typeof,
    CURRENT_VM,
    OutputBudget,
    reserve_string,
    to_array_length,
)
from .errors import (
    JSError,
    JSRangeError,
    JSSyntaxError,
    JSTypeError,
    JSReferenceError,
    MemoryLimitError,
    TimeLimitError,
)
from .numbers import (
    js_number,
    js_pow,
    js_remainder,
    number_to_radix_string,
    to_exponential,
    to_fixed,
    to_precision,
    to_int32,
    to_uint32,
)
from .regex import RegExpError, RegexTimeoutError


class JSThrow(Exception):
    """A JavaScript exception unwinding through Python code.

    Raised when a thrown value finds no handler above the current run loop's
    floor - for example inside a callback invoked by a native function. The
    enclosing run loop catches it and continues unwinding from there.
    """

    def __init__(self, value: JSValue):
        super().__init__(value)
        self.value = value


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
    closure_cells: List[ClosureCell] = (
        None  # Cells for captured variables (from outer function)
    )
    cell_storage: List[ClosureCell] = (
        None  # Cells for variables captured by inner functions
    )
    is_constructor_call: bool = False  # True if this frame is from a "new" call
    new_target: JSValue = None  # The new object for constructor calls
    # Active try handlers in this frame: (catch_ip, stack_depth at TRY_START)
    handlers: List[Tuple[int, int]] = field(default_factory=list)


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


# Deepest JavaScript call stack before a RangeError
MAX_CALL_DEPTH = 10000


def heap_size(roots: List[Any]) -> int:
    """Estimate the bytes used by every JS value reachable from roots."""
    total = 0
    seen = set()
    pending = list(roots)
    while pending:
        value = pending.pop()
        if isinstance(value, str):
            # Count each large string once; small ones are cheap to recount
            if len(value) > 256:
                if id(value) in seen:
                    continue
                seen.add(id(value))
            total += sys.getsizeof(value)
            continue
        if value is None or isinstance(value, (bool, int, float, JSUndefined, JSNull)):
            continue  # Stored inline in the slot that holds them
        if id(value) in seen:
            continue
        seen.add(id(value))
        if isinstance(value, JSObject):
            total += 64
            if isinstance(value, JSArray):
                total += 8 * len(value._elements)
                pending.extend(value._elements)
            elif isinstance(value, JSTypedArray):
                total += value.length * value._element_size
            elif isinstance(value, JSArrayBuffer):
                total += value.byteLength
            for props in (value._properties, value._getters, value._setters):
                if props:
                    total += 64 * len(props)
                    pending.extend(props.keys())
                    pending.extend(props.values())
            if value._prototype is not None:
                pending.append(value._prototype)
        elif isinstance(value, JSFunction):
            total += 256
            for cell in getattr(value, "_closure_cells", None) or ():
                pending.append(cell.value)
            for attr in ("_prototype", "_bound_this", "_original_func"):
                pending.append(getattr(value, attr, None))
            pending.extend(getattr(value, "_bound_args", None) or ())
        elif isinstance(value, ForInIterator):
            total += 64 + 8 * len(value.keys)
            pending.extend(value.keys)
        elif isinstance(value, ForOfIterator):
            total += 64 + 8 * len(value.values)
            pending.extend(value.values)
        else:
            total += 64  # Native functions and other host objects
    return total


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

        # Memory accounting: bytes charged since the heap was last measured,
        # and how many more may be charged before measuring it again
        self._allocated = 0
        self._allocation_budget = memory_limit or 0
        # Size of the environment (built-ins) not counted against the limit
        self.baseline_bytes = 0

    def run(self, compiled: CompiledFunction) -> JSValue:
        """Run compiled bytecode and return result."""
        self.start_time = time.monotonic()

        # Create initial call frame
        frame = CallFrame(
            func=compiled,
            ip=0,
            bp=len(self.stack),
            locals=[UNDEFINED] * compiled.num_locals,
            this_value=UNDEFINED,
        )
        self.call_stack.append(frame)

        token = CURRENT_VM.set(self)
        try:
            return self._run_frames(0)
        except JSThrow as e:
            error = self._uncaught_error(e.value)
            raise error from error.__cause__
        finally:
            CURRENT_VM.reset(token)

    def run_nested(self, compiled: CompiledFunction) -> JSValue:
        """Run a compiled program inside the current execution.

        Used by indirect eval: the program shares this VM's globals, time
        limit and exception handlers, so its throws reach enclosing catches.
        """
        frame = CallFrame(
            func=compiled,
            ip=0,
            bp=len(self.stack),
            locals=[UNDEFINED] * compiled.num_locals,
            this_value=UNDEFINED,
        )
        floor = len(self.call_stack)
        self.call_stack.append(frame)
        return self._run_nested(floor, frame.bp)

    def _run_nested(self, floor: int, stack_len: int) -> JSValue:
        """Run frames above ``floor`` from Python code, cleaning up on error.

        However the nested run ends, its frames and stack values are gone
        afterwards, so an outer handler can never resume a dead frame.
        """
        try:
            return self._run_frames(floor)
        except BaseException:
            del self.call_stack[floor:]
            del self.stack[stack_len:]
            raise

    def _check_limits(self) -> None:
        """Check the time limit every 1024 instructions.

        Memory is checked when it is allocated, by charge().
        """
        self.instruction_count += 1
        if not self.instruction_count & 1023:
            self.check_deadline()

    def check_deadline(self) -> None:
        """Raise TimeLimitError if the time limit has passed."""
        if self.time_limit is not None:
            if time.monotonic() - self.start_time > self.time_limit:
                raise TimeLimitError("Execution timeout")

    def charge(self, nbytes: int) -> None:
        """Account for an allocation of about nbytes, before it is made.

        Charges are tallied. Once the tally could take the heap past
        memory_limit, the live heap is measured - as a garbage collector
        would, only reachable values count - and MemoryLimitError is raised
        if the allocation does not fit.
        """
        if self.memory_limit is None:
            return
        self._allocated += nbytes
        if self._allocated > self._allocation_budget:
            live = self.measure_heap()
            if live + nbytes > self.memory_limit:
                raise MemoryLimitError("Memory limit exceeded")
            self._allocated = nbytes
            # Don't re-measure constantly when close to the limit
            self._allocation_budget = max(
                self.memory_limit - live, self.memory_limit // 8
            )

    def measure_heap(self) -> int:
        """Estimate the bytes of live script data (excluding the baseline)."""
        roots: List[Any] = list(self.globals.values())
        roots.extend(self.stack)
        frames_size = 0
        for frame in self.call_stack:
            frames_size += 128 + 8 * len(frame.locals)
            roots.extend(frame.locals)
            roots.append(frame.this_value)
            roots.append(frame.new_target)
            for cells in (frame.closure_cells, frame.cell_storage):
                for cell in cells or ():
                    roots.append(cell.value)
        return max(0, heap_size(roots) + frames_size - self.baseline_bytes)

    def _charge_result(self, value: JSValue) -> None:
        """Charge for a value a native function returned."""
        if self.memory_limit is None:
            return
        if isinstance(value, str):
            self.charge(len(value) + 49)
        elif isinstance(value, JSArray):
            self.charge(64 + 8 * len(value._elements))
        elif isinstance(value, JSObject):
            self.charge(64 + 64 * len(value._properties))

    def _run_frames(self, floor: int) -> JSValue:
        """Execute until the call stack shrinks back to ``floor`` frames.

        Returns the value left by the frame that returned to ``floor``. A
        thrown value with no handler above ``floor`` propagates as JSThrow,
        to be caught by whichever run loop called the native code we are
        nested in.
        """
        call_stack = self.call_stack
        while len(call_stack) > floor:
            self._check_limits()

            frame = call_stack[-1]
            bytecode = frame.func.bytecode

            if frame.ip >= len(bytecode):
                self._return(UNDEFINED)
                continue

            op = OpCode(bytecode[frame.ip])
            frame.ip += 1

            # Decode operand, if any
            arg = None
            if op in OPCODES_WITH_ARG:
                arg = bytecode[frame.ip]
                frame.ip += 1

            try:
                self._execute_opcode(op, arg, frame)
            except JSThrow as e:
                self._throw(e.value, floor)
            except (TimeLimitError, MemoryLimitError):
                # Sandbox limits must never be catchable by JavaScript
                raise
            except RegexTimeoutError:
                raise TimeLimitError("Regex execution timeout")
            except JSError as e:
                self._throw(self._make_error(e.name, e.message), floor)
            except RegExpError as e:
                error = self._make_error(
                    "SyntaxError", f"Invalid regular expression: {e}"
                )
                self._throw(error, floor)
            except RecursionError:
                # JS -> native -> JS nesting exhausted the Python stack
                error = self._make_error(
                    "RangeError", "Maximum call stack size exceeded"
                )
                self._throw(error, floor)
            except Exception as e:
                # A host function, or an engine bug: surface it as a JS error
                error = self._make_error("InternalError", f"{type(e).__name__}: {e}")
                error._python_exception = e
                self._throw(error, floor)

        return self.stack.pop()

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
            self.charge(64 + 8 * arg)
            elements = []
            for _ in range(arg):
                elements.insert(0, self.stack.pop())
            arr = JSArray()
            arr._elements = elements
            # Set prototype from Array constructor
            array_constructor = self.globals.get("Array")
            if array_constructor and hasattr(array_constructor, "_prototype"):
                arr._prototype = array_constructor._prototype
            self.stack.append(arr)

        elif op == OpCode.BUILD_OBJECT:
            self.charge(64 + 64 * arg)
            obj = JSObject()
            # Set prototype from Object constructor
            object_constructor = self.globals.get("Object")
            if object_constructor and hasattr(object_constructor, "_prototype"):
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
            # Create a timeout callback for the regex engine
            poll_callback = None
            if self.time_limit is not None:

                def check_timeout() -> bool:
                    """Return True if time limit exceeded (to abort regex)."""
                    return time.monotonic() - self.start_time > self.time_limit

                poll_callback = check_timeout
            regex = JSRegExp(pattern, flags, poll_callback)
            self.stack.append(regex)

        # Arithmetic
        elif op == OpCode.ADD:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(self._add(a, b))

        elif op == OpCode.SUB:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(js_number(to_number(a) - to_number(b)))

        elif op == OpCode.MUL:
            b = self.stack.pop()
            a = self.stack.pop()
            a_num = to_number(a)
            b_num = to_number(b)
            if a_num == 0 or b_num == 0:
                # Floats keep the sign of zero: 0 * -1 is -0
                self.stack.append(float(a_num) * float(b_num))
            else:
                self.stack.append(js_number(a_num * b_num))

        elif op == OpCode.DIV:
            b = self.stack.pop()
            a = self.stack.pop()
            b_num = to_number(b)
            a_num = to_number(a)
            if b_num == 0:
                # Check sign of zero using copysign
                b_sign = math.copysign(1, b_num)
                if a_num == 0:
                    self.stack.append(float("nan"))
                elif (a_num > 0) == (b_sign > 0):  # Same sign
                    self.stack.append(float("inf"))
                else:  # Different signs
                    self.stack.append(float("-inf"))
            else:
                self.stack.append(a_num / b_num)

        elif op == OpCode.MOD:
            b = self.stack.pop()
            a = self.stack.pop()
            a_num = to_number(a)
            self.stack.append(js_remainder(a_num, to_number(b)))

        elif op == OpCode.POW:
            b = self.stack.pop()
            a = self.stack.pop()
            a_num = to_number(a)
            self.stack.append(js_pow(a_num, to_number(b)))

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
            if not (
                isinstance(constructor, JSFunction)
                or (
                    isinstance(constructor, JSObject)
                    and hasattr(constructor, "_call_fn")
                )
            ):
                raise JSTypeError("Right-hand side of instanceof is not callable")

            # Check prototype chain
            if not isinstance(obj, JSObject):
                self.stack.append(False)
            else:
                # Get constructor's prototype property
                # For JSFunction, check _prototype attribute (if set and not None)
                # For JSCallableObject and other constructors, use get("prototype")
                proto = None
                if (
                    isinstance(constructor, JSFunction)
                    and getattr(constructor, "_prototype", None) is not None
                ):
                    proto = constructor._prototype
                elif isinstance(constructor, JSObject):
                    # Try get("prototype") first for callable objects, fall back to _prototype
                    proto = constructor.get("prototype")
                    if proto is None or proto is UNDEFINED:
                        proto = getattr(constructor, "_prototype", None)

                # Walk the prototype chain
                result = False
                current = getattr(obj, "_prototype", None)
                while current is not None:
                    if current is proto:
                        result = True
                        break
                    current = getattr(current, "_prototype", None)
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
            self._return(result)

        elif op == OpCode.RETURN_UNDEFINED:
            self._return(UNDEFINED)

        # Object operations
        elif op == OpCode.NEW:
            self._new_object(arg)

        elif op == OpCode.THIS:
            self.stack.append(frame.this_value)

        # Exception handling
        elif op == OpCode.THROW:
            exc = self.stack.pop()
            self._set_error_location(exc)
            raise JSThrow(exc)

        elif op == OpCode.TRY_START:
            # arg is the catch handler offset
            frame.handlers.append((arg, len(self.stack)))

        elif op == OpCode.TRY_END:
            frame.handlers.pop()

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
            self.stack.append(js_number(to_number(a) + 1))

        elif op == OpCode.DEC:
            a = self.stack.pop()
            self.stack.append(js_number(to_number(a) - 1))

        # Closures
        elif op == OpCode.MAKE_CLOSURE:
            self.charge(512)  # Function, prototype object and cells
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
                        if frame.cell_storage and var_name in getattr(
                            frame.func, "cell_vars", []
                        ):
                            idx = frame.func.cell_vars.index(var_name)
                            # Share the same cell!
                            closure_cells.append(frame.cell_storage[idx])
                        elif frame.closure_cells and var_name in getattr(
                            frame.func, "free_vars", []
                        ):
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

    def _return(self, result: JSValue) -> None:
        """Pop the current frame, discard its stack values and push result."""
        frame = self.call_stack.pop()
        del self.stack[frame.bp :]
        # For constructor calls, return the new object unless result is an object
        if frame.is_constructor_call and not isinstance(result, JSObject):
            result = frame.new_target
        self.stack.append(result)

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
            method = self._get_property(value, method_name)
            if method is UNDEFINED or method is NULL:
                continue
            if isinstance(method, JSFunction) or callable(method):
                result = self._call_callback(method, [], value)
                if not isinstance(result, JSObject):
                    return result

        # If we get here, conversion failed
        raise JSTypeError("Cannot convert object to primitive value")

    def _to_number(self, value: JSValue) -> Union[int, float]:
        """Convert to number, with ToPrimitive for objects."""
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
            a_str = to_string(a)
            b_str = to_string(b)
            reserve_string(len(a_str) + len(b_str))
            return a_str + b_str
        # Numeric addition
        return js_number(to_number(a) + to_number(b))

    def _to_int32(self, value: JSValue) -> int:
        """Convert to 32-bit signed integer."""
        return to_int32(to_number(value))

    def _to_uint32(self, value: JSValue) -> int:
        """Convert to 32-bit unsigned integer."""
        return to_uint32(to_number(value))

    def _compare(self, a: JSValue, b: JSValue) -> int:
        """Compare two values. Returns -1, 0, or 1."""
        # Both strings: compare as strings
        if isinstance(a, str) and isinstance(b, str):
            if a < b:
                return -1
            if a > b:
                return 1
            return 0

        # Convert to numbers for numeric comparison
        a_num = to_number(a)
        b_num = to_number(b)
        # Handle NaN - any comparison with NaN returns false, we return 1
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

        if isinstance(obj, JSArrayBuffer):
            if key_str == "byteLength":
                return obj.byteLength
            return obj.get(key_str)

        if isinstance(obj, JSTypedArray):
            # Typed array index access
            try:
                idx = int(key_str)
                if idx >= 0:
                    return obj.get_index(idx)
            except ValueError:
                pass
            if key_str == "length":
                return obj.length
            if key_str == "BYTES_PER_ELEMENT":
                return obj._element_size
            if key_str == "buffer":
                # Return the underlying buffer if it exists
                return getattr(obj, "_buffer", UNDEFINED)
            # Built-in typed array methods
            typed_array_methods = ["toString", "join", "subarray", "set"]
            if key_str in typed_array_methods:
                return self._make_typed_array_method(obj, key_str)
            return obj.get(key_str)

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
                "push",
                "pop",
                "shift",
                "unshift",
                "toString",
                "join",
                "map",
                "filter",
                "reduce",
                "reduceRight",
                "forEach",
                "indexOf",
                "lastIndexOf",
                "find",
                "findIndex",
                "some",
                "every",
                "concat",
                "slice",
                "splice",
                "reverse",
                "includes",
                "sort",
            ]
            if key_str in array_methods:
                return self._make_array_method(obj, key_str)
            return obj.get(key_str)

        if isinstance(obj, JSRegExp):
            # RegExp methods and properties
            if key_str in ("test", "exec"):
                return self._make_regexp_method(obj, key_str)
            # RegExp properties
            if key_str in (
                "source",
                "flags",
                "global",
                "ignoreCase",
                "multiline",
                "dotAll",
                "unicode",
                "sticky",
                "lastIndex",
            ):
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
                return getattr(obj, "_prototype", UNDEFINED) or UNDEFINED
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
            proto = getattr(obj, "_prototype", None)
            while proto is not None:
                if isinstance(proto, JSObject) and proto.has(key_str):
                    return proto.get(key_str)
                proto = getattr(proto, "_prototype", None)
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
                "charAt",
                "charCodeAt",
                "indexOf",
                "lastIndexOf",
                "substring",
                "slice",
                "split",
                "toLowerCase",
                "toUpperCase",
                "trim",
                "trimStart",
                "trimEnd",
                "concat",
                "repeat",
                "startsWith",
                "endsWith",
                "includes",
                "replace",
                "replaceAll",
                "padStart",
                "padEnd",
                "match",
                "search",
                "toString",
            ]
            if key_str in string_methods:
                return self._make_string_method(obj, key_str)
            return UNDEFINED

        if isinstance(obj, (int, float)):
            # Number methods
            if key_str in (
                "toFixed",
                "toString",
                "toExponential",
                "toPrecision",
                "valueOf",
            ):
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
            vm.charge(8 * len(args))
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
            vm.charge(8 * len(args))
            arr._elements[0:0] = args
            return arr.length

        def array_elem_to_string(elem):
            # undefined and null convert to empty string in array join/toString
            if elem is UNDEFINED or elem is NULL:
                return ""
            return to_string(elem)

        def join_elements(sep):
            budget = OutputBudget()
            parts = []
            for elem in arr._elements:
                part = array_elem_to_string(elem)
                budget.add(len(part) + len(sep))
                parts.append(part)
            budget.finish()
            return sep.join(parts)

        def toString_fn(*args):
            return join_elements(",")

        def join_fn(*args):
            sep = "," if not args or args[0] is UNDEFINED else to_string(args[0])
            return join_elements(sep)

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

        def reduceRight_fn(*args):
            callback = args[0] if args else None
            initial = args[1] if len(args) > 1 else UNDEFINED
            if not callback:
                raise JSTypeError("reduceRight callback is not a function")
            acc = initial
            length = len(arr._elements)
            start_idx = length - 1
            if acc is UNDEFINED:
                if not arr._elements:
                    raise JSTypeError("Reduce of empty array with no initial value")
                acc = arr._elements[length - 1]
                start_idx = length - 2
            for i in range(start_idx, -1, -1):
                elem = arr._elements[i]
                acc = vm._call_callback(callback, [acc, elem, i, arr])
            return acc

        def splice_fn(*args):
            start = int(to_number(args[0])) if args else 0
            delete_count = (
                int(to_number(args[1])) if len(args) > 1 else len(arr._elements) - start
            )
            items = list(args[2:]) if len(args) > 2 else []
            vm.charge(8 * len(items))

            length = len(arr._elements)
            if start < 0:
                start = max(0, length + start)
            else:
                start = min(start, length)

            delete_count = max(0, min(delete_count, length - start))

            # Create result array with deleted elements
            result = JSArray()
            result._elements = arr._elements[start : start + delete_count]

            # Modify original array
            arr._elements = (
                arr._elements[:start] + items + arr._elements[start + delete_count :]
            )

            return result

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
                if not i & 4095:
                    vm.check_deadline()
            return -1

        def lastIndexOf_fn(*args):
            search = args[0] if args else UNDEFINED
            start = int(to_number(args[1])) if len(args) > 1 else len(arr._elements) - 1
            if start < 0:
                start = len(arr._elements) + start
            for i in range(min(start, len(arr._elements) - 1), -1, -1):
                if vm._strict_equals(arr._elements[i], search):
                    return i
                if not i & 4095:
                    vm.check_deadline()
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
            vm.charge(
                8 * len(arr._elements)
                + sum(8 * len(a._elements) for a in args if isinstance(a, JSArray))
            )
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
                if not i & 4095:
                    vm.check_deadline()
            return False

        def sort_fn(*args):
            comparator = args[0] if args else None

            # Default string comparison
            def default_compare(a, b):
                # Convert to strings and compare
                str_a = to_string(a)
                str_b = to_string(b)
                if str_a < str_b:
                    return -1
                if str_a > str_b:
                    return 1
                return 0

            comparisons = [0]

            def compare_fn(a, b):
                comparisons[0] += 1
                if not comparisons[0] & 1023:
                    vm.check_deadline()
                # undefined values always sort to the end per JS spec
                if a is UNDEFINED and b is UNDEFINED:
                    return 0
                if a is UNDEFINED:
                    return 1
                if b is UNDEFINED:
                    return -1
                # Use comparator if provided
                if comparator and (
                    callable(comparator) or isinstance(comparator, JSFunction)
                ):
                    num = to_number(vm._call_callback(comparator, [a, b]))
                    # Only the sign matters; NaN counts as equal
                    return (num > 0) - (num < 0)
                return default_compare(a, b)

            # Sort using Python's sort with custom key
            from functools import cmp_to_key

            arr._elements.sort(key=cmp_to_key(compare_fn))
            return arr

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
            "splice": splice_fn,
            "reverse": reverse_fn,
            "includes": includes_fn,
            "sort": sort_fn,
            "reduceRight": reduceRight_fn,
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
                params=func.params[
                    len(bound_args) :
                ],  # Remaining params after bound args
                bytecode=func.bytecode,
            )
            # Copy compiled function reference
            if hasattr(func, "_compiled"):
                bound_func._compiled = func._compiled
            # Copy closure cells
            if hasattr(func, "_closure_cells"):
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
        if hasattr(func, "_bound_this"):
            this_val = func._bound_this
        if hasattr(func, "_bound_args"):
            args = list(func._bound_args) + list(args)
        if hasattr(func, "_original_func"):
            func = func._original_func

        return self._call_callback(func, args, this_val)

    def _make_regexp_method(self, re: JSRegExp, method: str) -> Any:
        """Create a bound RegExp method."""

        def test_fn(*args):
            string = to_string(args[0]) if args else ""
            try:
                return re.test(string)
            except RegexTimeoutError:
                raise TimeLimitError("Regex execution timeout")

        def exec_fn(*args):
            string = to_string(args[0]) if args else ""
            try:
                return re.exec(string)
            except RegexTimeoutError:
                raise TimeLimitError("Regex execution timeout")

        methods = {
            "test": test_fn,
            "exec": exec_fn,
        }
        return methods.get(method, lambda *args: UNDEFINED)

    def _make_typed_array_method(self, arr: JSTypedArray, method: str) -> Any:
        """Create a bound typed array method."""

        def toString_fn(*args):
            # Join elements with comma
            return ",".join(str(arr.get_index(i)) for i in range(arr.length))

        def join_fn(*args):
            separator = to_string(args[0]) if args else ","
            return separator.join(str(arr.get_index(i)) for i in range(arr.length))

        def subarray_fn(*args):
            begin = int(to_number(args[0])) if len(args) > 0 else 0
            end = int(to_number(args[1])) if len(args) > 1 else arr.length

            # Handle negative indices
            if begin < 0:
                begin = max(0, arr.length + begin)
            if end < 0:
                end = max(0, arr.length + end)

            # Clamp to bounds
            begin = min(begin, arr.length)
            end = min(end, arr.length)

            # Create new typed array of same type
            result = type(arr)(max(0, end - begin))
            for i in range(begin, end):
                result.set_index(i - begin, arr.get_index(i))
            # Share the same buffer if the original has one
            if hasattr(arr, "_buffer"):
                result._buffer = arr._buffer
            return result

        def set_fn(*args):
            # TypedArray.set(array, offset)
            source = args[0] if args else UNDEFINED
            offset = int(to_number(args[1])) if len(args) > 1 else 0

            if isinstance(source, (JSArray, JSTypedArray)):
                for i in range(source.length):
                    arr.set_index(offset + i, source.get_index(i))
            return UNDEFINED

        methods = {
            "toString": toString_fn,
            "join": join_fn,
            "subarray": subarray_fn,
            "set": set_fn,
        }
        return methods.get(method, lambda *args: UNDEFINED)

    def _make_number_method(self, n: float, method: str) -> Any:
        """Create a bound number method."""

        def toFixed(*args):
            digits = to_number(args[0]) if args else 0
            digits = 0 if digits != digits else int(digits)
            if digits < 0 or digits > 100:
                raise JSRangeError(
                    "toFixed() digits argument must be between 0 and 100"
                )
            return to_fixed(n, digits)

        def toString(*args):
            radix = 10
            if args and args[0] is not UNDEFINED:
                radix = to_number(args[0])
                radix = 0 if radix != radix else int(radix)
            if radix < 2 or radix > 36:
                raise JSRangeError("toString() radix must be between 2 and 36")
            if radix == 10:
                return to_string(n)
            return number_to_radix_string(n, radix)

        def toExponential(*args):
            digits = None
            if args and args[0] is not UNDEFINED:
                digits = to_number(args[0])
                digits = 0 if digits != digits else int(digits)
            if digits is not None and math.isfinite(n) and not 0 <= digits <= 100:
                raise JSRangeError("toExponential() digits must be between 0 and 100")
            return to_exponential(n, digits)

        def toPrecision(*args):
            if not args or args[0] is UNDEFINED:
                return to_string(n)
            precision = to_number(args[0])
            precision = 0 if precision != precision else int(precision)
            if not math.isfinite(n):
                return to_string(n)
            if not 1 <= precision <= 100:
                raise JSRangeError("toPrecision() precision must be between 1 and 100")
            return to_precision(n, precision)

        def valueOf(*args):
            return n

        methods = {
            "toFixed": toFixed,
            "toString": toString,
            "toExponential": toExponential,
            "toPrecision": toPrecision,
            "valueOf": valueOf,
        }
        return methods.get(method, lambda *args: UNDEFINED)

    @staticmethod
    def _get_substitution(
        template: str, matched: str, string: str, position: int, captures: List
    ) -> str:
        """Expand $$, $&, $`, $' and $n/$nn in a replacement string."""
        result = []
        i = 0
        n = len(template)
        while i < n:
            ch = template[i]
            if ch != "$" or i + 1 >= n:
                result.append(ch)
                i += 1
                continue
            nxt = template[i + 1]
            if nxt == "$":
                result.append("$")
            elif nxt == "&":
                result.append(matched)
            elif nxt == "`":
                result.append(string[:position])
            elif nxt == "'":
                result.append(string[position + len(matched) :])
            elif "0" <= nxt <= "9":
                # Prefer a two-digit group number when that group exists
                two = template[i + 1 : i + 3]
                if (
                    len(two) == 2
                    and "0" <= two[1] <= "9"
                    and 1 <= int(two) <= len(captures)
                ):
                    group, width = int(two), 2
                elif 1 <= int(nxt) <= len(captures):
                    group, width = int(nxt), 1
                else:
                    result.append("$")
                    i += 1
                    continue
                capture = captures[group - 1]
                result.append(
                    "" if capture is None or capture is UNDEFINED else capture
                )
                i += 1 + width
                continue
            else:
                result.append("$")
                i += 1
                continue
            i += 2
        return "".join(result)

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
            return float("nan")

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
            if isinstance(sep, str) or (
                sep is not UNDEFINED and not isinstance(sep, JSRegExp)
            ):
                # Charge for the pieces before making them
                sep_str = to_string(sep)
                pieces = len(s) if sep_str == "" else s.count(sep_str) + 1
                self.charge(64 * pieces + len(s))

            if sep is UNDEFINED:
                parts = [s]
            elif isinstance(sep, JSRegExp):
                # Split with regex using microjs.regex
                try:
                    regex_internal = sep._internal
                    parts = []
                    last_end = 0
                    pos = 0
                    capture_count = regex_internal._capture_count

                    while pos <= len(s):
                        # Create fresh regex VM for each search to avoid lastIndex issues
                        vm_regex = regex_internal._create_vm()
                        result = vm_regex.search(s, pos)
                        if result is None:
                            break

                        # Add the part before this match
                        parts.append(s[last_end : result.index])

                        # Add captured groups (JS behavior) - capture_count includes group 0
                        for i in range(1, capture_count):
                            group_val = result[i]
                            parts.append(
                                group_val if group_val is not None else UNDEFINED
                            )

                        # Move past the match
                        match_len = len(result[0]) if result[0] else 0
                        last_end = result.index + match_len
                        # Advance position (at least by 1 to avoid infinite loop on zero-width)
                        pos = last_end if match_len > 0 else result.index + 1

                    # Add remainder after last match
                    parts.append(s[last_end:])
                except RegexTimeoutError:
                    raise TimeLimitError("Regex execution timeout")
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

        def trimStart(*args):
            return s.lstrip()

        def trimEnd(*args):
            return s.rstrip()

        def concat(*args):
            parts = [s] + [to_string(arg) for arg in args]
            reserve_string(sum(len(part) for part in parts))
            return "".join(parts)

        def repeat(*args):
            count = to_number(args[0]) if args else 0
            if count != count:
                count = 0
            if count < 0 or count == float("inf"):
                raise JSRangeError("Invalid count value")
            count = int(count)
            reserve_string(len(s) * count)
            return s * count

        def pad(args, at_start):
            target = to_number(args[0]) if args else 0
            target = 0 if target != target else target
            filler = " "
            if len(args) > 1 and args[1] is not UNDEFINED:
                filler = to_string(args[1])
            if target <= len(s) or not filler:
                return s
            if target == float("inf"):
                raise JSRangeError("Invalid string length")
            target = int(target)
            reserve_string(target)
            needed = target - len(s)
            padding = (filler * (needed // len(filler) + 1))[:needed]
            return padding + s if at_start else s + padding

        def padStart(*args):
            return pad(args, at_start=True)

        def padEnd(*args):
            return pad(args, at_start=False)

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

        def make_replacer(replacement):
            """Return f(matched, position, captures) giving the replacement text."""
            if isinstance(replacement, JSFunction) or callable(replacement):
                # Called with (match, ...captures, offset, string)
                def call(matched, position, captures):
                    args = [matched]
                    args += [UNDEFINED if c is None else c for c in captures]
                    args += [position, s]
                    return to_string(self._call_callback(replacement, args))

                return call
            template = to_string(replacement)
            return lambda matched, position, captures: self._get_substitution(
                template, matched, s, position, captures
            )

        def replace(*args):
            pattern = args[0] if args else ""
            replacer = make_replacer(args[1] if len(args) > 1 else UNDEFINED)

            if isinstance(pattern, JSRegExp):
                # Replace with regex using microjs.regex
                try:
                    regex_internal = pattern._internal
                    is_global = "g" in pattern._flags
                    capture_count = regex_internal._capture_count

                    result_parts = []
                    budget = OutputBudget()
                    last_end = 0
                    pos = 0

                    while pos <= len(s):
                        # Create fresh regex VM for each search
                        vm_regex = regex_internal._create_vm()
                        match_result = vm_regex.search(s, pos)
                        if match_result is None:
                            break

                        matched = match_result[0] or ""
                        # _capture_count includes group 0, the whole match
                        captures = [match_result[i] for i in range(1, capture_count)]
                        # Add the part before this match, then the replacement
                        before = s[last_end : match_result.index]
                        replacement = replacer(matched, match_result.index, captures)
                        budget.add(len(before) + len(replacement))
                        result_parts.append(before)
                        result_parts.append(replacement)

                        # Move past the match
                        last_end = match_result.index + len(matched)
                        pos = last_end if matched else match_result.index + 1

                        if not is_global:
                            break

                    # Add remainder after last match
                    result_parts.append(s[last_end:])
                    budget.add(len(s) - last_end)
                    budget.finish()
                    return "".join(result_parts)
                except RegexTimeoutError:
                    raise TimeLimitError("Regex execution timeout")
            else:
                # String pattern: replace the first occurrence only
                search = to_string(pattern)
                idx = s.find(search)
                if idx < 0:
                    return s
                return s[:idx] + replacer(search, idx, []) + s[idx + len(search) :]

        def replaceAll(*args):
            pattern = args[0] if args else ""
            replacement = args[1] if len(args) > 1 else UNDEFINED

            if isinstance(pattern, JSRegExp):
                # replaceAll with regex requires global flag
                if "g" not in pattern._flags:
                    raise JSTypeError("replaceAll called with a non-global RegExp")
                return replace(pattern, replacement)

            # String pattern: replace every non-overlapping occurrence
            search = to_string(pattern)
            replacer = make_replacer(replacement)
            if search == "":
                positions = list(range(len(s) + 1))
            else:
                positions = []
                idx = s.find(search)
                while idx >= 0:
                    positions.append(idx)
                    idx = s.find(search, idx + len(search))
            parts = []
            budget = OutputBudget()
            last_end = 0
            for idx in positions:
                before = s[last_end:idx]
                replacement = replacer(search, idx, [])
                budget.add(len(before) + len(replacement))
                parts.append(before)
                parts.append(replacement)
                last_end = idx + len(search)
            parts.append(s[last_end:])
            budget.add(len(s) - last_end)
            budget.finish()
            return "".join(parts)

        def match(*args):
            pattern = args[0] if args else None
            if pattern is None:
                # Match empty string
                arr = JSArray()
                arr._elements = [""]
                arr.set("index", 0)
                arr.set("input", s)
                return arr

            from .regex import RegExp as InternalRegExp

            if isinstance(pattern, JSRegExp):
                regex_internal = pattern._internal
                is_global = "g" in pattern._flags
            else:
                # Convert string to regex using microjs.regex
                # Create a poll_callback if the VM has time limits
                poll_callback = None
                if self.time_limit is not None:
                    poll_callback = (
                        lambda: time.monotonic() - self.start_time > self.time_limit
                    )
                regex_internal = InternalRegExp(to_string(pattern), "", poll_callback)
                is_global = False

            try:
                if is_global:
                    # Global flag: return all matches without groups
                    matches = []
                    pos = 0
                    while pos <= len(s):
                        # Create fresh regex VM for each search
                        vm_regex = regex_internal._create_vm()
                        result = vm_regex.search(s, pos)
                        if result is None:
                            break
                        matches.append(result[0])
                        # Advance position
                        match_len = len(result[0]) if result[0] else 0
                        pos = (
                            result.index + match_len
                            if match_len > 0
                            else result.index + 1
                        )

                    if not matches:
                        return NULL
                    arr = JSArray()
                    arr._elements = list(matches)
                    return arr
                else:
                    # Non-global: return first match with groups
                    vm_regex = regex_internal._create_vm()
                    result = vm_regex.search(s, 0)
                    if result is None:
                        return NULL
                    arr = JSArray()
                    arr._elements = [result[0]]
                    # Add captured groups (capture_count includes group 0, so iterate 1 to capture_count-1)
                    capture_count = regex_internal._capture_count
                    for i in range(1, capture_count):
                        group_val = result[i]
                        if group_val is None:
                            arr._elements.append(UNDEFINED)
                        else:
                            arr._elements.append(group_val)
                    arr.set("index", result.index)
                    arr.set("input", s)
                    return arr
            except RegexTimeoutError:
                raise TimeLimitError("Regex execution timeout")

        def search(*args):
            pattern = args[0] if args else None
            if pattern is None:
                return 0  # Match empty string at start

            from .regex import RegExp as InternalRegExp

            if isinstance(pattern, JSRegExp):
                regex_internal = pattern._internal
            else:
                # Convert string to regex using microjs.regex
                poll_callback = None
                if self.time_limit is not None:
                    poll_callback = (
                        lambda: time.monotonic() - self.start_time > self.time_limit
                    )
                regex_internal = InternalRegExp(to_string(pattern), "", poll_callback)

            try:
                vm_regex = regex_internal._create_vm()
                result = vm_regex.search(s, 0)
                return result.index if result else -1
            except RegexTimeoutError:
                raise TimeLimitError("Regex execution timeout")

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
            "trimStart": trimStart,
            "trimEnd": trimEnd,
            "concat": concat,
            "repeat": repeat,
            "startsWith": startsWith,
            "endsWith": endsWith,
            "includes": includes,
            "replace": replace,
            "replaceAll": replaceAll,
            "padStart": padStart,
            "padEnd": padEnd,
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

        if isinstance(obj, JSTypedArray):
            try:
                idx = int(key_str)
                if idx >= 0:
                    obj.set_index(idx, value)
                    return
            except ValueError:
                pass
            obj.set(key_str, value)
            return

        if isinstance(obj, JSArray):
            # Special handling for length property
            if key_str == "length":
                obj.length = to_array_length(value)
                return
            # Strict array mode: reject non-integer indices
            # Valid indices are integer strings in range [0, 2^32-2]
            try:
                idx = int(key_str)
                if idx >= 0 and str(idx) == key_str:
                    if idx == len(obj._elements):
                        self.charge(8)
                    obj.set_index(idx, value)
                    return
            except (ValueError, IndexError):
                pass
            # If key looks like a number but isn't a valid integer index, throw
            # This includes NaN, Infinity, -Infinity, floats like "1.2"
            invalid_keys = ("NaN", "Infinity", "-Infinity")
            if key_str in invalid_keys:
                raise JSTypeError(f"Cannot set property '{key_str}' on array")
            # Check if it looks like a float
            try:
                float_val = float(key_str)
                if (
                    not float_val.is_integer()
                    or math.isinf(float_val)
                    or math.isnan(float_val)
                ):
                    raise JSTypeError(f"Cannot set property '{key_str}' on array")
            except ValueError:
                pass  # Not a number, allow as string property
            obj.set(key_str, value)
        elif isinstance(obj, JSObject):
            # Check for setter
            setter = obj.get_setter(key_str)
            if setter is not None:
                self._invoke_setter(setter, obj, value)
            else:
                if key_str not in obj._properties:
                    self.charge(64 + len(key_str))
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
            self._charge_result(result)
            self.stack.append(result if result is not None else UNDEFINED)
        else:
            raise JSTypeError(f"{callee} is not a function")

    def _call_method(
        self, method: JSValue, this_val: JSValue, args: List[JSValue]
    ) -> None:
        """Call a method."""
        from .values import JSBoundMethod

        if isinstance(method, JSFunction):
            self._invoke_js_function(method, args, this_val)
        elif isinstance(method, JSBoundMethod):
            # JSBoundMethod expects this_val as first argument
            result = method(this_val, *args)
            self._charge_result(result)
            self.stack.append(result if result is not None else UNDEFINED)
        elif callable(method):
            result = method(*args)
            self._charge_result(result)
            self.stack.append(result if result is not None else UNDEFINED)
        else:
            raise JSTypeError(f"{method} is not a function")

    def _call_callback(
        self, callback: JSValue, args: List[JSValue], this_val: JSValue = None
    ) -> JSValue:
        """Call a function synchronously from Python and return its result."""
        from .values import JSBoundMethod

        if this_val is None:
            this_val = UNDEFINED
        if isinstance(callback, JSFunction):
            floor = len(self.call_stack)
            stack_len = len(self.stack)
            self._invoke_js_function(callback, args, this_val)
            return self._run_nested(floor, stack_len)
        if isinstance(callback, JSBoundMethod):
            result = callback(this_val, *args)
        elif callable(callback):
            result = callback(*args)
        else:
            raise JSTypeError(f"{callback} is not a function")
        return UNDEFINED if result is None else result

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
        if hasattr(func, "_bound_this"):
            this_val = func._bound_this
        if hasattr(func, "_bound_args"):
            args = list(func._bound_args) + list(args)
        if hasattr(func, "_original_func"):
            func = func._original_func

        compiled = getattr(func, "_compiled", None)
        if compiled is None:
            raise JSTypeError("Function has no bytecode")
        if len(self.call_stack) >= MAX_CALL_DEPTH:
            raise JSRangeError("Maximum call stack size exceeded")
        self.charge(192 + 8 * (compiled.num_locals + len(args)))

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
        closure_cells = getattr(func, "_closure_cells", None)

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
            if hasattr(constructor, "_prototype"):
                obj._prototype = constructor._prototype
            # Call constructor with new object as 'this'
            # Mark this as a constructor call so RETURN knows to return the object
            self._invoke_js_function(
                constructor, args, obj, is_constructor=True, new_target=obj
            )
            # Don't push obj here - RETURN/RETURN_UNDEFINED will handle it
        elif isinstance(constructor, JSObject) and hasattr(constructor, "_call_fn"):
            # Built-in constructor (like Object, Array, RegExp)
            result = constructor._call_fn(*args)
            self._charge_result(result)
            self.stack.append(result)
        else:
            raise JSTypeError(f"{constructor} is not a constructor")

    def _get_source_location(self) -> Tuple[Optional[int], Optional[int]]:
        """Get the source location (line, column) for the current instruction."""
        if not self.call_stack:
            return None, None
        frame = self.call_stack[-1]
        source_map = getattr(frame.func, "source_map", None)
        if source_map:
            # Find the closest source location at or before current IP
            # Walk backwards from current IP to find a mapped position
            for ip in range(frame.ip, -1, -1):
                if ip in source_map:
                    return source_map[ip]
        return None, None

    def _set_error_location(self, exc: JSValue) -> None:
        """Record the current source location on a thrown error object.

        Error constructors create a lineNumber placeholder; other thrown
        objects are user data and are left alone.
        """
        if isinstance(exc, JSObject) and exc.has("lineNumber"):
            line, column = self._get_source_location()
            if line is not None:
                exc.set("lineNumber", line)
            if column is not None:
                exc.set("columnNumber", column)

    def _throw(self, exc: JSValue, floor: int) -> None:
        """Transfer control to the innermost handler above ``floor``.

        Frames without a handler are discarded. If no frame above ``floor``
        has one, the exception continues as JSThrow.
        """
        while len(self.call_stack) > floor:
            frame = self.call_stack[-1]
            if frame.handlers:
                catch_ip, stack_depth = frame.handlers.pop()
                del self.stack[stack_depth:]
                self.stack.append(exc)
                frame.ip = catch_ip
                return
            self.call_stack.pop()
            del self.stack[frame.bp :]
        raise JSThrow(exc)

    def _make_error(self, error_type: str, message: str) -> JSValue:
        """Create a JavaScript error object, located at the current instruction.

        Uses the global constructor named ``error_type`` (TypeError, ...) if
        there is one, otherwise an Error whose name is ``error_type``.
        """
        error_constructor = self.globals.get(error_type)
        if not hasattr(error_constructor, "_call_fn"):
            error_constructor = self.globals.get("Error")
        if hasattr(error_constructor, "_call_fn"):
            error_obj = error_constructor._call_fn(message)
        else:
            error_obj = JSObject()
            error_obj.set("message", message)
        if not isinstance(error_obj, JSObject):
            error_obj = JSObject()
            error_obj.set("message", message)
        error_obj.set("name", error_type)
        self._set_error_location(error_obj)
        return error_obj

    _ERROR_CLASSES = {
        "TypeError": JSTypeError,
        "ReferenceError": JSReferenceError,
        "RangeError": JSRangeError,
        "SyntaxError": JSSyntaxError,
    }

    def _uncaught_error(self, exc: JSValue) -> JSError:
        """Build the Python exception for a JS exception nothing caught.

        The exception's class and name follow the thrown error's name, and
        its ``value`` attribute holds the thrown JS value.
        """
        name, message = "Error", to_string(exc)
        if isinstance(exc, JSObject):
            js_name = exc.get("name")
            js_message = exc.get("message")
            if js_name is not UNDEFINED or js_message is not UNDEFINED:
                if js_name is not UNDEFINED and js_name is not NULL:
                    name = to_string(js_name)
                message = "" if js_message is UNDEFINED else to_string(js_message)
        error_class = self._ERROR_CLASSES.get(name)
        error = error_class(message) if error_class else JSError(message, name)
        error.value = exc
        error.__cause__ = getattr(exc, "_python_exception", None)
        return error
