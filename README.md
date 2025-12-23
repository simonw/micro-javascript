# microjs

A pure Python JavaScript sandbox engine based on [MQuickJS](https://github.com/bellard/mquickjs).

## Overview

This project aims to provide a sandboxed JavaScript execution environment with:

- **Memory limits** - Configurable maximum memory usage
- **Time limits** - Configurable execution timeout
- **Pure Python** - No C extensions or external dependencies
- **ES5 subset** - Supports JavaScript "stricter mode" (a safe subset of ES5)

## Installation

```bash
pip install microjs
```

## Usage

```python
from microjs import JSContext

# Create a context with optional limits
ctx = JSContext(memory_limit=1024*1024, time_limit=5.0)

# Evaluate JavaScript code
result = ctx.eval("1 + 2")  # Returns 3
```

## Development

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Install development dependencies
uv sync

# Run tests
uv run pytest
```

## License

MIT License - see [LICENSE](LICENSE) file.

Based on MQuickJS by Fabrice Bellard and Charlie Gordon.
