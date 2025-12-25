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
- **Broad ES5+ support** - Variables, functions, closures, classes, iterators, promises, regex, and more

## How it was built

Most of this library was built using Claude Code for web - [here is the 15+ hour transcript](https://static.simonwillison.net/static/2025/claude-code-microjs/index.html).

## Installation

```bash
pip install micro-javascript
```

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

See [open-problems.md]([open-problems.md](https://github.com/simonw/micro-javascript/blob/main/open-problems.md)) for details on:
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

MIT License - see [LICENSE](https://github.com/simonw/micro-javascript/blob/main/LICENSE) file.

Based on MicroQuickJS by Fabrice Bellard.
