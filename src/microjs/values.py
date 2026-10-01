"""JavaScript value types."""

from typing import Any, Dict, List, Optional, Sequence, Union, TYPE_CHECKING
import contextvars
import math

from .errors import JSRangeError
from .numbers import number_to_string, string_to_number

if TYPE_CHECKING:
    from .context import Context

# The VM executing on this thread. Converting an object to a primitive can
# call its valueOf() or toString(), which needs the running VM, as does
# accounting for memory and time inside native functions.
CURRENT_VM: contextvars.ContextVar = contextvars.ContextVar(
    "microjs_current_vm", default=None
)

# The longest string a script can build (V8's limit) and the largest array
# length; exceeding either is a RangeError whatever the memory limit.
MAX_STRING_LENGTH = 2**29 - 24
MAX_ARRAY_LENGTH = 2**32 - 1


def charge_memory(nbytes: int) -> None:
    """Account for allocating about nbytes against the memory limit.

    Call before allocating: raises MemoryLimitError if it will not fit.
    """
    vm = CURRENT_VM.get()
    if vm is not None:
        vm.charge(nbytes)


def check_deadline() -> None:
    """Raise TimeLimitError if the running script is out of time."""
    vm = CURRENT_VM.get()
    if vm is not None:
        vm.check_deadline()


def reserve_string(length: int) -> None:
    """Check that a string of this length may be created, before creating it."""
    if length > MAX_STRING_LENGTH:
        raise JSRangeError("Invalid string length")
    charge_memory(length + 49)


def to_array_length(value: "JSValue") -> int:
    """Validate a new array length, as new Array(n) and length = n do."""
    n = to_number(value)
    if n != n or n < 0 or n > MAX_ARRAY_LENGTH or n != int(n):
        raise JSRangeError("Invalid array length")
    return int(n)


class OutputBudget:
    """Checks a string being assembled from parts as it grows.

    Natives that build their result piece by piece (join, replace, ...)
    add each piece's length; the total is checked against the maximum
    string length and the memory limit each time it doubles, and the
    deadline is checked every few thousand pieces.
    """

    def __init__(self) -> None:
        self.length = 0
        self._pieces = 0
        self._next_check = 4096

    def add(self, length: int) -> None:
        self.length += length
        self._pieces += 1
        if self.length >= self._next_check:
            reserve_string(self.length)
            self._next_check = self.length * 2
        if not self._pieces & 4095:
            check_deadline()

    def finish(self) -> None:
        """Check the complete length, just before joining the parts."""
        reserve_string(self.length)


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
    # JSCallableObject (like Object, Array constructors) should be "function"
    if isinstance(value, JSObject) and hasattr(value, "_call_fn"):
        return "function"
    if isinstance(value, JSObject):
        return "object"
    # Python callable (including JSBoundMethod)
    if callable(value):
        return "function"
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
    """Convert a JavaScript value to number (ToNumber)."""
    if value is UNDEFINED:
        return float("nan")
    if value is NULL:
        return 0
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return string_to_number(value)
    if isinstance(value, JSObject):
        vm = CURRENT_VM.get()
        if vm is not None:
            return to_number(vm._to_primitive(value, "number"))
    return float("nan")


def to_string(value: JSValue) -> str:
    """Convert a JavaScript value to string (ToString)."""
    if value is UNDEFINED:
        return "undefined"
    if value is NULL:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return number_to_string(value)
    if isinstance(value, str):
        return value
    if isinstance(value, JSObject):
        vm = CURRENT_VM.get()
        if vm is not None:
            return to_string(vm._to_primitive(value, "string"))
    return "[object Object]"


class JSObject:
    """JavaScript object."""

    def __init__(self, prototype: Optional["JSObject"] = None):
        self._properties: Dict[str, JSValue] = {}
        self._getters: Dict[str, Any] = {}  # property name -> getter function
        self._setters: Dict[str, Any] = {}  # property name -> setter function
        self._prototype = prototype

    def get(self, key: str) -> JSValue:
        """Get a property value (does not invoke getters - use get_property for that)."""
        if key in self._properties:
            return self._properties[key]
        if self._prototype is not None:
            return self._prototype.get(key)
        return UNDEFINED

    def get_getter(self, key: str) -> Optional[Any]:
        """Get the getter function for a property, if any."""
        if key in self._getters:
            return self._getters[key]
        if self._prototype is not None:
            return self._prototype.get_getter(key)
        return None

    def get_setter(self, key: str) -> Optional[Any]:
        """Get the setter function for a property, if any."""
        if key in self._setters:
            return self._setters[key]
        if self._prototype is not None:
            return self._prototype.get_setter(key)
        return None

    def define_getter(self, key: str, getter: Any) -> None:
        """Define a getter for a property."""
        self._getters[key] = getter

    def define_setter(self, key: str, setter: Any) -> None:
        """Define a setter for a property."""
        self._setters[key] = setter

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


def grow_array(elements: List["JSValue"], count: int) -> None:
    """Append count undefined elements, checking memory and time as it goes."""
    charge_memory(8 * count)
    while count > 0:
        chunk = min(count, 1 << 20)
        elements.extend([UNDEFINED] * chunk)
        count -= chunk
        check_deadline()


class JSArray(JSObject):
    """JavaScript array."""

    def __init__(self, length: int = 0):
        super().__init__()
        self._elements: List[JSValue] = []
        if length:
            grow_array(self._elements, length)

    @property
    def length(self) -> int:
        return len(self._elements)

    @length.setter
    def length(self, value: int) -> None:
        if value < len(self._elements):
            del self._elements[value:]
        else:
            grow_array(self._elements, value - len(self._elements))

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
        bytecode: Sequence[int],
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


class JSBoundMethod:
    """A method that expects 'this' as the first argument when called."""

    def __init__(self, fn):
        self._fn = fn

    def __call__(self, this_val, *args):
        return self._fn(this_val, *args)


class JSTypedArray(JSObject):
    """Base class for JavaScript typed arrays."""

    # Subclasses override these
    _element_size = 1  # bytes per element
    _type_name = "TypedArray"
    _signed = False

    def __init__(self, length: int = 0):
        super().__init__()
        self._data = [0] * length
        self._buffer = None
        self._byte_offset = 0

    @property
    def length(self) -> int:
        return len(self._data)

    def get_index(self, index: int):
        if 0 <= index < len(self._data):
            if self._buffer is not None:
                # Read from buffer
                return self._read_from_buffer(index)
            return self._data[index]
        return UNDEFINED

    def set_index(self, index: int, value) -> None:
        if 0 <= index < len(self._data):
            coerced = self._coerce_value(value)
            self._data[index] = coerced
            if self._buffer is not None:
                # Write to buffer
                self._write_to_buffer(index, coerced)

    def _read_from_buffer(self, index: int):
        """Read a value from the underlying buffer."""
        import struct

        offset = self._byte_offset + index * self._element_size
        data = bytes(self._buffer._data[offset : offset + self._element_size])
        if len(data) < self._element_size:
            return 0
        return self._unpack_value(data)

    def _write_to_buffer(self, index: int, value) -> None:
        """Write a value to the underlying buffer."""
        import struct

        offset = self._byte_offset + index * self._element_size
        packed = self._pack_value(value)
        for i, b in enumerate(packed):
            self._buffer._data[offset + i] = b

    def _unpack_value(self, data: bytes):
        """Unpack bytes to a value. Override in subclasses for float types."""
        return int.from_bytes(data, "little", signed=self._signed)

    def _pack_value(self, value) -> bytes:
        """Pack a value to bytes. Override in subclasses for float types."""
        return int(value).to_bytes(self._element_size, "little", signed=self._signed)

    def _coerce_value(self, value):
        """Coerce value to the appropriate type. Override in subclasses."""
        return int(value) if isinstance(value, (int, float)) else 0

    def __repr__(self) -> str:
        return f"{self._type_name}({self._data})"


class JSInt32Array(JSTypedArray):
    """JavaScript Int32Array."""

    _element_size = 4
    _type_name = "Int32Array"
    _signed = True

    def _coerce_value(self, value):
        """Coerce to signed 32-bit integer."""
        if isinstance(value, (int, float)):
            v = int(value)
            # Handle overflow to signed 32-bit
            v = v & 0xFFFFFFFF
            if v >= 0x80000000:
                v -= 0x100000000
            return v
        return 0


class JSUint32Array(JSTypedArray):
    """JavaScript Uint32Array."""

    _element_size = 4
    _type_name = "Uint32Array"
    _signed = False

    def _coerce_value(self, value):
        """Coerce to unsigned 32-bit integer."""
        if isinstance(value, (int, float)):
            return int(value) & 0xFFFFFFFF
        return 0


class JSFloat64Array(JSTypedArray):
    """JavaScript Float64Array."""

    _element_size = 8
    _type_name = "Float64Array"
    _signed = False

    def _coerce_value(self, value):
        """Coerce to float."""
        if isinstance(value, (int, float)):
            return float(value)
        return 0.0

    def _unpack_value(self, data: bytes):
        """Unpack bytes to float64."""
        import struct

        return struct.unpack("<d", data)[0]

    def _pack_value(self, value) -> bytes:
        """Pack float64 to bytes."""
        import struct

        return struct.pack("<d", float(value))


class JSUint8Array(JSTypedArray):
    """JavaScript Uint8Array."""

    _element_size = 1
    _type_name = "Uint8Array"
    _signed = False

    def _coerce_value(self, value):
        """Coerce to unsigned 8-bit integer."""
        if isinstance(value, (int, float)):
            return int(value) & 0xFF
        return 0


class JSInt8Array(JSTypedArray):
    """JavaScript Int8Array."""

    _element_size = 1
    _type_name = "Int8Array"
    _signed = True

    def _coerce_value(self, value):
        """Coerce to signed 8-bit integer."""
        if isinstance(value, (int, float)):
            v = int(value) & 0xFF
            if v >= 0x80:
                v -= 0x100
            return v
        return 0


class JSInt16Array(JSTypedArray):
    """JavaScript Int16Array."""

    _element_size = 2
    _type_name = "Int16Array"
    _signed = True

    def _coerce_value(self, value):
        """Coerce to signed 16-bit integer."""
        if isinstance(value, (int, float)):
            v = int(value) & 0xFFFF
            if v >= 0x8000:
                v -= 0x10000
            return v
        return 0


class JSUint16Array(JSTypedArray):
    """JavaScript Uint16Array."""

    _element_size = 2
    _type_name = "Uint16Array"
    _signed = False

    def _coerce_value(self, value):
        """Coerce to unsigned 16-bit integer."""
        if isinstance(value, (int, float)):
            return int(value) & 0xFFFF
        return 0


class JSUint8ClampedArray(JSTypedArray):
    """JavaScript Uint8ClampedArray."""

    _element_size = 1
    _type_name = "Uint8ClampedArray"

    def _coerce_value(self, value):
        """Coerce to clamped unsigned 8-bit integer (0-255)."""
        if isinstance(value, (int, float)):
            # Round half to even for 0.5 values
            v = round(value)
            # Clamp to 0-255
            if v < 0:
                return 0
            if v > 255:
                return 255
            return v
        return 0


class JSFloat32Array(JSTypedArray):
    """JavaScript Float32Array."""

    _element_size = 4
    _type_name = "Float32Array"
    _signed = False

    def _coerce_value(self, value):
        """Coerce to 32-bit float."""
        import struct

        if isinstance(value, (int, float)):
            # Convert to float32 and back to simulate precision loss
            packed = struct.pack("<f", float(value))
            return struct.unpack("<f", packed)[0]
        return 0.0

    def _unpack_value(self, data: bytes):
        """Unpack bytes to float32."""
        import struct

        return struct.unpack("<f", data)[0]

    def _pack_value(self, value) -> bytes:
        """Pack float32 to bytes."""
        import struct

        return struct.pack("<f", float(value))


class JSArrayBuffer(JSObject):
    """JavaScript ArrayBuffer - raw binary data buffer."""

    def __init__(self, byte_length: int = 0):
        super().__init__()
        self._data = bytearray(byte_length)

    @property
    def byteLength(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"ArrayBuffer({self.byteLength})"
