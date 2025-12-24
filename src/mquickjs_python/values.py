"""JavaScript value types."""

from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING
import math

if TYPE_CHECKING:
    from .context import JSContext


class JSUndefined:
    """JavaScript undefined value (singleton)."""

    _instance: Optional["JSUndefined"] = None

    def __new__(cls) -> "JSUndefined":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "undefined"

    def __str__(self) -> str:
        return "undefined"

    def __bool__(self) -> bool:
        return False


class JSNull:
    """JavaScript null value (singleton)."""

    _instance: Optional["JSNull"] = None

    def __new__(cls) -> "JSNull":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "null"

    def __str__(self) -> str:
        return "null"

    def __bool__(self) -> bool:
        return False


# Singleton instances
UNDEFINED = JSUndefined()
NULL = JSNull()


# Type alias for JavaScript values
JSValue = Union[
    JSUndefined,
    JSNull,
    bool,
    int,
    float,
    str,
    "JSObject",
    "JSArray",
    "JSFunction",
]


def is_nan(value: Any) -> bool:
    """Check if value is NaN."""
    return isinstance(value, float) and math.isnan(value)


def is_infinity(value: Any) -> bool:
    """Check if value is positive or negative infinity."""
    return isinstance(value, float) and math.isinf(value)


def js_typeof(value: JSValue) -> str:
    """Return the JavaScript typeof for a value."""
    if value is UNDEFINED:
        return "undefined"
    if value is NULL:
        return "object"  # JavaScript quirk
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, JSFunction):
        return "function"
    if isinstance(value, JSObject):
        return "object"
    return "undefined"


def to_boolean(value: JSValue) -> bool:
    """Convert a JavaScript value to boolean."""
    if value is UNDEFINED or value is NULL:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if is_nan(value) or value == 0:
            return False
        return True
    if isinstance(value, str):
        return len(value) > 0
    # Objects are always truthy
    return True


def to_number(value: JSValue) -> Union[int, float]:
    """Convert a JavaScript value to number."""
    if value is UNDEFINED:
        return float("nan")
    if value is NULL:
        return 0
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        s = value.strip()
        if s == "":
            return 0
        try:
            if "." in s or "e" in s.lower():
                return float(s)
            if s.startswith("0x") or s.startswith("0X"):
                return int(s, 16)
            if s.startswith("0o") or s.startswith("0O"):
                return int(s, 8)
            if s.startswith("0b") or s.startswith("0B"):
                return int(s, 2)
            return int(s)
        except ValueError:
            return float("nan")
    # TODO: Handle objects with valueOf
    return float("nan")


def to_string(value: JSValue) -> str:
    """Convert a JavaScript value to string."""
    if value is UNDEFINED:
        return "undefined"
    if value is NULL:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if is_nan(value):
            return "NaN"
        if value == float("inf"):
            return "Infinity"
        if value == float("-inf"):
            return "-Infinity"
        # Handle -0
        if value == 0 and math.copysign(1, value) < 0:
            return "0"
        # Format float nicely
        s = repr(value)
        if s.endswith(".0"):
            return s[:-2]
        return s
    if isinstance(value, str):
        return value
    # TODO: Handle objects with toString
    return "[object Object]"


class JSObject:
    """JavaScript object."""

    def __init__(self, prototype: Optional["JSObject"] = None):
        self._properties: Dict[str, JSValue] = {}
        self._prototype = prototype

    def get(self, key: str) -> JSValue:
        """Get a property value."""
        if key in self._properties:
            return self._properties[key]
        if self._prototype is not None:
            return self._prototype.get(key)
        return UNDEFINED

    def set(self, key: str, value: JSValue) -> None:
        """Set a property value."""
        self._properties[key] = value

    def has(self, key: str) -> bool:
        """Check if object has own property."""
        return key in self._properties

    def delete(self, key: str) -> bool:
        """Delete a property."""
        if key in self._properties:
            del self._properties[key]
            return True
        return False

    def keys(self) -> List[str]:
        """Get own enumerable property keys."""
        return list(self._properties.keys())

    def __repr__(self) -> str:
        return f"JSObject({self._properties})"


class JSCallableObject(JSObject):
    """JavaScript object that is also callable (for constructors like Number, String, Boolean)."""

    def __init__(self, call_fn, prototype: Optional["JSObject"] = None):
        super().__init__(prototype)
        self._call_fn = call_fn

    def __call__(self, *args):
        return self._call_fn(*args)

    def __repr__(self) -> str:
        return f"JSCallableObject({self._properties})"


class JSArray(JSObject):
    """JavaScript array."""

    def __init__(self, length: int = 0):
        super().__init__()
        self._elements: List[JSValue] = [UNDEFINED] * length

    @property
    def length(self) -> int:
        return len(self._elements)

    @length.setter
    def length(self, value: int) -> None:
        if value < len(self._elements):
            self._elements = self._elements[:value]
        else:
            self._elements.extend([UNDEFINED] * (value - len(self._elements)))

    def get_index(self, index: int) -> JSValue:
        if 0 <= index < len(self._elements):
            return self._elements[index]
        return UNDEFINED

    def set_index(self, index: int, value: JSValue) -> None:
        if index < 0:
            raise IndexError("Negative array index")
        if index >= len(self._elements):
            # Extend array (stricter mode: only allow append at end)
            if index == len(self._elements):
                self._elements.append(value)
            else:
                raise IndexError("Array index out of bounds (stricter mode)")
        else:
            self._elements[index] = value

    def push(self, value: JSValue) -> int:
        self._elements.append(value)
        return len(self._elements)

    def pop(self) -> JSValue:
        if self._elements:
            return self._elements.pop()
        return UNDEFINED

    def __repr__(self) -> str:
        return f"JSArray({self._elements})"


class JSFunction:
    """JavaScript function (closure)."""

    def __init__(
        self,
        name: str,
        params: List[str],
        bytecode: bytes,
        closure_vars: Optional[Dict[str, JSValue]] = None,
    ):
        self.name = name
        self.params = params
        self.bytecode = bytecode
        self.closure_vars = closure_vars or {}

    def __repr__(self) -> str:
        return f"[Function: {self.name}]" if self.name else "[Function (anonymous)]"


class JSRegExp(JSObject):
    """JavaScript RegExp object."""

    def __init__(self, pattern: str, flags: str = "", poll_callback=None):
        super().__init__()
        from .regex import RegExp as InternalRegExp, MatchResult

        self._internal = InternalRegExp(pattern, flags, poll_callback)
        self._pattern = pattern
        self._flags = flags

        # Set properties
        self.set("source", pattern)
        self.set("flags", flags)
        self.set("global", "g" in flags)
        self.set("ignoreCase", "i" in flags)
        self.set("multiline", "m" in flags)
        self.set("dotAll", "s" in flags)
        self.set("unicode", "u" in flags)
        self.set("sticky", "y" in flags)
        self.set("lastIndex", 0)

    @property
    def lastIndex(self) -> int:
        return self.get("lastIndex") or 0

    @lastIndex.setter
    def lastIndex(self, value: int):
        self.set("lastIndex", value)
        self._internal.lastIndex = value

    def test(self, string: str) -> bool:
        """Test if the pattern matches the string."""
        self._internal.lastIndex = self.lastIndex
        result = self._internal.test(string)
        self.lastIndex = self._internal.lastIndex
        return result

    def exec(self, string: str):
        """Execute a search for a match."""
        self._internal.lastIndex = self.lastIndex
        result = self._internal.exec(string)
        self.lastIndex = self._internal.lastIndex

        if result is None:
            return NULL

        # Convert to JSArray with match result properties
        arr = JSArray()
        for i in range(len(result)):
            val = result[i]
            if val is None:
                arr._elements.append(UNDEFINED)
            else:
                arr._elements.append(val)

        # Add match result properties
        arr.set("index", result.index)
        arr.set("input", result.input)

        return arr

    def __repr__(self) -> str:
        return f"/{self._pattern}/{self._flags}"
