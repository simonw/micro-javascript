"""JavaScript execution context."""

import json
import math
import random
import time
from typing import Any, Dict, Optional

from .parser import Parser
from .compiler import Compiler
from .vm import VM
from .values import UNDEFINED, NULL, JSValue, JSObject, JSCallableObject, JSArray, JSFunction, JSRegExp, JSBoundMethod, to_string, to_number
from .errors import JSError, MemoryLimitError, TimeLimitError


class JSContext:
    """JavaScript execution context with configurable limits."""

    def __init__(
        self,
        memory_limit: Optional[int] = None,
        time_limit: Optional[float] = None,
    ):
        """Create a new JavaScript context.

        Args:
            memory_limit: Maximum memory usage in bytes (approximate)
            time_limit: Maximum execution time in seconds
        """
        self.memory_limit = memory_limit
        self.time_limit = time_limit
        self._globals: Dict[str, JSValue] = {}
        self._setup_globals()

    def _setup_globals(self) -> None:
        """Set up built-in global objects and functions."""
        # Console object with log function
        console = JSObject()
        console.set("log", self._console_log)
        self._globals["console"] = console

        # Infinity and NaN
        self._globals["Infinity"] = float("inf")
        self._globals["NaN"] = float("nan")
        self._globals["undefined"] = UNDEFINED

        # Basic type constructors (minimal implementations)
        self._globals["Object"] = self._create_object_constructor()
        self._globals["Array"] = self._create_array_constructor()
        self._globals["Error"] = self._create_error_constructor("Error")
        self._globals["TypeError"] = self._create_error_constructor("TypeError")
        self._globals["SyntaxError"] = self._create_error_constructor("SyntaxError")
        self._globals["ReferenceError"] = self._create_error_constructor("ReferenceError")
        self._globals["RangeError"] = self._create_error_constructor("RangeError")
        self._globals["URIError"] = self._create_error_constructor("URIError")
        self._globals["EvalError"] = self._create_error_constructor("EvalError")

        # Math object
        self._globals["Math"] = self._create_math_object()

        # JSON object
        self._globals["JSON"] = self._create_json_object()

        # Number constructor and methods
        self._globals["Number"] = self._create_number_constructor()

        # String constructor and methods
        self._globals["String"] = self._create_string_constructor()

        # Boolean constructor
        self._globals["Boolean"] = self._create_boolean_constructor()

        # Date constructor
        self._globals["Date"] = self._create_date_constructor()

        # RegExp constructor
        self._globals["RegExp"] = self._create_regexp_constructor()

        # Function constructor
        self._globals["Function"] = self._create_function_constructor()

        # Typed array constructors
        self._globals["Int32Array"] = self._create_typed_array_constructor("Int32Array")
        self._globals["Uint32Array"] = self._create_typed_array_constructor("Uint32Array")
        self._globals["Float64Array"] = self._create_typed_array_constructor("Float64Array")
        self._globals["Float32Array"] = self._create_typed_array_constructor("Float32Array")
        self._globals["Uint8Array"] = self._create_typed_array_constructor("Uint8Array")
        self._globals["Int8Array"] = self._create_typed_array_constructor("Int8Array")
        self._globals["Int16Array"] = self._create_typed_array_constructor("Int16Array")
        self._globals["Uint16Array"] = self._create_typed_array_constructor("Uint16Array")
        self._globals["Uint8ClampedArray"] = self._create_typed_array_constructor("Uint8ClampedArray")

        # ArrayBuffer constructor
        self._globals["ArrayBuffer"] = self._create_arraybuffer_constructor()

        # Global number functions
        self._globals["isNaN"] = self._global_isnan
        self._globals["isFinite"] = self._global_isfinite
        self._globals["parseInt"] = self._global_parseint
        self._globals["parseFloat"] = self._global_parsefloat

        # eval function
        self._globals["eval"] = self._create_eval_function()

    def _console_log(self, *args: JSValue) -> None:
        """Console.log implementation."""
        print(" ".join(to_string(arg) for arg in args))

    def _create_object_constructor(self) -> JSCallableObject:
        """Create the Object constructor with static methods."""
        # Create Object.prototype first
        object_prototype = JSObject()

        # Constructor function - new Object() creates empty object
        def object_constructor(*args):
            obj = JSObject()
            obj._prototype = object_prototype
            return obj

        # Create a callable object that acts as constructor
        obj_constructor = JSCallableObject(object_constructor)
        obj_constructor._prototype = object_prototype
        object_prototype.set("constructor", obj_constructor)

        # Add Object.prototype methods
        def proto_toString(this_val, *args):
            # Get the [[Class]] internal property
            if this_val is UNDEFINED:
                return "[object Undefined]"
            if this_val is NULL:
                return "[object Null]"
            if isinstance(this_val, bool):
                return "[object Boolean]"
            if isinstance(this_val, (int, float)):
                return "[object Number]"
            if isinstance(this_val, str):
                return "[object String]"
            if isinstance(this_val, JSArray):
                return "[object Array]"
            if callable(this_val) or isinstance(this_val, JSCallableObject):
                return "[object Function]"
            return "[object Object]"

        def proto_hasOwnProperty(this_val, *args):
            prop = to_string(args[0]) if args else ""
            if isinstance(this_val, JSArray):
                # For arrays, check both properties and array indices
                try:
                    idx = int(prop)
                    if 0 <= idx < len(this_val._elements):
                        return True
                except (ValueError, TypeError):
                    pass
                return this_val.has(prop) or prop in this_val._getters or prop in this_val._setters
            if isinstance(this_val, JSObject):
                return this_val.has(prop) or prop in this_val._getters or prop in this_val._setters
            return False

        def proto_valueOf(this_val, *args):
            return this_val

        def proto_isPrototypeOf(this_val, *args):
            obj = args[0] if args else UNDEFINED
            if not isinstance(obj, JSObject):
                return False
            proto = getattr(obj, '_prototype', None)
            while proto is not None:
                if proto is this_val:
                    return True
                proto = getattr(proto, '_prototype', None)
            return False

        # These methods need special handling for 'this'
        from .values import JSBoundMethod
        object_prototype.set("toString", JSBoundMethod(proto_toString))
        object_prototype.set("hasOwnProperty", JSBoundMethod(proto_hasOwnProperty))
        object_prototype.set("valueOf", JSBoundMethod(proto_valueOf))
        object_prototype.set("isPrototypeOf", JSBoundMethod(proto_isPrototypeOf))

        # Store for other constructors to use
        self._object_prototype = object_prototype

        def keys_fn(*args):
            obj = args[0] if args else UNDEFINED
            if not isinstance(obj, JSObject):
                return JSArray()
            arr = JSArray()
            arr._elements = list(obj.keys())
            return arr

        def values_fn(*args):
            obj = args[0] if args else UNDEFINED
            if not isinstance(obj, JSObject):
                return JSArray()
            arr = JSArray()
            arr._elements = [obj.get(k) for k in obj.keys()]
            return arr

        def entries_fn(*args):
            obj = args[0] if args else UNDEFINED
            if not isinstance(obj, JSObject):
                return JSArray()
            arr = JSArray()
            arr._elements = []
            for k in obj.keys():
                entry = JSArray()
                entry._elements = [k, obj.get(k)]
                arr._elements.append(entry)
            return arr

        def assign_fn(*args):
            if not args:
                return JSObject()
            target = args[0]
            if not isinstance(target, JSObject):
                return target
            for i in range(1, len(args)):
                source = args[i]
                if isinstance(source, JSObject):
                    for k in source.keys():
                        target.set(k, source.get(k))
            return target

        def get_prototype_of(*args):
            obj = args[0] if args else UNDEFINED
            if not isinstance(obj, JSObject):
                return NULL
            return getattr(obj, '_prototype', NULL) or NULL

        def set_prototype_of(*args):
            if len(args) < 2:
                return UNDEFINED
            obj, proto = args[0], args[1]
            if not isinstance(obj, JSObject):
                return obj
            if proto is NULL or proto is None:
                obj._prototype = None
            elif isinstance(proto, JSObject):
                obj._prototype = proto
            return obj

        def define_property(*args):
            """Object.defineProperty(obj, prop, descriptor)."""
            if len(args) < 3:
                return UNDEFINED
            obj, prop, descriptor = args[0], args[1], args[2]
            if not isinstance(obj, JSObject):
                return obj
            prop_name = to_string(prop)

            if isinstance(descriptor, JSObject):
                # Check for getter/setter
                getter = descriptor.get("get")
                setter = descriptor.get("set")

                if getter is not UNDEFINED and getter is not NULL:
                    obj.define_getter(prop_name, getter)
                if setter is not UNDEFINED and setter is not NULL:
                    obj.define_setter(prop_name, setter)

                # Check for value (only if no getter/setter)
                if getter is UNDEFINED and setter is UNDEFINED:
                    value = descriptor.get("value")
                    if value is not UNDEFINED:
                        obj.set(prop_name, value)

            return obj

        def define_properties(*args):
            """Object.defineProperties(obj, props)."""
            if len(args) < 2:
                return UNDEFINED
            obj, props = args[0], args[1]
            if not isinstance(obj, JSObject) or not isinstance(props, JSObject):
                return obj

            for key in props.keys():
                descriptor = props.get(key)
                define_property(obj, key, descriptor)

            return obj

        def create_fn(*args):
            """Object.create(proto, properties)."""
            proto = args[0] if args else NULL
            properties = args[1] if len(args) > 1 else UNDEFINED

            obj = JSObject()
            if proto is NULL or proto is None:
                obj._prototype = None
            elif isinstance(proto, JSObject):
                obj._prototype = proto

            if properties is not UNDEFINED and isinstance(properties, JSObject):
                define_properties(obj, properties)

            return obj

        def get_own_property_descriptor(*args):
            """Object.getOwnPropertyDescriptor(obj, prop)."""
            if len(args) < 2:
                return UNDEFINED
            obj, prop = args[0], args[1]
            if not isinstance(obj, JSObject):
                return UNDEFINED
            prop_name = to_string(prop)

            if not obj.has(prop_name) and prop_name not in obj._getters and prop_name not in obj._setters:
                return UNDEFINED

            descriptor = JSObject()

            getter = obj._getters.get(prop_name)
            setter = obj._setters.get(prop_name)

            if getter or setter:
                descriptor.set("get", getter if getter else UNDEFINED)
                descriptor.set("set", setter if setter else UNDEFINED)
            else:
                descriptor.set("value", obj.get(prop_name))
                descriptor.set("writable", True)

            descriptor.set("enumerable", True)
            descriptor.set("configurable", True)

            return descriptor

        obj_constructor.set("keys", keys_fn)
        obj_constructor.set("values", values_fn)
        obj_constructor.set("entries", entries_fn)
        obj_constructor.set("assign", assign_fn)
        obj_constructor.set("getPrototypeOf", get_prototype_of)
        obj_constructor.set("setPrototypeOf", set_prototype_of)
        obj_constructor.set("defineProperty", define_property)
        obj_constructor.set("defineProperties", define_properties)
        obj_constructor.set("create", create_fn)
        obj_constructor.set("getOwnPropertyDescriptor", get_own_property_descriptor)
        obj_constructor.set("prototype", object_prototype)

        return obj_constructor

    def _create_array_constructor(self) -> JSCallableObject:
        """Create the Array constructor with static methods."""
        # Create Array.prototype (inherits from Object.prototype)
        array_prototype = JSArray()
        array_prototype._prototype = self._object_prototype

        def array_constructor(*args):
            if len(args) == 1 and isinstance(args[0], (int, float)):
                arr = JSArray(int(args[0]))
            else:
                arr = JSArray()
                for arg in args:
                    arr.push(arg)
            arr._prototype = array_prototype
            return arr

        arr_constructor = JSCallableObject(array_constructor)
        arr_constructor._prototype = array_prototype
        array_prototype.set("constructor", arr_constructor)

        # Store for other uses
        self._array_prototype = array_prototype

        # Array.prototype.sort() - sort in-place
        def array_sort(this, *args):
            if not isinstance(this, JSArray):
                return this
            comparator = args[0] if args else None

            # Default string comparison
            def default_compare(a, b):
                # undefined values sort to the end
                if a is UNDEFINED and b is UNDEFINED:
                    return 0
                if a is UNDEFINED:
                    return 1
                if b is UNDEFINED:
                    return -1
                # Convert to strings and compare
                str_a = to_string(a)
                str_b = to_string(b)
                if str_a < str_b:
                    return -1
                if str_a > str_b:
                    return 1
                return 0

            def compare_fn(a, b):
                if comparator and callable(comparator):
                    if isinstance(comparator, JSFunction):
                        result = self._call_function(comparator, [a, b])
                    else:
                        result = comparator(a, b)
                    # Convert to integer for cmp_to_key
                    num = to_number(result) if result is not UNDEFINED else 0
                    return int(num) if isinstance(num, (int, float)) else 0
                return default_compare(a, b)

            # Sort using Python's sort with custom key
            from functools import cmp_to_key
            this._elements.sort(key=cmp_to_key(compare_fn))
            return this

        array_prototype.set("sort", JSBoundMethod(array_sort))

        # Array.isArray()
        def is_array(*args):
            obj = args[0] if args else UNDEFINED
            return isinstance(obj, JSArray)

        arr_constructor.set("isArray", is_array)

        return arr_constructor

    def _create_error_constructor(self, error_name: str) -> JSCallableObject:
        """Create an Error constructor (Error, TypeError, SyntaxError, etc.)."""
        # Add prototype first so it can be captured in closure
        error_prototype = JSObject()
        error_prototype.set("name", error_name)
        error_prototype.set("message", "")

        def error_constructor(*args):
            message = args[0] if args else UNDEFINED
            err = JSObject(error_prototype)  # Set prototype
            err.set("message", to_string(message) if message is not UNDEFINED else "")
            err.set("name", error_name)
            err.set("stack", "")  # Stack trace placeholder
            err.set("lineNumber", None)  # Will be set when error is thrown
            err.set("columnNumber", None)  # Will be set when error is thrown
            return err

        constructor = JSCallableObject(error_constructor)
        constructor._name = error_name

        error_prototype.set("constructor", constructor)
        constructor.set("prototype", error_prototype)

        return constructor

    def _create_math_object(self) -> JSObject:
        """Create the Math global object."""
        math_obj = JSObject()

        # Constants
        math_obj.set("PI", math.pi)
        math_obj.set("E", math.e)
        math_obj.set("LN2", math.log(2))
        math_obj.set("LN10", math.log(10))
        math_obj.set("LOG2E", 1 / math.log(2))
        math_obj.set("LOG10E", 1 / math.log(10))
        math_obj.set("SQRT2", math.sqrt(2))
        math_obj.set("SQRT1_2", math.sqrt(0.5))

        # Basic functions
        def abs_fn(*args):
            x = to_number(args[0]) if args else float('nan')
            return abs(x)

        def floor_fn(*args):
            x = to_number(args[0]) if args else float('nan')
            return math.floor(x)

        def ceil_fn(*args):
            x = to_number(args[0]) if args else float('nan')
            return math.ceil(x)

        def round_fn(*args):
            x = to_number(args[0]) if args else float('nan')
            # JavaScript-style round (round half towards positive infinity)
            return math.floor(x + 0.5)

        def trunc_fn(*args):
            x = to_number(args[0]) if args else float('nan')
            return math.trunc(x)

        def min_fn(*args):
            if not args:
                return float('inf')
            nums = [to_number(a) for a in args]
            return min(nums)

        def max_fn(*args):
            if not args:
                return float('-inf')
            nums = [to_number(a) for a in args]
            return max(nums)

        def pow_fn(*args):
            x = to_number(args[0]) if args else float('nan')
            y = to_number(args[1]) if len(args) > 1 else float('nan')
            return math.pow(x, y)

        def sqrt_fn(*args):
            x = to_number(args[0]) if args else float('nan')
            if x < 0:
                return float('nan')
            return math.sqrt(x)

        def sin_fn(*args):
            x = to_number(args[0]) if args else float('nan')
            return math.sin(x)

        def cos_fn(*args):
            x = to_number(args[0]) if args else float('nan')
            return math.cos(x)

        def tan_fn(*args):
            x = to_number(args[0]) if args else float('nan')
            return math.tan(x)

        def asin_fn(*args):
            x = to_number(args[0]) if args else float('nan')
            if x < -1 or x > 1:
                return float('nan')
            return math.asin(x)

        def acos_fn(*args):
            x = to_number(args[0]) if args else float('nan')
            if x < -1 or x > 1:
                return float('nan')
            return math.acos(x)

        def atan_fn(*args):
            x = to_number(args[0]) if args else float('nan')
            return math.atan(x)

        def atan2_fn(*args):
            y = to_number(args[0]) if args else float('nan')
            x = to_number(args[1]) if len(args) > 1 else float('nan')
            return math.atan2(y, x)

        def log_fn(*args):
            x = to_number(args[0]) if args else float('nan')
            if x <= 0:
                return float('-inf') if x == 0 else float('nan')
            return math.log(x)

        def exp_fn(*args):
            x = to_number(args[0]) if args else float('nan')
            return math.exp(x)

        def random_fn(*args):
            return random.random()

        def sign_fn(*args):
            x = to_number(args[0]) if args else float('nan')
            if math.isnan(x):
                return float('nan')
            if x > 0:
                return 1
            if x < 0:
                return -1
            return 0

        def imul_fn(*args):
            # 32-bit integer multiplication
            a = int(to_number(args[0])) if args else 0
            b = int(to_number(args[1])) if len(args) > 1 else 0
            # Convert to 32-bit signed integers
            a = a & 0xFFFFFFFF
            b = b & 0xFFFFFFFF
            if a >= 0x80000000:
                a -= 0x100000000
            if b >= 0x80000000:
                b -= 0x100000000
            result = (a * b) & 0xFFFFFFFF
            if result >= 0x80000000:
                result -= 0x100000000
            return result

        def fround_fn(*args):
            # Convert to 32-bit float
            import struct
            x = to_number(args[0]) if args else float('nan')
            # Pack as 32-bit float and unpack as 64-bit
            packed = struct.pack('f', x)
            return struct.unpack('f', packed)[0]

        def clz32_fn(*args):
            # Count leading zeros in 32-bit integer
            x = int(to_number(args[0])) if args else 0
            x = x & 0xFFFFFFFF
            if x == 0:
                return 32
            count = 0
            while (x & 0x80000000) == 0:
                count += 1
                x <<= 1
            return count

        def hypot_fn(*args):
            if not args:
                return 0
            nums = [to_number(a) for a in args]
            return math.hypot(*nums)

        def cbrt_fn(*args):
            x = to_number(args[0]) if args else float('nan')
            if x < 0:
                return -(-x) ** (1/3)
            return x ** (1/3)

        def log2_fn(*args):
            x = to_number(args[0]) if args else float('nan')
            return math.log2(x) if x > 0 else float('nan')

        def log10_fn(*args):
            x = to_number(args[0]) if args else float('nan')
            return math.log10(x) if x > 0 else float('nan')

        def expm1_fn(*args):
            x = to_number(args[0]) if args else float('nan')
            return math.expm1(x)

        def log1p_fn(*args):
            x = to_number(args[0]) if args else float('nan')
            return math.log1p(x) if x > -1 else float('nan')

        # Set all methods
        math_obj.set("abs", abs_fn)
        math_obj.set("floor", floor_fn)
        math_obj.set("ceil", ceil_fn)
        math_obj.set("round", round_fn)
        math_obj.set("trunc", trunc_fn)
        math_obj.set("min", min_fn)
        math_obj.set("max", max_fn)
        math_obj.set("pow", pow_fn)
        math_obj.set("sqrt", sqrt_fn)
        math_obj.set("sin", sin_fn)
        math_obj.set("cos", cos_fn)
        math_obj.set("tan", tan_fn)
        math_obj.set("asin", asin_fn)
        math_obj.set("acos", acos_fn)
        math_obj.set("atan", atan_fn)
        math_obj.set("atan2", atan2_fn)
        math_obj.set("log", log_fn)
        math_obj.set("exp", exp_fn)
        math_obj.set("random", random_fn)
        math_obj.set("sign", sign_fn)
        math_obj.set("imul", imul_fn)
        math_obj.set("fround", fround_fn)
        math_obj.set("clz32", clz32_fn)
        math_obj.set("hypot", hypot_fn)
        math_obj.set("cbrt", cbrt_fn)
        math_obj.set("log2", log2_fn)
        math_obj.set("log10", log10_fn)
        math_obj.set("expm1", expm1_fn)
        math_obj.set("log1p", log1p_fn)

        return math_obj

    def _create_json_object(self) -> JSObject:
        """Create the JSON global object."""
        json_obj = JSObject()
        ctx = self  # Reference for closures

        def parse_fn(*args):
            text = to_string(args[0]) if args else ""
            try:
                py_value = json.loads(text)
                return ctx._to_js(py_value)
            except json.JSONDecodeError as e:
                from .errors import JSSyntaxError
                raise JSSyntaxError(f"JSON.parse: {e}")

        def stringify_fn(*args):
            value = args[0] if args else UNDEFINED
            # Convert JS value to Python for json.dumps, handling undefined specially
            def to_json_value(v):
                if v is UNDEFINED:
                    return None  # Will be filtered out for object properties
                if v is NULL:
                    return None
                if isinstance(v, bool):
                    return v
                if isinstance(v, (int, float)):
                    return v
                if isinstance(v, str):
                    return v
                if isinstance(v, JSArray):
                    # For arrays, undefined becomes null
                    return [None if elem is UNDEFINED else to_json_value(elem) for elem in v._elements]
                if isinstance(v, JSObject):
                    # For objects, skip undefined values
                    result = {}
                    for k, val in v._properties.items():
                        if val is not UNDEFINED:
                            result[k] = to_json_value(val)
                    return result
                return None

            py_value = to_json_value(value)
            try:
                return json.dumps(py_value, separators=(',', ':'))
            except (TypeError, ValueError) as e:
                from .errors import JSTypeError
                raise JSTypeError(f"JSON.stringify: {e}")

        json_obj.set("parse", parse_fn)
        json_obj.set("stringify", stringify_fn)

        return json_obj

    def _create_number_constructor(self) -> JSCallableObject:
        """Create the Number constructor with static methods."""

        def number_call(*args):
            """Convert argument to a number."""
            if not args:
                return 0
            return to_number(args[0])

        num_constructor = JSCallableObject(number_call)

        def isNaN_fn(*args):
            x = args[0] if args else UNDEFINED
            # Number.isNaN only returns true for actual NaN
            if not isinstance(x, (int, float)):
                return False
            return math.isnan(x)

        def isFinite_fn(*args):
            x = args[0] if args else UNDEFINED
            if not isinstance(x, (int, float)):
                return False
            return not (math.isnan(x) or math.isinf(x))

        def isInteger_fn(*args):
            x = args[0] if args else UNDEFINED
            if not isinstance(x, (int, float)):
                return False
            if math.isnan(x) or math.isinf(x):
                return False
            return x == int(x)

        def parseInt_fn(*args):
            s = to_string(args[0]) if args else ""
            radix = int(to_number(args[1])) if len(args) > 1 else 10
            if radix == 0:
                radix = 10
            s = s.strip()
            if not s:
                return float('nan')
            # Handle leading sign
            sign = 1
            if s.startswith('-'):
                sign = -1
                s = s[1:]
            elif s.startswith('+'):
                s = s[1:]
            # Handle 0x prefix for hex
            if s.startswith('0x') or s.startswith('0X'):
                radix = 16
                s = s[2:]
            # Parse digits
            result = 0
            found = False
            for ch in s:
                if ch.isdigit():
                    digit = ord(ch) - ord('0')
                elif ch.isalpha():
                    digit = ord(ch.lower()) - ord('a') + 10
                else:
                    break
                if digit >= radix:
                    break
                result = result * radix + digit
                found = True
            if not found:
                return float('nan')
            return sign * result

        def parseFloat_fn(*args):
            s = to_string(args[0]) if args else ""
            s = s.strip()
            if not s:
                return float('nan')
            # Find the longest valid float prefix
            i = 0
            has_dot = False
            has_exp = False
            if s[i] in '+-':
                i += 1
            while i < len(s):
                if s[i].isdigit():
                    i += 1
                elif s[i] == '.' and not has_dot:
                    has_dot = True
                    i += 1
                elif s[i] in 'eE' and not has_exp:
                    has_exp = True
                    i += 1
                    if i < len(s) and s[i] in '+-':
                        i += 1
                else:
                    break
            if i == 0:
                return float('nan')
            try:
                return float(s[:i])
            except ValueError:
                return float('nan')

        num_constructor.set("isNaN", isNaN_fn)
        num_constructor.set("isFinite", isFinite_fn)
        num_constructor.set("isInteger", isInteger_fn)
        num_constructor.set("parseInt", parseInt_fn)
        num_constructor.set("parseFloat", parseFloat_fn)

        return num_constructor

    def _create_string_constructor(self) -> JSCallableObject:
        """Create the String constructor with static methods."""

        def string_call(*args):
            """Convert argument to a string."""
            if not args:
                return ""
            return to_string(args[0])

        string_constructor = JSCallableObject(string_call)

        def fromCharCode_fn(*args):
            """String.fromCharCode - create string from char codes."""
            return "".join(chr(int(to_number(arg))) for arg in args)

        string_constructor.set("fromCharCode", fromCharCode_fn)

        return string_constructor

    def _create_boolean_constructor(self) -> JSCallableObject:
        """Create the Boolean constructor."""

        def boolean_call(*args):
            """Convert argument to a boolean."""
            if not args:
                return False
            val = args[0]
            # JavaScript truthiness rules
            if val is UNDEFINED or val is NULL:
                return False
            if isinstance(val, bool):
                return val
            if isinstance(val, (int, float)):
                if math.isnan(val):
                    return False
                return val != 0
            if isinstance(val, str):
                return len(val) > 0
            # Objects are always truthy
            return True

        boolean_constructor = JSCallableObject(boolean_call)
        return boolean_constructor

    def _create_date_constructor(self) -> JSObject:
        """Create the Date constructor with static methods."""
        date_constructor = JSObject()

        def now_fn(*args):
            return int(time.time() * 1000)

        date_constructor.set("now", now_fn)

        return date_constructor

    def _create_regexp_constructor(self) -> JSCallableObject:
        """Create the RegExp constructor."""
        def regexp_constructor_fn(*args):
            pattern = to_string(args[0]) if args else ""
            flags = to_string(args[1]) if len(args) > 1 else ""
            return JSRegExp(pattern, flags)

        return JSCallableObject(regexp_constructor_fn)

    def _create_function_constructor(self) -> JSCallableObject:
        """Create the Function constructor for dynamic function creation."""
        from .values import JSFunction

        def function_constructor_fn(*args):
            if not args:
                # new Function() - empty function
                body = ""
                params = []
            else:
                # All args are strings
                str_args = [to_string(arg) for arg in args]
                # Last argument is the body, rest are parameter names
                body = str_args[-1]
                params = str_args[:-1]

            # Create a function expression to parse
            param_str = ", ".join(params)
            source = f"(function({param_str}) {{ {body} }})"

            # Parse and compile
            try:
                parser = Parser(source)
                ast = parser.parse()
                compiler = Compiler()
                bytecode_module = compiler.compile(ast)

                # The result should be a function expression wrapped in a program
                # We need to extract the function from the bytecode
                # Execute the expression to get the function object
                vm = VM(self.memory_limit, self.time_limit)
                vm.globals = self._globals
                result = vm.run(bytecode_module)

                if isinstance(result, JSFunction):
                    return result
                else:
                    # Fallback: return a simple empty function
                    return JSFunction("anonymous", params, bytes(), {})
            except Exception as e:
                from .errors import JSError
                raise JSError(f"SyntaxError: {str(e)}")

        fn_constructor = JSCallableObject(function_constructor_fn)

        # Function.prototype - add basic methods
        fn_prototype = JSObject()

        # These are implemented in VM's _get_property for JSFunction
        # but we still set them here for completeness
        fn_constructor.set("prototype", fn_prototype)

        return fn_constructor

    def _create_typed_array_constructor(self, name: str) -> JSCallableObject:
        """Create a typed array constructor (Int32Array, Uint8Array, etc.)."""
        from .values import (
            JSInt32Array, JSUint32Array, JSFloat64Array, JSFloat32Array,
            JSUint8Array, JSInt8Array, JSInt16Array, JSUint16Array,
            JSUint8ClampedArray, JSArrayBuffer, JSArray
        )

        type_classes = {
            "Int32Array": JSInt32Array,
            "Uint32Array": JSUint32Array,
            "Float64Array": JSFloat64Array,
            "Float32Array": JSFloat32Array,
            "Uint8Array": JSUint8Array,
            "Int8Array": JSInt8Array,
            "Int16Array": JSInt16Array,
            "Uint16Array": JSUint16Array,
            "Uint8ClampedArray": JSUint8ClampedArray,
        }

        array_class = type_classes[name]

        def constructor_fn(*args):
            if not args:
                return array_class(0)
            arg = args[0]
            if isinstance(arg, (int, float)):
                # new Int32Array(length)
                return array_class(int(arg))
            elif isinstance(arg, JSArrayBuffer):
                # new Int32Array(buffer, byteOffset?, length?)
                buffer = arg
                byte_offset = int(args[1]) if len(args) > 1 else 0
                element_size = array_class._element_size

                if len(args) > 2:
                    length = int(args[2])
                else:
                    length = (buffer.byteLength - byte_offset) // element_size

                result = array_class(length)
                result._buffer = buffer
                result._byte_offset = byte_offset

                # Read values from buffer
                import struct
                for i in range(length):
                    offset = byte_offset + i * element_size
                    if name in ("Float32Array", "Float64Array"):
                        fmt = 'f' if element_size == 4 else 'd'
                        val = struct.unpack(fmt, bytes(buffer._data[offset:offset+element_size]))[0]
                    else:
                        val = int.from_bytes(buffer._data[offset:offset+element_size], 'little', signed='Int' in name)
                    result._data[i] = result._coerce_value(val)

                return result
            elif isinstance(arg, JSArray):
                # new Int32Array([1, 2, 3])
                length = arg.length
                result = array_class(length)
                for i in range(length):
                    result.set_index(i, arg.get_index(i))
                return result
            return array_class(0)

        constructor = JSCallableObject(constructor_fn)
        constructor._name = name
        return constructor

    def _create_arraybuffer_constructor(self) -> JSCallableObject:
        """Create the ArrayBuffer constructor."""
        from .values import JSArrayBuffer

        def constructor_fn(*args):
            length = int(args[0]) if args else 0
            return JSArrayBuffer(length)

        constructor = JSCallableObject(constructor_fn)
        constructor._name = "ArrayBuffer"
        return constructor

    def _create_eval_function(self):
        """Create the global eval function."""
        ctx = self  # Reference for closure

        def eval_fn(*args):
            if not args:
                return UNDEFINED
            code = args[0]
            if not isinstance(code, str):
                # If not a string, return the argument unchanged
                return code

            try:
                parser = Parser(code)
                ast = parser.parse()
                compiler = Compiler()
                bytecode_module = compiler.compile(ast)

                vm = VM(ctx.memory_limit, ctx.time_limit)
                vm.globals = ctx._globals
                return vm.run(bytecode_module)
            except Exception as e:
                from .errors import JSError
                raise JSError(f"EvalError: {str(e)}")

        return eval_fn

    def _global_isnan(self, *args) -> bool:
        """Global isNaN - converts argument to number first."""
        x = to_number(args[0]) if args else float('nan')
        return math.isnan(x)

    def _global_isfinite(self, *args) -> bool:
        """Global isFinite - converts argument to number first."""
        x = to_number(args[0]) if args else float('nan')
        return not (math.isnan(x) or math.isinf(x))

    def _global_parseint(self, *args):
        """Global parseInt."""
        s = to_string(args[0]) if args else ""
        radix = int(to_number(args[1])) if len(args) > 1 else 10
        if radix == 0:
            radix = 10
        s = s.strip()
        if not s:
            return float('nan')
        sign = 1
        if s.startswith('-'):
            sign = -1
            s = s[1:]
        elif s.startswith('+'):
            s = s[1:]
        if s.startswith('0x') or s.startswith('0X'):
            radix = 16
            s = s[2:]
        result = 0
        found = False
        for ch in s:
            if ch.isdigit():
                digit = ord(ch) - ord('0')
            elif ch.isalpha():
                digit = ord(ch.lower()) - ord('a') + 10
            else:
                break
            if digit >= radix:
                break
            result = result * radix + digit
            found = True
        if not found:
            return float('nan')
        return sign * result

    def _global_parsefloat(self, *args):
        """Global parseFloat."""
        s = to_string(args[0]) if args else ""
        s = s.strip()
        if not s:
            return float('nan')

        # Handle Infinity
        if s.startswith("Infinity"):
            return float('inf')
        if s.startswith("-Infinity"):
            return float('-inf')
        if s.startswith("+Infinity"):
            return float('inf')

        i = 0
        has_dot = False
        has_exp = False
        if s[i] in '+-':
            i += 1
        while i < len(s):
            if s[i].isdigit():
                i += 1
            elif s[i] == '.' and not has_dot:
                has_dot = True
                i += 1
            elif s[i] in 'eE' and not has_exp:
                has_exp = True
                i += 1
                if i < len(s) and s[i] in '+-':
                    i += 1
            else:
                break
        if i == 0:
            return float('nan')
        try:
            return float(s[:i])
        except ValueError:
            return float('nan')

    def eval(self, code: str) -> Any:
        """Evaluate JavaScript code and return the result.

        Args:
            code: JavaScript source code to evaluate

        Returns:
            The result of evaluating the code, converted to Python types

        Raises:
            JSSyntaxError: If the code has syntax errors
            JSError: If a JavaScript error is thrown
            MemoryLimitError: If memory limit is exceeded
            TimeLimitError: If time limit is exceeded
        """
        # Parse the code
        parser = Parser(code)
        ast = parser.parse()

        # Compile to bytecode
        compiler = Compiler()
        compiled = compiler.compile(ast)

        # Execute
        vm = VM(memory_limit=self.memory_limit, time_limit=self.time_limit)

        # Share globals with VM (don't copy - allows nested eval to modify globals)
        vm.globals = self._globals

        result = vm.run(compiled)

        return self._to_python(result)

    def _call_function(self, func: JSFunction, args: list) -> Any:
        """Call a JavaScript function with the given arguments.

        This is used internally to invoke JSFunction objects from Python code.
        """
        vm = VM(memory_limit=self.memory_limit, time_limit=self.time_limit)
        vm.globals.update(self._globals)
        result = vm._call_callback(func, args, UNDEFINED)
        self._globals.update(vm.globals)
        return result

    def get(self, name: str) -> Any:
        """Get a global variable.

        Args:
            name: Variable name

        Returns:
            The value of the variable, converted to Python types
        """
        value = self._globals.get(name, UNDEFINED)
        return self._to_python(value)

    def set(self, name: str, value: Any) -> None:
        """Set a global variable.

        Args:
            name: Variable name
            value: Value to set (Python value, will be converted)
        """
        self._globals[name] = self._to_js(value)

    def _to_python(self, value: JSValue) -> Any:
        """Convert a JavaScript value to Python."""
        if value is UNDEFINED:
            return None
        if value is NULL:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            return value
        if isinstance(value, JSArray):
            return [self._to_python(elem) for elem in value._elements]
        if isinstance(value, JSObject):
            return {k: self._to_python(v) for k, v in value._properties.items()}
        return value

    def _to_js(self, value: Any) -> JSValue:
        """Convert a Python value to JavaScript."""
        if value is None:
            return NULL
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            return value
        # Already JS values - pass through
        if isinstance(value, (JSObject, JSFunction, JSCallableObject)):
            return value
        if value is UNDEFINED:
            return value
        if isinstance(value, list):
            arr = JSArray()
            for elem in value:
                arr.push(self._to_js(elem))
            return arr
        if isinstance(value, dict):
            obj = JSObject()
            for k, v in value.items():
                obj.set(str(k), self._to_js(v))
            return obj
        # Python callables become JS functions
        if callable(value):
            return value
        return UNDEFINED
