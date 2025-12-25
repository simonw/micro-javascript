# MQuickJS Python - Specification

A Pure Python JavaScript Sandbox Engine

This document provides a specification and TODO list for implementing a Python port
of the MQuickJS JavaScript engine. The goal is to create a sandboxed JavaScript
execution environment with memory and time limits, implemented entirely in Python
with no external dependencies.

Based on: https://github.com/bellard/mquickjs
License: MIT (see LICENSE file)

## Overview

MQuickJS is a minimal JavaScript engine supporting a subset close to ES5 with
"stricter mode" - a subset of JavaScript that works in standard engines but
disables error-prone or inefficient constructs.

Key design principles for the Python port:
- Pure Python implementation (no C extensions, no dependencies)
- Sandboxed execution with configurable memory and time limits
- Support for the MQuickJS JavaScript subset (stricter mode)
- Stack-based bytecode VM similar to the original

## JavaScript Subset Supported (Stricter Mode)

The engine supports a subset of JavaScript with these restrictions:

### 1. Strict Mode Only
- All code runs in strict mode
- No 'with' keyword
- Global variables must be declared with 'var'

### 2. Arrays
- No holes allowed (sparse arrays not supported)
- Out-of-bound writes are errors (except appending at end)
- Array literals with holes are syntax errors: `[1, , 3]`
- `new Array(len)` creates array with undefined elements

### 3. Eval
- Only global (indirect) eval is supported: `(1, eval)('code')`
- Direct eval is forbidden: `eval('code')`

### 4. No Value Boxing
- `new Number(1)`, `new Boolean(true)`, `new String("s")` not supported
- Primitive values are used directly

### 5. Property Restrictions
- All properties are writable, enumerable, and configurable
- 'for...in' only iterates over own properties

### 6. Other Restrictions
- Date: only `Date.now()` is supported
- String case functions: only ASCII characters
- RegExp: case folding only for ASCII

## Architecture

The implementation consists of the following main components:

### 1. Lexer (lexer.py)
- Converts JavaScript source code into tokens
- Handles string literals, numbers, identifiers, operators
- Unicode support (UTF-8 internal storage)

### 2. Parser (parser.py)
- Recursive descent parser (non-recursive to bound stack usage)
- Produces bytecode directly (no AST intermediate representation)
- One-pass compilation with optimization

### 3. Bytecode Compiler (compiler.py)
- Generates stack-based bytecode
- Handles scope resolution, closures, variable references
- Optimizes short jumps, common patterns

### 4. Virtual Machine (vm.py)
- Stack-based bytecode interpreter
- Implements all opcodes
- Memory and time limit enforcement

### 5. Runtime (runtime.py)
- JavaScript value representation
- Object model (objects, arrays, functions, closures)
- Garbage collection (tracing GC)

### 6. Built-in Objects (builtins/)
- Object, Array, String, Number, Boolean, Function
- Math, JSON, RegExp, Error types
- TypedArrays: Uint8Array, Int8Array, etc.

### 7. Context (context.py)
- Execution context management
- Global object
- Memory and time limit configuration

## Data Types

JavaScript values in the Python implementation:

### Primitive Types
- `undefined`: singleton JSUndefined
- `null`: singleton JSNull
- `boolean`: Python bool (True/False)
- `number`: Python int or float (31-bit ints optimized)
- `string`: Python str (UTF-8, with surrogate pair handling)

### Object Types
- `JSObject`: base class for all objects
- `JSArray`: array object with special length handling
- `JSFunction`: JavaScript function (closure)
- `JSCFunction`: native Python function callable from JS
- `JSRegExp`: regular expression object
- `JSError`: error object (TypeError, ReferenceError, etc.)
- `JSTypedArray`: typed array views (Uint8Array, etc.)
- `JSArrayBuffer`: raw binary data buffer

## Bytecode Opcodes

Based on mquickjs_opcode.h, the VM uses these opcodes:

### Stack Manipulation
- `push_value`, `push_const`, `push_i8`, `push_i16`
- `push_0` through `push_7`, `push_minus1`
- `undefined`, `null`, `push_true`, `push_false`
- `drop`, `dup`, `dup1`, `dup2`, `swap`, `rot3l`, `nip`, `perm3`, `perm4`
- `insert2`, `insert3`

### Control Flow
- `if_false`, `if_true`, `goto`
- `call`, `call_method`, `call_constructor`, `return`, `return_undef`
- `throw`, `catch`, `gosub`, `ret` (for finally blocks)
- `for_in_start`, `for_of_start`, `for_of_next`

### Variables and Properties
- `get_loc`, `put_loc`, `get_loc0-3`, `put_loc0-3`
- `get_arg`, `put_arg`, `get_arg0-3`, `put_arg0-3`
- `get_var_ref`, `put_var_ref`
- `get_field`, `get_field2`, `put_field`
- `get_array_el`, `get_array_el2`, `put_array_el`
- `get_length`, `get_length2`
- `define_field`, `define_getter`, `define_setter`, `set_proto`

### Arithmetic/Logic
- `add`, `sub`, `mul`, `div`, `mod`, `pow`
- `neg`, `plus`, `inc`, `dec`, `post_inc`, `post_dec`
- `shl`, `sar`, `shr`, `and`, `or`, `xor`, `not`
- `lt`, `lte`, `gt`, `gte`, `eq`, `neq`, `strict_eq`, `strict_neq`
- `lnot`, `typeof`, `delete`, `instanceof`, `in`

### Objects
- `object`, `array_from`, `fclosure`, `fclosure8`
- `push_this`, `this_func`, `arguments`, `new_target`
- `regexp`

## TODO List

### Phase 1: Core Infrastructure
- [x] Set up project structure with uv
- [x] Copy test files from mquickjs
- [x] Create basic pytest test harness
- [x] Write this spec
- [x] Create base value types (values.py)
- [x] Create token types (tokens.py)
- [x] Implement lexer (lexer.py) - 54 TDD tests passing

### Phase 2: Parser
- [x] Implement expression parser
- [x] Implement statement parser
- [x] Implement function parsing
- [x] Implement object/array literal parsing
- [x] AST node types (ast_nodes.py) - 59 TDD tests passing

### Phase 3: Compiler
- [x] Implement bytecode generation
- [x] Implement scope analysis
- [x] Implement closure compilation
- [ ] Implement optimizations

### Phase 4: Virtual Machine
- [x] Implement VM core (vm.py)
- [x] Implement Context public API (context.py)
- [ ] Implement memory limits (basic structure exists)
- [ ] Implement time limits (basic structure exists)
- [ ] Implement garbage collector

### Phase 5: Built-in Objects
- [ ] Object (basic)
- [ ] Array (basic)
- [ ] String
- [ ] Number
- [ ] Boolean
- [ ] Function
- [ ] Math
- [ ] JSON
- [ ] RegExp
- [ ] Error types
- [ ] Date (Date.now only)
- [ ] TypedArrays
- [x] console (basic log)

### Phase 6: Testing
- [ ] Make test_language.js pass
- [ ] Make test_loop.js pass
- [ ] Make test_closure.js pass
- [ ] Make test_builtin.js pass
- [ ] Make mandelbrot.js run

### Phase 7: Advanced Features
- [ ] Memory limit enforcement
- [ ] Time limit enforcement
- [ ] eval() (global only)
- [ ] Strict mode validation

## API Design

The main public API should be simple and Pythonic:

```python
from microjs import Context

# Create a context with optional limits
ctx = Context(memory_limit=1024*1024, time_limit=5.0)

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

## File Structure

```
microjs/
  src/
    microjs/
      __init__.py       # Public API exports
      context.py        # Context main class
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
  tests/
    basic/              # Incremental test files
    test_js_basic.py    # Parameterized test runner
    test_language.js    # JS test files from mquickjs
    test_loop.js
    test_closure.js
    test_builtin.js
    mandelbrot.js
    microbench.js
    test_rect.js
  spec.md               # This specification
  pyproject.toml
  LICENSE
  README.md
```

## Implementation Notes

### 1. UTF-8 String Handling
- JavaScript uses UTF-16 internally, with surrogate pairs for chars > 0xFFFF
- Python uses UTF-8 (or UTF-32 internally)
- Need to handle length, indexing, and iteration correctly
- `String[i]` should return UTF-16 code units, not Unicode codepoints

### 2. Number Handling
- JavaScript numbers are IEEE 754 doubles
- MQuickJS optimizes 31-bit integers
- Need to handle: NaN, Infinity, -Infinity, -0
- Bitwise ops work on 32-bit integers

### 3. Object Identity
- Objects have identity: `{} !== {}`
- Need Python object identity for JS objects
- Primitives compared by value

### 4. Prototype Chain
- All objects have `[[Prototype]]` internal slot
- Property lookup follows prototype chain
- `Constructor.prototype` for new instances

### 5. Garbage Collection
- Track all allocated objects
- Simple mark-and-sweep should suffice
- May need weak references for some cases

### 6. Error Handling
- JavaScript exceptions become Python exceptions
- Need to preserve stack traces
- Catch SyntaxError during parsing, runtime errors during execution

## Version Information

- Specification Version: 0.1.0
- Target MQuickJS Version: 2025.01

## Test Files

### Required (must pass)
- test_language.js
- test_loop.js
- test_closure.js
- test_builtin.js
- mandelbrot.js

### Optional
- microbench.js (performance benchmark)
- test_rect.js (requires C function interface)
