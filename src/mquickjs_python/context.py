"""JavaScript execution context."""

from typing import Any, Dict, Optional

from .parser import Parser
from .compiler import Compiler
from .vm import VM
from .values import UNDEFINED, NULL, JSValue, JSObject, JSArray, to_string
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
        self._globals["Object"] = self._object_constructor
        self._globals["Array"] = self._array_constructor

    def _console_log(self, *args: JSValue) -> None:
        """Console.log implementation."""
        print(" ".join(to_string(arg) for arg in args))

    def _object_constructor(self) -> JSObject:
        """Object constructor."""
        return JSObject()

    def _array_constructor(self, *args: JSValue) -> JSArray:
        """Array constructor."""
        if len(args) == 1 and isinstance(args[0], (int, float)):
            return JSArray(int(args[0]))
        arr = JSArray()
        for arg in args:
            arr.push(arg)
        return arr

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
