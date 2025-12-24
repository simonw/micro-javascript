"""JavaScript execution context."""

import json
import math
import random
import time
from typing import Any, Dict, Optional

from .parser import Parser
from .compiler import Compiler
from .vm import VM
from .values import UNDEFINED, NULL, JSValue, JSObject, JSArray, JSRegExp, to_string, to_number
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
        self._globals["Array"] = self._array_constructor
        self._globals["Error"] = self._error_constructor

        # Math object
        self._globals["Math"] = self._create_math_object()

        # JSON object
        self._globals["JSON"] = self._create_json_object()

        # Number constructor and methods
        self._globals["Number"] = self._create_number_constructor()

        # Date constructor
        self._globals["Date"] = self._create_date_constructor()

        # RegExp constructor
        self._globals["RegExp"] = self._create_regexp_constructor()

        # Global number functions
        self._globals["isNaN"] = self._global_isnan
        self._globals["isFinite"] = self._global_isfinite
        self._globals["parseInt"] = self._global_parseint
        self._globals["parseFloat"] = self._global_parsefloat

    def _console_log(self, *args: JSValue) -> None:
        """Console.log implementation."""
        print(" ".join(to_string(arg) for arg in args))

    def _create_object_constructor(self) -> JSObject:
        """Create the Object constructor with static methods."""
        # Create a callable object that acts as constructor
        obj_constructor = JSObject()

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

        obj_constructor.set("keys", keys_fn)
        obj_constructor.set("values", values_fn)
        obj_constructor.set("entries", entries_fn)
        obj_constructor.set("assign", assign_fn)

        return obj_constructor

    def _array_constructor(self, *args: JSValue) -> JSArray:
        """Array constructor."""
        if len(args) == 1 and isinstance(args[0], (int, float)):
            return JSArray(int(args[0]))
        arr = JSArray()
        for arg in args:
            arr.push(arg)
        return arr

    def _error_constructor(self, message: JSValue = UNDEFINED) -> JSObject:
        """Error constructor."""
        err = JSObject()
        err.set("message", to_string(message) if message is not UNDEFINED else "")
        err.set("name", "Error")
        return err

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
            # Convert JS value to Python for json.dumps
            py_value = ctx._to_python(value)
            try:
                return json.dumps(py_value, separators=(',', ':'))
            except (TypeError, ValueError) as e:
                from .errors import JSTypeError
                raise JSTypeError(f"JSON.stringify: {e}")

        json_obj.set("parse", parse_fn)
        json_obj.set("stringify", stringify_fn)

        return json_obj

    def _create_number_constructor(self) -> JSObject:
        """Create the Number constructor with static methods."""
        num_constructor = JSObject()

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

    def _create_date_constructor(self) -> JSObject:
        """Create the Date constructor with static methods."""
        date_constructor = JSObject()

        def now_fn(*args):
            return int(time.time() * 1000)

        date_constructor.set("now", now_fn)

        return date_constructor

    def _create_regexp_constructor(self) -> JSObject:
        """Create the RegExp constructor."""
        # The constructor is a callable that creates JSRegExp objects
        # This is wrapped in JSObject but the VM will call it specially

        def regexp_constructor_fn(*args):
            pattern = to_string(args[0]) if args else ""
            flags = to_string(args[1]) if len(args) > 1 else ""
            return JSRegExp(pattern, flags)

        # Return a callable marker
        regexp_constructor = JSObject()
        regexp_constructor._callable = regexp_constructor_fn
        return regexp_constructor

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

        # Set up globals
        vm.globals.update(self._globals)

        result = vm.run(compiled)

        # Update globals from VM
        self._globals.update(vm.globals)

        return self._to_python(result)

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
        return UNDEFINED
