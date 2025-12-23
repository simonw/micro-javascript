"""
MQuickJS Python - A Pure Python JavaScript Sandbox Engine

This module provides a specification and TODO list for implementing a Python port
of the MQuickJS JavaScript engine. The goal is to create a sandboxed JavaScript
execution environment with memory and time limits, implemented entirely in Python
with no external dependencies.

Based on: https://github.com/bellard/mquickjs
License: MIT (see LICENSE file)

================================================================================
OVERVIEW
================================================================================

MQuickJS is a minimal JavaScript engine supporting a subset close to ES5 with
"stricter mode" - a subset of JavaScript that works in standard engines but
disables error-prone or inefficient constructs.

Key design principles for the Python port:
- Pure Python implementation (no C extensions, no dependencies)
- Sandboxed execution with configurable memory and time limits
- Support for the MQuickJS JavaScript subset (stricter mode)
- Stack-based bytecode VM similar to the original

================================================================================
JAVASCRIPT SUBSET SUPPORTED (Stricter Mode)
================================================================================

The engine supports a subset of JavaScript with these restrictions:

1. STRICT MODE ONLY
   - All code runs in strict mode
   - No 'with' keyword
   - Global variables must be declared with 'var'

2. ARRAYS
   - No holes allowed (sparse arrays not supported)
   - Out-of-bound writes are errors (except appending at end)
   - Array literals with holes are syntax errors: [1, , 3]
   - new Array(len) creates array with undefined elements

3. EVAL
   - Only global (indirect) eval is supported: (1, eval)('code')
   - Direct eval is forbidden: eval('code')

4. NO VALUE BOXING
   - new Number(1), new Boolean(true), new String("s") not supported
   - Primitive values are used directly

5. PROPERTY RESTRICTIONS
   - All properties are writable, enumerable, and configurable
   - 'for...in' only iterates over own properties

6. OTHER RESTRICTIONS
   - Date: only Date.now() is supported
   - String case functions: only ASCII characters
   - RegExp: case folding only for ASCII

================================================================================
ARCHITECTURE
================================================================================

The implementation consists of the following main components:

1. LEXER (tokenizer.py)
   - Converts JavaScript source code into tokens
   - Handles string literals, numbers, identifiers, operators
   - Unicode support (UTF-8 internal storage)

2. PARSER (parser.py)
   - Recursive descent parser (non-recursive to bound stack usage)
   - Produces bytecode directly (no AST intermediate representation)
   - One-pass compilation with optimization

3. BYTECODE COMPILER (compiler.py)
   - Generates stack-based bytecode
   - Handles scope resolution, closures, variable references
   - Optimizes short jumps, common patterns

4. VIRTUAL MACHINE (vm.py)
   - Stack-based bytecode interpreter
   - Implements all opcodes
   - Memory and time limit enforcement

5. RUNTIME (runtime.py)
   - JavaScript value representation
   - Object model (objects, arrays, functions, closures)
   - Garbage collection (tracing GC)

6. BUILT-IN OBJECTS (builtins.py)
   - Object, Array, String, Number, Boolean, Function
   - Math, JSON, RegExp, Error types
   - TypedArrays: Uint8Array, Int8Array, etc.

7. CONTEXT (context.py)
   - Execution context management
   - Global object
   - Memory and time limit configuration

================================================================================
DATA TYPES
================================================================================

JavaScript values in the Python implementation:

1. PRIMITIVE TYPES
   - undefined: singleton JSUndefined
   - null: singleton JSNull
   - boolean: Python bool (True/False)
   - number: Python int or float (31-bit ints optimized)
   - string: Python str (UTF-8, with surrogate pair handling)

2. OBJECT TYPES
   - JSObject: base class for all objects
   - JSArray: array object with special length handling
   - JSFunction: JavaScript function (closure)
   - JSCFunction: native Python function callable from JS
   - JSRegExp: regular expression object
   - JSError: error object (TypeError, ReferenceError, etc.)
   - JSTypedArray: typed array views (Uint8Array, etc.)
   - JSArrayBuffer: raw binary data buffer

================================================================================
BYTECODE OPCODES
================================================================================

Based on mquickjs_opcode.h, the VM uses these opcodes:

STACK MANIPULATION:
- push_value, push_const, push_i8, push_i16
- push_0 through push_7, push_minus1
- undefined, null, push_true, push_false
- drop, dup, dup1, dup2, swap, rot3l, nip, perm3, perm4
- insert2, insert3

CONTROL FLOW:
- if_false, if_true, goto
- call, call_method, call_constructor, return, return_undef
- throw, catch, gosub, ret (for finally blocks)
- for_in_start, for_of_start, for_of_next

VARIABLES AND PROPERTIES:
- get_loc, put_loc, get_loc0-3, put_loc0-3
- get_arg, put_arg, get_arg0-3, put_arg0-3
- get_var_ref, put_var_ref
- get_field, get_field2, put_field
- get_array_el, get_array_el2, put_array_el
- get_length, get_length2
- define_field, define_getter, define_setter, set_proto

ARITHMETIC/LOGIC:
- add, sub, mul, div, mod, pow
- neg, plus, inc, dec, post_inc, post_dec
- shl, sar, shr, and, or, xor, not
- lt, lte, gt, gte, eq, neq, strict_eq, strict_neq
- lnot, typeof, delete, instanceof, in

OBJECTS:
- object, array_from, fclosure, fclosure8
- push_this, this_func, arguments, new_target
- regexp

================================================================================
TODO LIST
================================================================================

Phase 1: Core Infrastructure
-----------------------------
TODO: [DONE] Set up project structure with uv
TODO: [DONE] Copy test files from mquickjs
TODO: [DONE] Create basic pytest test harness
TODO: [DONE] Write this spec.py

TODO: Create base value types (values.py)
  - JSUndefined, JSNull singletons
  - JSValue base class
  - Number handling (int vs float, NaN, Infinity)
  - String handling with UTF-8 and surrogate pairs

TODO: Create token types (tokens.py)
  - TokenType enum for all JS tokens
  - Token dataclass with type, value, line, column

TODO: Implement lexer (lexer.py)
  - Tokenize identifiers and keywords
  - Tokenize numbers (decimal, hex, octal, binary, float)
  - Tokenize strings (single/double quotes, escapes, unicode)
  - Tokenize operators and punctuation
  - Tokenize regular expression literals
  - Handle comments (single-line and multi-line)
  - Track line and column numbers for error reporting

Phase 2: Parser
----------------
TODO: Implement expression parser (parser.py)
  - Primary expressions (literals, identifiers, this, grouping)
  - Member expressions (dot and bracket notation)
  - Call expressions
  - Unary operators
  - Binary operators with precedence
  - Conditional (ternary) operator
  - Assignment operators
  - Comma operator

TODO: Implement statement parser (parser.py)
  - Variable declarations (var only, no let/const)
  - Expression statements
  - Block statements
  - If/else statements
  - While, do-while, for loops
  - For-in, for-of loops
  - Switch statements
  - Try/catch/finally
  - Throw statement
  - Return statement
  - Break/continue with labels
  - Function declarations

TODO: Implement function parsing
  - Named function declarations
  - Function expressions
  - Arrow functions (if supported)
  - Parameter handling
  - Default parameters (if supported)
  - Rest parameters (if supported)

TODO: Implement object/array literal parsing
  - Object literals with computed properties
  - Getter/setter definitions
  - Method shorthand
  - Array literals
  - Spread syntax (if supported)

Phase 3: Compiler
------------------
TODO: Implement bytecode generation (compiler.py)
  - Opcode definitions matching mquickjs_opcode.h
  - Bytecode writer with instruction encoding
  - Constant pool management
  - Label resolution and jump patching

TODO: Implement scope analysis
  - Variable declaration hoisting
  - Closure variable detection
  - Scope chain management
  - 'with' statement rejection (stricter mode)

TODO: Implement closure compilation
  - Free variable identification
  - Closure creation bytecode
  - Variable reference opcodes

TODO: Implement optimizations
  - Short opcode forms (get_loc0-3, push_0-7)
  - Constant folding (optional)
  - Dead code elimination (optional)

Phase 4: Virtual Machine
-------------------------
TODO: Implement VM core (vm.py)
  - Bytecode interpreter loop
  - Value stack management
  - Call frame management
  - Exception handling (try/catch/finally)

TODO: Implement memory limits
  - Track allocated memory
  - Configurable memory limit
  - Out-of-memory exception

TODO: Implement time limits
  - Instruction counter or time check
  - Configurable execution timeout
  - Interrupt handler

TODO: Implement garbage collector
  - Object tracking
  - Mark-and-sweep or similar
  - Cycle detection
  - Weak references (if needed)

Phase 5: Built-in Objects
--------------------------
TODO: Implement Object (builtins/object.py)
  - Object() constructor
  - Object.create()
  - Object.defineProperty()
  - Object.getOwnPropertyDescriptor()
  - Object.getPrototypeOf()
  - Object.setPrototypeOf()
  - Object.keys(), Object.values(), Object.entries()
  - prototype methods: hasOwnProperty, toString, valueOf

TODO: Implement Array (builtins/array.py)
  - Array() constructor with stricter mode restrictions
  - length property (getter/setter)
  - Mutator methods: push, pop, shift, unshift, splice, reverse, sort
  - Accessor methods: concat, slice, indexOf, lastIndexOf, join
  - Iteration methods: forEach, map, filter, reduce, reduceRight, every, some
  - Array.isArray()

TODO: Implement String (builtins/string.py)
  - String() constructor (no boxing)
  - length property
  - charAt, charCodeAt, codePointAt
  - indexOf, lastIndexOf
  - slice, substring, substr
  - split, replace, replaceAll
  - toLowerCase, toUpperCase (ASCII only)
  - trim, trimStart, trimEnd
  - concat
  - String.fromCharCode, String.fromCodePoint

TODO: Implement Number (builtins/number.py)
  - Number() constructor (no boxing)
  - toFixed, toPrecision, toExponential
  - toString
  - parseInt, parseFloat (global)
  - isNaN, isFinite (global)
  - Number.isNaN, Number.isFinite, Number.isInteger

TODO: Implement Boolean (builtins/boolean.py)
  - Boolean() constructor (no boxing)
  - toString, valueOf

TODO: Implement Function (builtins/function.py)
  - Function() constructor
  - call, apply, bind
  - prototype property
  - length, name properties

TODO: Implement Math (builtins/math.py)
  - Constants: PI, E, LN2, LN10, LOG2E, LOG10E, SQRT2, SQRT1_2
  - abs, ceil, floor, round, trunc
  - min, max, pow, sqrt, cbrt
  - sin, cos, tan, asin, acos, atan, atan2
  - exp, log, log2, log10
  - random (with seed support for reproducibility)
  - sign, imul, clz32, fround

TODO: Implement JSON (builtins/json.py)
  - JSON.parse()
  - JSON.stringify()
  - Handle circular references
  - Replacer and reviver functions

TODO: Implement RegExp (builtins/regexp.py)
  - RegExp() constructor
  - exec, test methods
  - String integration: match, search, replace, split
  - Flags: g, i, m, s, u, y
  - Special characters and escapes
  - Character classes
  - Quantifiers
  - Groups and backreferences
  - Lookahead assertions

TODO: Implement Error types (builtins/error.py)
  - Error base class
  - TypeError, ReferenceError, SyntaxError
  - RangeError, URIError, EvalError
  - InternalError (for VM errors)
  - Stack trace support

TODO: Implement Date (builtins/date.py)
  - Date.now() only (per stricter mode)

TODO: Implement TypedArrays (builtins/typedarray.py)
  - ArrayBuffer
  - Uint8Array, Int8Array
  - Uint16Array, Int16Array
  - Uint32Array, Int32Array
  - Uint8ClampedArray
  - Float32Array, Float64Array
  - DataView (optional)

TODO: Implement console (builtins/console.py)
  - console.log()
  - Output capture for testing

TODO: Implement globalThis and global object

Phase 6: Testing
-----------------
TODO: Create pytest wrapper for JS tests
  - Load and execute .js test files
  - Capture output and errors
  - Assert no exceptions for passing tests

TODO: Make test_language.js pass
  - Basic operators
  - Type conversions
  - Increment/decrement
  - new operator
  - instanceof, in, typeof, delete
  - Prototype handling
  - Arguments object
  - Getters/setters

TODO: Make test_loop.js pass
  - while, do-while, for loops
  - for-in, for-of
  - break, continue with labels
  - switch statements
  - try/catch/finally

TODO: Make test_closure.js pass
  - Nested functions
  - Closure variable capture
  - Recursive functions

TODO: Make test_builtin.js pass
  - All built-in objects
  - All methods and properties
  - Edge cases

TODO: Make mandelbrot.js run
  - Complex number operations
  - Console output
  - Math functions

TODO: Make microbench.js run (optional performance test)

TODO: Make test_rect.js pass (requires C function interface - may skip)

Phase 7: Advanced Features
---------------------------
TODO: Implement memory limit enforcement
  - Track object allocations
  - Limit total memory usage
  - Graceful OOM handling

TODO: Implement time limit enforcement
  - Instruction counting
  - Timeout mechanism
  - Interruptible execution

TODO: Implement eval() (global only)
  - Parse and compile at runtime
  - Execute in global scope

TODO: Implement with strict mode validation
  - Reject 'with' statements
  - Require var declarations for globals
  - Other stricter mode checks

================================================================================
API DESIGN
================================================================================

The main public API should be simple and Pythonic:

```python
from mquickjs import JSContext

# Create a context with optional limits
ctx = JSContext(memory_limit=1024*1024, time_limit=5.0)

# Evaluate JavaScript code
result = ctx.eval("1 + 2")  # Returns Python int 3

# Evaluate with return value
result = ctx.eval("var x = [1,2,3]; x.map(n => n*2)")  # Returns [2,4,6]

# Access global variables
ctx.eval("var greeting = 'Hello'")
greeting = ctx.get("greeting")  # Returns "Hello"

# Set global variables
ctx.set("data", [1, 2, 3])
result = ctx.eval("data.length")  # Returns 3

# Handle errors
try:
    ctx.eval("throw new Error('oops')")
except JSError as e:
    print(e.message)  # "oops"

# Memory limit exceeded
try:
    ctx.eval("var a = []; while(true) a.push(1)")
except MemoryLimitError:
    print("Out of memory")

# Time limit exceeded
try:
    ctx.eval("while(true) {}")
except TimeLimitError:
    print("Execution timeout")
```

================================================================================
FILE STRUCTURE
================================================================================

mquickjs-python/
  src/
    mquickjs_python/
      __init__.py       # Public API exports
      context.py        # JSContext main class
      values.py         # JavaScript value types
      tokens.py         # Token definitions
      lexer.py          # Tokenizer
      parser.py         # Parser and compiler
      compiler.py       # Bytecode generation
      opcodes.py        # Opcode definitions
      vm.py             # Virtual machine
      runtime.py        # Runtime support
      builtins/
        __init__.py
        object.py
        array.py
        string.py
        number.py
        boolean.py
        function.py
        math.py
        json.py
        regexp.py
        error.py
        date.py
        typedarray.py
        console.py
      errors.py         # Exception classes
      gc.py             # Garbage collector
  tests/
    test_basic.py       # Python unit tests
    test_language.js    # JS test files from mquickjs
    test_loop.js
    test_closure.js
    test_builtin.js
    mandelbrot.js
    microbench.js
    test_rect.js
  spec.py               # This specification
  pyproject.toml
  LICENSE
  README.md

================================================================================
IMPLEMENTATION NOTES
================================================================================

1. UTF-8 STRING HANDLING
   - JavaScript uses UTF-16 internally, with surrogate pairs for chars > 0xFFFF
   - Python uses UTF-8 (or UTF-32 internally)
   - Need to handle length, indexing, and iteration correctly
   - String[i] should return UTF-16 code units, not Unicode codepoints

2. NUMBER HANDLING
   - JavaScript numbers are IEEE 754 doubles
   - MQuickJS optimizes 31-bit integers
   - Need to handle: NaN, Infinity, -Infinity, -0
   - Bitwise ops work on 32-bit integers

3. OBJECT IDENTITY
   - Objects have identity: {} !== {}
   - Need Python object identity for JS objects
   - Primitives compared by value

4. PROTOTYPE CHAIN
   - All objects have [[Prototype]] internal slot
   - Property lookup follows prototype chain
   - Constructor.prototype for new instances

5. GARBAGE COLLECTION
   - Track all allocated objects
   - Simple mark-and-sweep should suffice
   - May need weak references for some cases

6. ERROR HANDLING
   - JavaScript exceptions become Python exceptions
   - Need to preserve stack traces
   - Catch SyntaxError during parsing, runtime errors during execution

================================================================================
"""

# Version of this specification
SPEC_VERSION = "0.1.0"

# Target compatibility
TARGET_MQUICKJS_VERSION = "2025.01"

# Test files that should pass when implementation is complete
REQUIRED_TEST_FILES = [
    "test_language.js",
    "test_loop.js",
    "test_closure.js",
    "test_builtin.js",
    "mandelbrot.js",
]

# Optional test files
OPTIONAL_TEST_FILES = [
    "microbench.js",   # Performance benchmark
    "test_rect.js",    # Requires C function interface
]
