# microjs

A pure Python JavaScript engine, inspired by [MicroQuickJS](https://github.com/bellard/mquickjs).

## Overview

This project provides a JavaScript execution environment with:

- **Memory limits** - Configurable maximum memory usage
- **Time limits** - Configurable execution timeout
- **Pure Python** - No C extensions or external dependencies
- **Broad ES5+ support** - Variables, functions, closures, classes, iterators, promises, regex, and more

## Usage

```python
from microjs import JSContext

# Create a context with optional limits
ctx = JSContext(memory_limit=1024*1024, time_limit=5.0)

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

## Supported Features

- **Core**: variables, operators, control flow, functions, closures
- **Objects**: object literals, prototypes, getters/setters, JSON
- **Arrays**: literals, methods (map, filter, reduce, etc.), typed arrays
- **Functions**: arrow functions, rest/spread, default parameters
- **Classes**: class syntax, inheritance, static methods
- **Iteration**: for-of, iterators, generators
- **Async**: Promises, async/await
- **Regex**: Full regex support with capture groups, lookahead/lookbehind
- **Error handling**: try/catch/finally with stack traces

## Known Limitations

See [open-problems.md](open-problems.md) for details on:
- Deep nesting limits (parser uses recursion)
- Some regex edge cases with optional lookahead captures
- Error constructor location tracking

## Development

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Run tests
uv run pytest
```

## License

MIT License - see [LICENSE](LICENSE) file.

Based on MicroQuickJS by Fabrice Bellard.
