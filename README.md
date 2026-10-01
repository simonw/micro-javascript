# micro-javascript

[![PyPI](https://img.shields.io/pypi/v/micro-javascript.svg)](https://pypi.org/project/micro-javascript/)
[![Changelog](https://img.shields.io/github/v/release/simonw/micro-javascript?include_prereleases&label=changelog)](https://github.com/simonw/micro-javascript/releases)
[![Tests](https://github.com/simonw/micro-javascript/workflows/Test/badge.svg)](https://github.com/simonw/micro-javascript/actions?query=workflow%3ATest)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/simonw/micro-javascript/blob/main/LICENSE)

A pure Python JavaScript engine, inspired by [MicroQuickJS](https://github.com/bellard/mquickjs).

## Overview

This project provides a JavaScript execution environment with:

- **Memory limits** - Configurable maximum memory usage
- **Time limits** - Configurable execution timeout
- **Pure Python** - No C extensions or external dependencies
- **An ES5 subset of JavaScript** - the language supported by MicroQuickJS, plus arrow functions and `for...of` (see [Supported features](#supported-features))

> [!WARNING]
> The sandbox is **not production ready**. Memory use is estimated rather than measured exactly, and the engine has not been fully audited against escapes that could allow JavaScript to run arbitrary Python. See the [sandbox issue label](https://github.com/simonw/micro-javascript/issues?q=label%3A%22sandbox%22) for more.

## Interactive demos

Try [playground.html](https://simonw.github.io/micro-javascript/playground.html) in your browser to execute JavaScript using this Python library run via [Pyodide](https://pyodide.org/) (so JavaScript in Python in WebAssembly in JavaScript).

Use [parser-playground.html](https://simonw.github.io/micro-javascript/parser-playground.html) to see how the `micro-javascript` tokenizer and parser works with different JavaScript code.

## How it was built

Most of this library was built using Claude Code for web - [here is the 15+ hour transcript](https://static.simonwillison.net/static/2025/claude-code-microjs/index.html).

## Installation

```bash
pip install micro-javascript
```

## Usage

```python
from microjs import Context

# Create a context with optional limits
ctx = Context(memory_limit=1024*1024, time_limit=5.0)

# Evaluate JavaScript code
result = ctx.eval("1 + 2")  # Returns 3

# Functions and closures
ctx.eval("""
    function makeCounter() {
        var count = 0;
        return function() { return ++count; };
    }
    var counter = makeCounter();
""")
assert ctx.eval("counter()") == 1
assert ctx.eval("counter()") == 2

# Regular expressions
result = ctx.eval('/hello (\\w+)/.exec("hello world")')
# Returns ['hello world', 'world']

# Error handling with line/column tracking
ctx.eval("""
try {
    throw new Error("oops");
} catch (e) {
    // e.lineNumber and e.columnNumber are set
}
""")
```

## Setting and Getting Variables

Use `set()` and `get()` to pass values between Python and JavaScript:

```python
ctx = Context()

# Set a Python value as a JavaScript global variable
ctx.set("x", 42)
ctx.set("name", "Alice")
ctx.set("items", [1, 2, 3])

# Use the variable in JavaScript
result = ctx.eval("x * 2")  # Returns 84
result = ctx.eval("'Hello, ' + name")  # Returns 'Hello, Alice'
result = ctx.eval("items.map(n => n * 2)")  # Returns [2, 4, 6]

# Get a JavaScript variable back into Python
ctx.eval("var total = items.reduce((a, b) => a + b, 0)")
total = ctx.get("total")  # Returns 6
```

## Exposing Python Functions to JavaScript

You can expose Python functions to JavaScript by setting them as global variables:

```python
ctx = Context()

# Define a Python function
def add(a, b):
    return a + b

# Expose it to JavaScript
ctx.set("add", add)

# Call it from JavaScript
result = ctx.eval("add(2, 3)")  # Returns 5
```

Primitive values (numbers, strings, booleans) are passed directly as Python types, and primitives returned from Python functions work in JavaScript.

Arrays and objects are passed as internal JavaScript types (`JSArray`, `JSObject`). To return objects that JavaScript can use, return `JSObject` instances:

```python
from microjs.values import JSObject, JSArray

ctx = Context()

# Access array elements via ._elements
def sum_array(arr):
    return sum(arr._elements)

ctx.set("sumArray", sum_array)
result = ctx.eval("sumArray([1, 2, 3, 4, 5])")  # Returns 15

# Return a JSObject for JavaScript to use
def make_point(x, y):
    obj = JSObject()
    obj.set("x", x)
    obj.set("y", y)
    return obj

ctx.set("makePoint", make_point)
result = ctx.eval("var p = makePoint(10, 20); p.x + p.y;")  # Returns 30
```

## Resource limits

`time_limit` is in seconds. It covers everything a script does, including long-running built-in functions and code run by `eval()`.

`memory_limit` is in bytes and applies to the data a script keeps alive, not counting the built-in objects. The engine tallies allocations as they happen; when the tally could exceed the limit it measures everything still reachable, much as a garbage collector would, so a script that creates lots of short-lived garbage is fine. Single large allocations such as `"x".repeat(n)` or `new Array(n)` are refused before they are made. The size of each value is an estimate, so treat the limit as approximate.

Exceeding either limit raises `TimeLimitError` or `MemoryLimitError`, which JavaScript code cannot catch:

```python
from microjs import Context, MemoryLimitError

ctx = Context(memory_limit=1024 * 1024, time_limit=5.0)
try:
    ctx.eval("var s = 'x'; while (true) s = s + s")
except MemoryLimitError:
    hit_limit = True  # Returns True
```

Like other JavaScript engines, micro-javascript also throws a catchable `RangeError` for invalid array lengths, strings longer than 536,870,888 characters and call stacks more than 10,000 calls deep, whether or not limits are set.

## Handling errors

An uncaught JavaScript exception is raised as a `JSError`, or as the subclass matching its type: `JSTypeError`, `JSReferenceError`, `JSRangeError` or `JSSyntaxError`. The thrown value is available as `.value`:

```python
from microjs import Context, JSError, JSReferenceError

ctx = Context()
try:
    ctx.eval("missing()")
except JSReferenceError as e:
    message = str(e)  # Returns 'ReferenceError: missing is not defined'

try:
    ctx.eval("throw {code: 42}")
except JSError as e:
    value = e.value  # Returns {'code': 42}
```

Exceptions raised by Python functions you expose become JavaScript errors named `InternalError`, which scripts can catch. If nothing catches one, the original Python exception is the `__cause__` of the resulting `JSError`. `TimeLimitError` and `MemoryLimitError` can never be caught by JavaScript.

## Supported features

micro-javascript implements roughly the subset of JavaScript supported by MicroQuickJS: ES5, plus arrow functions, `for...of` and regex lookbehind. The test suite runs every line of this example and checks each `// =>` result:

```javascript
// Functions, closures and arrow functions
function makeCounter() {
    var count = 0;
    return function () { return ++count; };
}
var counter = makeCounter();
counter(); counter();  // => 2
[1, 2, 3].map(x => x * 2).filter(x => x > 2).join(",");  // => "4,6"

// Constructors, prototypes, getters and setters
function Point(x, y) { this.x = x; this.y = y; }
Point.prototype.sum = function () { return this.x + this.y; };
new Point(1, 2).sum();  // => 3
var temp = { c: 20, get f() { return this.c * 9 / 5 + 32; } };
temp.f;  // => 68
var key = "dynamic";
({ [key]: 1 }).dynamic;  // => 1

// Labelled break, for...in and for...of
var found = null;
outer: for (var i = 0; i < 3; i++) {
    for (var j = 0; j < 3; j++) {
        if (i * j === 2) { found = [i, j]; break outer; }
    }
}
found;  // => [1, 2]
var keys = []; for (var k in { a: 1, b: 2 }) keys.push(k);
keys;  // => ["a", "b"]

// Exceptions
var caught;
try { null.x; } catch (e) { caught = e.name; } finally { caught += "!"; }
caught;  // => "TypeError!"

// Regular expressions, including lookbehind
/(\d+)-(\d+)/.exec("10-20");  // => ["10-20", "10", "20"]
"2026-10-01".replace(/-/g, "/");  // => "2026/10/01"
"a1b2".replace(/\d/g, d => d * 2);  // => "a2b4"
/(?<=\$)\d+/.exec("cost: $42")[0];  // => "42"

// Built-ins live on prototypes that scripts can use and extend
Array.prototype.slice.call({ length: 2, 0: "a", 1: "b" }).join("+");  // => "a+b"
Array.from("abc", c => c.toUpperCase()).join("");  // => "ABC"
[1, [2, [3, [4]]]].flat(Infinity).length;  // => 4
var frozen = Object.freeze({ x: 1 });
Object.isFrozen(frozen);  // => true

// JSON, Math and typed arrays
JSON.stringify({ a: [1, { b: true }] });  // => '{"a":[1,{"b":true}]}'
Math.max(3, 7, 5);  // => 7
var bytes = new Uint8Array(2); bytes[0] = 300;
bytes[0];  // => 44

// Indirect (global) eval
(1, eval)("6 * 7");  // => 42
```

## Not supported

These raise a `SyntaxError` or are undefined:

- `let`, `const`, `class`, generators, `async`/`await` and `Promise`
- Template literals, destructuring, spread, and rest or default parameters
- Optional chaining (`?.`) and nullish coalescing (`??`)
- `Symbol`, `Map`, `Set`, `WeakMap`, `Proxy`, `Reflect` and `BigInt`
- Iterators and the methods that return them (`Array.prototype.keys`, `String.prototype.matchAll`, ...), `globalThis` and `String.raw`
- `Date` beyond `Date.now()`, and `Error.prototype.stack` (always empty)

Like MicroQuickJS, arrays are dense: `[1, , 3]` is a `SyntaxError`, and writing to an index beyond the end of an array (rather than appending at the end) throws a `TypeError`.

Strings are sequences of Unicode code points rather than UTF-16 code units, so a character outside the Basic Multilingual Plane such as `"😀"` has a `length` of 1, not 2.

See [open-problems.md](https://github.com/simonw/micro-javascript/blob/main/open-problems.md) for known bugs that are tracked as expected-failure tests.

## Development

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Run tests
uv run pytest
```

## License

MIT License - see [LICENSE](https://github.com/simonw/micro-javascript/blob/main/LICENSE) file.

Based on MicroQuickJS by Fabrice Bellard.
