"""JavaScript execution context."""

import json
import math
import random
import sys
import time
from typing import Any, Dict, Optional

from .parser import Parser
from .compiler import Compiler
from .vm import (
    ARRAY_METHODS,
    NUMBER_METHODS,
    STRING_METHODS,
    VM,
    JSThrow,
    heap_size,
)
from .values import (
    UNDEFINED,
    NULL,
    JSValue,
    JSObject,
    JSCallableObject,
    JSArray,
    JSFunction,
    JSRegExp,
    JSBoundMethod,
    to_string,
    to_number,
    to_array_length,
    own_enumerable_keys,
    CURRENT_VM,
)
from .ast_nodes import ExpressionStatement, FunctionExpression
from .errors import (
    JSError,
    JSRangeError,
    JSSyntaxError,
    JSTypeError,
    MemoryLimitError,
    TimeLimitError,
)
from .numbers import (
    BINARY_MATH,
    MAX_SAFE_INTEGER,
    UNARY_MATH,
    VARIADIC_MATH,
    int_from_digits,
    js_number,
    number_to_string,
    parse_float,
    parse_int,
)

# Characters encodeURIComponent leaves alone, and those encodeURI also keeps
URI_UNRESERVED = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.!~*'()"
)
URI_RESERVED = ";/?:@&=+$,"


def uri_encoder(keep: str):
    """Build encodeURI or encodeURIComponent: %-encode UTF-8 except keep."""

    def encode(*args):
        text = to_string(args[0]) if args else "undefined"
        try:
            data = text.encode("utf-8")
        except UnicodeEncodeError:
            raise JSError("URI malformed", "URIError")
        return "".join(
            chr(byte) if chr(byte) in keep else f"%{byte:02X}" for byte in data
        )

    return encode


def uri_decoder(reserved: str):
    """Build decodeURI or decodeURIComponent: escapes of reserved stay as-is."""

    def decode(*args):
        text = to_string(args[0]) if args else "undefined"
        out = []
        i = 0
        while i < len(text):
            if text[i] != "%":
                out.append(text[i])
                i += 1
                continue
            # Collect one UTF-8 sequence of %XX escapes
            data = bytearray()
            start = i
            while True:
                hex_digits = text[i + 1 : i + 3]
                if len(hex_digits) < 2 or not all(
                    c in "0123456789abcdefABCDEF" for c in hex_digits
                ):
                    raise JSError("URI malformed", "URIError")
                data.append(int(hex_digits, 16))
                i += 3
                lead = data[0]
                needed = (
                    1
                    if lead < 0x80
                    else 2 if lead >> 5 == 6 else 3 if lead >> 4 == 14 else 4
                )
                if len(data) == needed or i >= len(text) or text[i] != "%":
                    break
            try:
                decoded = data.decode("utf-8")
            except UnicodeDecodeError:
                raise JSError("URI malformed", "URIError")
            if len(decoded) == 1 and decoded in reserved:
                out.append(text[start:i])
            else:
                out.append(decoded)
        return "".join(out)

    return decode


class Context:
    """JavaScript execution context with configurable limits."""

    def __init__(
        self,
        memory_limit: Optional[int] = None,
        time_limit: Optional[float] = None,
    ):
        """Create a new JavaScript context.

        Args:
            memory_limit: Maximum bytes of live script data, not counting the
                built-ins. Value sizes are estimated, so this is approximate.
            time_limit: Maximum execution time in seconds, per eval() call
        """
        self.memory_limit = memory_limit
        self.time_limit = time_limit
        self._globals: Dict[str, JSValue] = {}
        self._current_vm = None  # Set during eval() for timeout checking
        # The original built-in prototypes, shared with every VM
        self.intrinsics: Dict[str, JSObject] = {}
        self._setup_globals()
        # Memory used by the built-ins, which does not count against the limit
        self._baseline_bytes = (
            heap_size(list(self._globals.values())) if memory_limit else 0
        )

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
        self._globals["ReferenceError"] = self._create_error_constructor(
            "ReferenceError"
        )
        self._globals["RangeError"] = self._create_error_constructor("RangeError")
        self._globals["URIError"] = self._create_error_constructor("URIError")
        self._globals["EvalError"] = self._create_error_constructor("EvalError")

        # Math object
        self._globals["Math"] = self._create_math_object()

        # JSON object
        self._globals["JSON"] = self._create_json_object()

        # Number constructor and methods (Number.parseInt is the global parseInt)
        self._parse_int = self._global_parseint
        self._parse_float = self._global_parsefloat
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
        self._globals["Uint32Array"] = self._create_typed_array_constructor(
            "Uint32Array"
        )
        self._globals["Float64Array"] = self._create_typed_array_constructor(
            "Float64Array"
        )
        self._globals["Float32Array"] = self._create_typed_array_constructor(
            "Float32Array"
        )
        self._globals["Uint8Array"] = self._create_typed_array_constructor("Uint8Array")
        self._globals["Int8Array"] = self._create_typed_array_constructor("Int8Array")
        self._globals["Int16Array"] = self._create_typed_array_constructor("Int16Array")
        self._globals["Uint16Array"] = self._create_typed_array_constructor(
            "Uint16Array"
        )
        self._globals["Uint8ClampedArray"] = self._create_typed_array_constructor(
            "Uint8ClampedArray"
        )

        # ArrayBuffer constructor
        self._globals["ArrayBuffer"] = self._create_arraybuffer_constructor()

        # Global number functions
        self._globals["encodeURIComponent"] = uri_encoder(URI_UNRESERVED)
        self._globals["encodeURI"] = uri_encoder(URI_UNRESERVED + URI_RESERVED + "#")
        self._globals["decodeURIComponent"] = uri_decoder("")
        self._globals["decodeURI"] = uri_decoder(URI_RESERVED + "#")
        self._globals["isNaN"] = self._global_isnan
        self._globals["isFinite"] = self._global_isfinite
        self._globals["parseInt"] = self._parse_int
        self._globals["parseFloat"] = self._parse_float

        # eval function
        self._globals["eval"] = self._create_eval_function()

        self._install_prototypes()

    def _install_prototypes(self) -> None:
        """Link constructors with their prototypes and add built-in methods."""
        intrinsics = self.intrinsics
        object_prototype = intrinsics["ObjectPrototype"]
        function_prototype = intrinsics["FunctionPrototype"]
        globals_ = self._globals

        def link(constructor, prototype):
            constructor._prototype = function_prototype
            constructor.set_hidden("prototype", prototype)
            prototype.set_hidden("constructor", constructor)

        def native(kind, name):
            def call(this, *args):
                vm = CURRENT_VM.get()
                if vm is None:
                    raise JSTypeError(f"{name}() called outside a running script")
                return vm.call_builtin(kind, name, this, args)

            return JSBoundMethod(call, name)

        def install(prototype, kind, names):
            for name in names:
                prototype.set_hidden(name, native(kind, name))

        def new_prototype(name):
            prototype = JSObject(object_prototype)
            intrinsics[name] = prototype
            return prototype

        link(globals_["Object"], object_prototype)
        for name in (
            "toString",
            "hasOwnProperty",
            "valueOf",
            "isPrototypeOf",
            "propertyIsEnumerable",
            "toLocaleString",
        ):
            object_prototype.set_hidden(name, object_prototype.get(name))

        link(globals_["Function"], function_prototype)
        install(function_prototype, "function", ("call", "apply", "bind", "toString"))

        intrinsics["ArrayPrototype"] = self._array_prototype
        link(globals_["Array"], self._array_prototype)
        install(self._array_prototype, "array", ARRAY_METHODS)

        string_prototype = new_prototype("StringPrototype")
        link(globals_["String"], string_prototype)
        install(string_prototype, "string", STRING_METHODS)

        number_prototype = new_prototype("NumberPrototype")
        link(globals_["Number"], number_prototype)
        install(number_prototype, "number", NUMBER_METHODS)

        boolean_prototype = new_prototype("BooleanPrototype")
        link(globals_["Boolean"], boolean_prototype)
        install(boolean_prototype, "boolean", ("toString", "valueOf"))

        regexp_prototype = new_prototype("RegExpPrototype")
        link(globals_["RegExp"], regexp_prototype)
        install(regexp_prototype, "regexp", ("test", "exec", "toString"))

        # Error types inherit from Error
        error = globals_["Error"]
        error_prototype = error.get("prototype")
        error_prototype._prototype = object_prototype
        intrinsics["ErrorPrototype"] = error_prototype
        link(error, error_prototype)
        install(error_prototype, "error", ("toString",))
        for name in (
            "TypeError",
            "SyntaxError",
            "ReferenceError",
            "RangeError",
            "URIError",
            "EvalError",
        ):
            constructor = globals_[name]
            prototype = constructor.get("prototype")
            prototype._prototype = error_prototype
            link(constructor, prototype)
            constructor._prototype = error

        # Remaining constructors are functions too
        for name, value in globals_.items():
            if isinstance(value, JSCallableObject) and value._prototype is None:
                value._prototype = function_prototype

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
            if isinstance(this_val, JSRegExp):
                return "[object RegExp]"
            error_prototype = self.intrinsics.get("ErrorPrototype")
            proto = getattr(this_val, "_prototype", None)
            while proto is not None:
                if proto is error_prototype:
                    return "[object Error]"
                proto = proto._prototype
            if callable(this_val) or isinstance(
                this_val, (JSCallableObject, JSFunction)
            ):
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
                return (
                    this_val.has(prop)
                    or prop in this_val._getters
                    or prop in this_val._setters
                )
            if isinstance(this_val, JSObject):
                return (
                    this_val.has(prop)
                    or prop in this_val._getters
                    or prop in this_val._setters
                )
            return False

        def proto_valueOf(this_val, *args):
            return this_val

        def proto_isPrototypeOf(this_val, *args):
            obj = args[0] if args else UNDEFINED
            if not isinstance(obj, JSObject):
                return False
            proto = getattr(obj, "_prototype", None)
            while proto is not None:
                if proto is this_val:
                    return True
                proto = getattr(proto, "_prototype", None)
            return False

        # These methods need special handling for 'this'
        from .values import JSBoundMethod

        object_prototype.set("toString", JSBoundMethod(proto_toString))
        object_prototype.set("hasOwnProperty", JSBoundMethod(proto_hasOwnProperty))
        object_prototype.set("valueOf", JSBoundMethod(proto_valueOf))
        object_prototype.set("isPrototypeOf", JSBoundMethod(proto_isPrototypeOf))

        def proto_propertyIsEnumerable(this_val, *args):
            key = to_string(args[0]) if args else "undefined"
            if isinstance(this_val, JSArray):
                if key.isdigit() and int(key) < len(this_val._elements):
                    return True
            if not isinstance(this_val, JSObject):
                return False
            return key in this_val._properties and key not in this_val._hidden

        def proto_toLocaleString(this_val, *args):
            vm = CURRENT_VM.get()
            return vm._call_callback(
                vm._get_property(this_val, "toString"), [], this_val
            )

        object_prototype.set(
            "propertyIsEnumerable", JSBoundMethod(proto_propertyIsEnumerable)
        )
        object_prototype.set("toLocaleString", JSBoundMethod(proto_toLocaleString))

        # Store for other constructors to use
        self._object_prototype = object_prototype
        self.intrinsics["ObjectPrototype"] = object_prototype

        # Function.prototype is itself a function, which returns undefined
        function_prototype = JSCallableObject(lambda *args: UNDEFINED, object_prototype)
        self.intrinsics["FunctionPrototype"] = function_prototype
        obj_constructor._prototype = function_prototype

        def keys_fn(*args):
            obj = args[0] if args else UNDEFINED
            arr = JSArray()
            arr._elements = own_enumerable_keys(obj)
            return arr

        def values_fn(*args):
            obj = args[0] if args else UNDEFINED
            vm = CURRENT_VM.get()
            arr = JSArray()
            arr._elements = [vm._get_property(obj, k) for k in own_enumerable_keys(obj)]
            return arr

        def entries_fn(*args):
            obj = args[0] if args else UNDEFINED
            vm = CURRENT_VM.get()
            arr = JSArray()
            for k in own_enumerable_keys(obj):
                entry = JSArray()
                entry._elements = [k, vm._get_property(obj, k)]
                arr._elements.append(entry)
            return arr

        def assign_fn(*args):
            if not args:
                return JSObject()
            target = args[0]
            if not isinstance(target, JSObject):
                return target
            vm = CURRENT_VM.get()
            for source in args[1:]:
                for k in own_enumerable_keys(source):
                    vm._set_property(target, k, vm._get_property(source, k))
            return target

        def get_prototype_of(*args):
            obj = args[0] if args else UNDEFINED
            if not isinstance(obj, JSObject):
                return NULL
            return getattr(obj, "_prototype", NULL) or NULL

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

            descriptor = JSObject(object_prototype)
            getter = obj._getters.get(prop_name)
            setter = obj._setters.get(prop_name)
            if getter or setter:
                descriptor.set("get", getter if getter else UNDEFINED)
                descriptor.set("set", setter if setter else UNDEFINED)
            elif isinstance(obj, JSArray) and prop_name in array_own_keys(obj):
                value = (
                    obj.length
                    if prop_name == "length"
                    else obj._elements[int(prop_name)]
                )
                descriptor.set("value", value)
                descriptor.set("writable", not obj._frozen)
            elif obj.has(prop_name):
                descriptor.set("value", obj.get(prop_name))
                descriptor.set("writable", not obj._frozen)
            else:
                return UNDEFINED
            enumerable = prop_name not in obj._hidden and prop_name != "length"
            descriptor.set("enumerable", enumerable)
            descriptor.set("configurable", not obj._sealed and prop_name != "length")
            return descriptor

        def array_own_keys(arr):
            return [str(i) for i in range(len(arr._elements))] + ["length"]

        def own_property_names(*args):
            """Object.getOwnPropertyNames(obj): all own keys, enumerable or not."""
            obj = args[0] if args else UNDEFINED
            if isinstance(obj, str):
                names = [str(i) for i in range(len(obj))] + ["length"]
            elif not isinstance(obj, JSObject):
                names = []
            else:
                names = array_own_keys(obj) if isinstance(obj, JSArray) else []
                for key in list(obj._properties) + list(obj._getters):
                    if key not in names:
                        names.append(key)
            result = JSArray()
            result._elements = names
            return result

        def own_property_descriptors(*args):
            obj = args[0] if args else UNDEFINED
            result = JSObject(object_prototype)
            for name in own_property_names(obj)._elements:
                result.set(name, get_own_property_descriptor(obj, name))
            return result

        def is_fn(*args):
            """Object.is: SameValue (NaN is NaN, 0 is not -0)."""
            a = args[0] if args else UNDEFINED
            b = args[1] if len(args) > 1 else UNDEFINED
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                if isinstance(a, bool) or isinstance(b, bool):
                    return a is b
                if a != a and b != b:
                    return True
                if a == 0 and b == 0:
                    return math.copysign(1, a) == math.copysign(1, b)
                return a == b
            if isinstance(a, str) and isinstance(b, str):
                return a == b
            return a is b

        def from_entries(*args):
            entries = args[0] if args else UNDEFINED
            if not isinstance(entries, JSArray):
                raise JSTypeError("Object.fromEntries requires an array of entries")
            result = JSObject(object_prototype)
            for entry in entries._elements:
                if not isinstance(entry, JSArray):
                    raise JSTypeError("Object.fromEntries entries must be arrays")
                key = entry.get_index(0)
                result.set(to_string(key), entry.get_index(1))
            return result

        def restrict(level):
            """Object.preventExtensions (1), seal (2) and freeze (3)."""

            def restrict_fn(*args):
                obj = args[0] if args else UNDEFINED
                if isinstance(obj, JSObject):
                    obj._extensible = False
                    if level >= 2:
                        obj._sealed = True
                    if level >= 3:
                        obj._frozen = True
                return obj

            return restrict_fn

        def has_no_own_properties(obj):
            if isinstance(obj, JSArray) and obj._elements:
                return False
            return not obj._properties and not obj._getters and not obj._setters

        def is_frozen(*args):
            obj = args[0] if args else UNDEFINED
            if not isinstance(obj, JSObject):
                return True
            return obj._frozen or (not obj._extensible and has_no_own_properties(obj))

        def is_sealed(*args):
            obj = args[0] if args else UNDEFINED
            if not isinstance(obj, JSObject):
                return True
            return obj._sealed or (not obj._extensible and has_no_own_properties(obj))

        def is_extensible(*args):
            obj = args[0] if args else UNDEFINED
            return isinstance(obj, JSObject) and obj._extensible

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
        obj_constructor.set("getOwnPropertyDescriptors", own_property_descriptors)
        obj_constructor.set("getOwnPropertyNames", own_property_names)
        obj_constructor.set("is", is_fn)
        obj_constructor.set("fromEntries", from_entries)
        obj_constructor.set("preventExtensions", restrict(1))
        obj_constructor.set("seal", restrict(2))
        obj_constructor.set("freeze", restrict(3))
        obj_constructor.set("isFrozen", is_frozen)
        obj_constructor.set("isSealed", is_sealed)
        obj_constructor.set("isExtensible", is_extensible)
        obj_constructor.set("prototype", object_prototype)

        return obj_constructor

    def _create_array_constructor(self) -> JSCallableObject:
        """Create the Array constructor with static methods."""
        # Create Array.prototype (inherits from Object.prototype)
        array_prototype = JSArray()
        array_prototype._prototype = self._object_prototype

        def array_constructor(*args):
            if len(args) == 1 and isinstance(args[0], (int, float)):
                arr = JSArray(to_array_length(args[0]))
            else:
                arr = JSArray()
                for arg in args:
                    arr.push(arg)
            arr._prototype = array_prototype
            return arr

        arr_constructor = JSCallableObject(array_constructor)

        # Store for other uses
        self._array_prototype = array_prototype

        # Array.isArray()
        def is_array(*args):
            obj = args[0] if args else UNDEFINED
            return isinstance(obj, JSArray)

        arr_constructor.set("isArray", is_array)

        def array_from(*args):
            """Array.from(arrayLike or string, mapFn, thisArg)."""
            source = args[0] if args else UNDEFINED
            map_fn = args[1] if len(args) > 1 and args[1] is not UNDEFINED else None
            this_arg = args[2] if len(args) > 2 else UNDEFINED
            vm = CURRENT_VM.get()
            if source is UNDEFINED or source is NULL:
                raise JSTypeError("Array.from requires an array-like object")
            items, _ = vm._array_receiver(source)
            result = JSArray()
            result._elements = items._elements[:]
            if map_fn is not None:
                result._elements = [
                    vm._call_callback(map_fn, [value, i], this_arg)
                    for i, value in enumerate(result._elements)
                ]
            return result

        def array_of(*args):
            result = JSArray()
            result._elements = list(args)
            return result

        arr_constructor.set("from", array_from)
        arr_constructor.set("of", array_of)

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

        def unary(fn):
            return lambda *args: fn(to_number(args[0]) if args else float("nan"))

        def binary(fn):
            def call(*args):
                a = to_number(args[0]) if args else float("nan")
                b = to_number(args[1]) if len(args) > 1 else float("nan")
                return fn(a, b)

            return call

        def variadic(fn):
            return lambda *args: fn([to_number(arg) for arg in args])

        for name, fn in UNARY_MATH.items():
            math_obj.set(name, unary(fn))
        for name, fn in BINARY_MATH.items():
            math_obj.set(name, binary(fn))
        for name, fn in VARIADIC_MATH.items():
            math_obj.set(name, variadic(fn))
        math_obj.set("random", lambda *args: random.random())

        return math_obj

    def _create_json_object(self) -> JSObject:
        """Create the JSON global object."""
        json_obj = JSObject()
        ctx = self  # Reference for closures

        def reject_constant(name):
            # Python's json accepts NaN and Infinity; JSON does not
            raise json.JSONDecodeError(f"Unexpected token {name}", name, 0)

        def parse_json_int(text):
            n = int_from_digits(text.lstrip("-"))
            if text.startswith("-"):
                return -n if n else -0.0
            return n

        def parse_fn(*args):
            text = to_string(args[0]) if args else ""
            try:
                py_value = json.loads(
                    text, parse_constant=reject_constant, parse_int=parse_json_int
                )
                return ctx._to_js(py_value)
            except json.JSONDecodeError as e:
                from .errors import JSSyntaxError

                raise JSSyntaxError(f"JSON.parse: {e}")

        def stringify_fn(*args):
            value = args[0] if args else UNDEFINED

            # Convert JS value to Python for json.dumps, handling undefined specially
            in_progress = set()  # ids of the arrays and objects being serialized

            def to_json_value(v):
                if isinstance(v, JSFunction) or (
                    callable(v) and not isinstance(v, JSObject)
                ):
                    return UNDEFINED
                if isinstance(v, JSObject):
                    if id(v) in in_progress:
                        raise JSTypeError("Converting circular structure to JSON")
                    in_progress.add(id(v))
                    try:
                        return container_to_json(v)
                    finally:
                        in_progress.discard(id(v))
                return scalar_to_json(v)

            def scalar_to_json(v):
                if v is UNDEFINED:
                    return UNDEFINED  # Skipped in objects, null in arrays
                if v is NULL:
                    return None
                if isinstance(v, bool):
                    return v
                if isinstance(v, (int, float)):
                    return v
                if isinstance(v, str):
                    return v
                return None

            def container_to_json(v):
                if isinstance(v, JSArray):
                    # For arrays, undefined and functions become null
                    items = [to_json_value(elem) for elem in v._elements]
                    return [None if item is UNDEFINED else item for item in items]
                if isinstance(v, JSObject):
                    # For objects, skip undefined values and functions
                    result = {}
                    for k in v.keys():
                        item = to_json_value(v._properties[k])
                        if item is not UNDEFINED:
                            result[k] = item
                    return result
                return None

            def dump(v):
                # Numbers use JavaScript formatting; NaN and Infinity are null
                if isinstance(v, bool) or v is None:
                    return json.dumps(v)
                if isinstance(v, (int, float)):
                    return number_to_string(v) if math.isfinite(v) else "null"
                if isinstance(v, list):
                    return "[" + ",".join(dump(item) for item in v) + "]"
                if isinstance(v, dict):
                    return (
                        "{"
                        + ",".join(
                            f"{json.dumps(k)}:{dump(val)}" for k, val in v.items()
                        )
                        + "}"
                    )
                return json.dumps(v, ensure_ascii=False)

            py_value = to_json_value(value)
            if py_value is UNDEFINED:
                return UNDEFINED
            return dump(py_value)

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

        def is_number(x):
            return isinstance(x, (int, float)) and not isinstance(x, bool)

        def isNaN_fn(*args):
            x = args[0] if args else UNDEFINED
            # Number.isNaN only returns true for actual NaN
            return is_number(x) and math.isnan(x)

        def isFinite_fn(*args):
            x = args[0] if args else UNDEFINED
            return is_number(x) and math.isfinite(x)

        def isInteger_fn(*args):
            x = args[0] if args else UNDEFINED
            return is_number(x) and math.isfinite(x) and x == math.floor(x)

        def isSafeInteger_fn(*args):
            x = args[0] if args else UNDEFINED
            return isInteger_fn(x) and abs(x) <= MAX_SAFE_INTEGER

        num_constructor.set("isNaN", isNaN_fn)
        num_constructor.set("isFinite", isFinite_fn)
        num_constructor.set("isInteger", isInteger_fn)
        num_constructor.set("isSafeInteger", isSafeInteger_fn)
        num_constructor.set("parseInt", self._parse_int)
        num_constructor.set("parseFloat", self._parse_float)
        num_constructor.set("MAX_SAFE_INTEGER", MAX_SAFE_INTEGER)
        num_constructor.set("MIN_SAFE_INTEGER", -MAX_SAFE_INTEGER)
        num_constructor.set("EPSILON", 2.0**-52)
        num_constructor.set("MAX_VALUE", sys.float_info.max)
        num_constructor.set("MIN_VALUE", 5e-324)
        num_constructor.set("POSITIVE_INFINITY", float("inf"))
        num_constructor.set("NEGATIVE_INFINITY", float("-inf"))
        num_constructor.set("NaN", float("nan"))

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

        def fromCodePoint_fn(*args):
            chars = []
            for arg in args:
                code = to_number(arg)
                if code != code or code < 0 or code > 0x10FFFF or code != int(code):
                    raise JSRangeError(f"Invalid code point {to_string(arg)}")
                chars.append(chr(int(code)))
            return "".join(chars)

        string_constructor.set("fromCodePoint", fromCodePoint_fn)

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
        ctx = self  # Capture self for closure

        def regexp_constructor_fn(*args):
            pattern = to_string(args[0]) if args else ""
            flags = to_string(args[1]) if len(args) > 1 else ""
            # Create timeout callback if we have a current VM with time_limit
            poll_callback = None
            if ctx._current_vm and ctx._current_vm.time_limit is not None:
                vm = ctx._current_vm

                def check_timeout() -> bool:
                    """Return True if time limit exceeded (to abort regex)."""
                    return time.monotonic() - vm.start_time > vm.time_limit

                poll_callback = check_timeout
            return JSRegExp(pattern, flags, poll_callback)

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
            source = f"(function({param_str}) {{\n{body}\n}})"

            # Parse errors propagate as JSSyntaxError, which the VM throws
            # as a JavaScript SyntaxError
            ast = Parser(source).parse()
            # Reject bodies that close the wrapper early, such as
            # "}); code(); (function() {", rather than running them
            if not (
                len(ast.body) == 1
                and isinstance(ast.body[0], ExpressionStatement)
                and isinstance(ast.body[0].expression, FunctionExpression)
            ):
                raise JSSyntaxError("Invalid function body")
            bytecode_module = Compiler().compile(ast)

            # Evaluating the program creates the function object (no
            # user code runs)
            return self._new_vm().run(bytecode_module)

        fn_constructor = JSCallableObject(function_constructor_fn)
        fn_prototype = self.intrinsics["FunctionPrototype"]
        fn_prototype.set_hidden("constructor", fn_constructor)
        fn_constructor.set("prototype", fn_prototype)
        fn_constructor._prototype = fn_prototype

        return fn_constructor

    def _create_typed_array_constructor(self, name: str) -> JSCallableObject:
        """Create a typed array constructor (Int32Array, Uint8Array, etc.)."""
        from .values import (
            JSInt32Array,
            JSUint32Array,
            JSFloat64Array,
            JSFloat32Array,
            JSUint8Array,
            JSInt8Array,
            JSInt16Array,
            JSUint16Array,
            JSUint8ClampedArray,
            JSArrayBuffer,
            JSArray,
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
                        fmt = "f" if element_size == 4 else "d"
                        val = struct.unpack(
                            fmt, bytes(buffer._data[offset : offset + element_size])
                        )[0]
                    else:
                        val = int.from_bytes(
                            buffer._data[offset : offset + element_size],
                            "little",
                            signed="Int" in name,
                        )
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

            # Parse errors propagate as JSSyntaxError, which the VM throws
            # as a JavaScript SyntaxError
            compiled = Compiler().compile(Parser(code).parse())
            if ctx._current_vm is not None:
                # Run inside the current execution so that the time limit
                # keeps counting and throws reach the caller's handlers
                return ctx._current_vm.run_nested(compiled)
            return ctx._new_vm().run(compiled)

        return eval_fn

    def _global_isnan(self, *args) -> bool:
        """Global isNaN - converts argument to number first."""
        x = to_number(args[0]) if args else float("nan")
        return math.isnan(x)

    def _global_isfinite(self, *args) -> bool:
        """Global isFinite - converts argument to number first."""
        x = to_number(args[0]) if args else float("nan")
        return not (math.isnan(x) or math.isinf(x))

    def _global_parseint(self, *args):
        """Global parseInt."""
        s = to_string(args[0]) if args else "undefined"
        radix = to_number(args[1]) if len(args) > 1 else 0
        return parse_int(s, radix)

    def _global_parsefloat(self, *args):
        """Global parseFloat."""
        return parse_float(to_string(args[0]) if args else "undefined")

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
        vm = self._new_vm()

        # Store current VM for timeout checking and nested calls; restore the
        # previous one afterwards in case eval() was called re-entrantly
        previous_vm = self._current_vm
        self._current_vm = vm
        try:
            result = vm.run(compiled)
        except JSError as e:
            e.value = self._to_python(e.value)
            raise
        finally:
            self._current_vm = previous_vm

        return self._to_python(result)

    def _new_vm(self) -> VM:
        """Create a VM sharing this context's globals and limits."""
        vm = VM(memory_limit=self.memory_limit, time_limit=self.time_limit)
        # Share globals with the VM (not a copy, so eval can modify them)
        vm.globals = self._globals
        vm.baseline_bytes = self._baseline_bytes
        vm.intrinsics = self.intrinsics
        return vm

    def _call_function(self, func: JSFunction, args: list) -> Any:
        """Call a JavaScript function with the given arguments.

        This is used internally to invoke JSFunction objects from Python code.
        """
        if self._current_vm is not None:
            # Run on the active VM so throws unwind into the caller's handlers
            # and the time limit keeps counting from the start of eval()
            return self._current_vm._call_callback(func, args, UNDEFINED)
        vm = self._new_vm()
        vm.start_time = time.monotonic()
        try:
            return vm._call_callback(func, args, UNDEFINED)
        except JSThrow as e:
            raise vm._uncaught_error(e.value) from None

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
        """Convert a JavaScript value to Python.

        Arrays become lists and objects dicts. Shared and cyclic references
        are preserved, and nesting depth is not limited by Python's stack.
        """
        if not isinstance(value, JSObject) or isinstance(value, JSFunction):
            return self._primitive_to_python(value)
        converted: Dict[int, Any] = {}
        root = self._empty_python_container(value, converted)
        pending = [value]
        while pending:
            js_value = pending.pop()
            target = converted[id(js_value)]
            if isinstance(js_value, JSArray):
                items = js_value._elements
                target.extend([None] * len(items))
                slots = enumerate(items)
            else:
                slots = ((k, js_value._properties[k]) for k in js_value.keys())
            for key, item in slots:
                if not isinstance(item, JSObject) or isinstance(item, JSFunction):
                    target[key] = self._primitive_to_python(item)
                elif id(item) in converted:
                    target[key] = converted[id(item)]
                else:
                    target[key] = self._empty_python_container(item, converted)
                    pending.append(item)
        return root

    @staticmethod
    def _empty_python_container(value: JSObject, converted: Dict[int, Any]) -> Any:
        container = [] if isinstance(value, JSArray) else {}
        converted[id(value)] = container
        return container

    @staticmethod
    def _primitive_to_python(value: JSValue) -> Any:
        if value is UNDEFINED or value is NULL:
            return None
        return value

    def _to_js(self, value: Any) -> JSValue:
        """Convert a Python value to JavaScript.

        Lists become arrays and dicts objects, preserving shared and cyclic
        references without recursion.
        """
        if not isinstance(value, (list, dict)):
            return self._primitive_to_js(value)
        converted: Dict[int, JSValue] = {}
        root = self._empty_js_container(value, converted)
        pending = [value]
        while pending:
            py_value = pending.pop()
            target = converted[id(py_value)]
            if isinstance(py_value, list):
                slots = enumerate(py_value)
            else:
                slots = ((str(k), v) for k, v in py_value.items())
            for key, item in slots:
                if not isinstance(item, (list, dict)):
                    js_item = self._primitive_to_js(item)
                elif id(item) in converted:
                    js_item = converted[id(item)]
                else:
                    js_item = self._empty_js_container(item, converted)
                    pending.append(item)
                if isinstance(target, JSArray):
                    target._elements.append(js_item)
                else:
                    target.set(key, js_item)
        return root

    def _empty_js_container(self, value: Any, converted: Dict[int, JSValue]):
        if isinstance(value, list):
            container = JSArray()
            container._prototype = self._array_prototype
        else:
            container = JSObject(self._object_prototype)
        converted[id(value)] = container
        return container

    @staticmethod
    def _primitive_to_js(value: Any) -> JSValue:
        if value is None:
            return NULL
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return js_number(value)
        if isinstance(value, str):
            return value
        # Already JS values - pass through
        if isinstance(value, (JSObject, JSFunction, JSCallableObject)):
            return value
        if value is UNDEFINED:
            return value
        # Python callables become JS functions
        if callable(value):
            return value
        return UNDEFINED


# Backwards-compatible alias: JSContext was the original name and may be used
# by existing code. Keep this alias to avoid breaking changes.
JSContext = Context
