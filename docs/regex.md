# Regex Engine Python API

The `microjs.regex` module provides a sandboxed regular expression engine with:

- ReDoS protection (zero-advance detection)
- Memory limits via backtrack stack size
- Timeout integration via polling callbacks
- JavaScript regular expression compatibility

> [!WARNING]
> The sandbox is **not production ready**. ReDoS attacks may still be possible. See the [sandbox issue label](https://github.com/simonw/micro-javascript/issues?q=label%3A%22sandbox%22) for more.

## Quick Start

```python
from microjs.regex import RegExp, test, search, match

# Simple pattern matching
if test(r"\d+", "abc123"):
    print("Found digits!")

# Search for a pattern
result = search(r"(\w+)@(\w+)", "user@host")
if result:
    print(f"Full match: {result[0]}")  # "user@host"
    print(f"User: {result[1]}")         # "user"
    print(f"Host: {result[2]}")         # "host"

# Using RegExp object for repeated matching
re = RegExp(r"\w+", "g")  # global flag
text = "hello world"
while (m := re.exec(text)):
    print(m[0])  # "hello", then "world"
```

## Module Reference

### RegExp Class

```python
class RegExp:
    def __init__(
        self,
        pattern: str,
        flags: str = "",
        poll_callback: Optional[Callable[[], bool]] = None,
        stack_limit: int = 10000,
        poll_interval: int = 100,
    ):
```

**Parameters:**

- `pattern` - The regex pattern string
- `flags` - Optional flags string:
  - `g` - Global matching (find all matches)
  - `i` - Case-insensitive matching
  - `m` - Multiline mode (^ and $ match line boundaries)
  - `s` - DotAll mode (. matches newlines)
  - `u` - Unicode mode
  - `y` - Sticky mode (match only at lastIndex)
- `poll_callback` - Called periodically during matching; return `True` to abort
- `stack_limit` - Maximum backtrack stack size (default: 10000)
- `poll_interval` - Steps between poll callback calls (default: 100)

**Properties:**

- `source` - The pattern string
- `flags` - The flags string
- `lastIndex` - Current position for global/sticky matching
- `global_` - Whether the `g` flag is set
- `ignoreCase` - Whether the `i` flag is set
- `multiline` - Whether the `m` flag is set
- `dotAll` - Whether the `s` flag is set
- `unicode` - Whether the `u` flag is set
- `sticky` - Whether the `y` flag is set

#### RegExp.test(string)

Test if the pattern matches the string.

```python
re = RegExp(r"\d+")
re.test("abc123")  # True
re.test("abc")     # False
```

**Returns:** `bool`

#### RegExp.exec(string)

Execute a search for a match.

```python
re = RegExp(r"(\w+)@(\w+)")
result = re.exec("user@host.com")
if result:
    print(result[0])     # "user@host"
    print(result[1])     # "user"
    print(result[2])     # "host"
    print(result.index)  # 0
```

**Returns:** `MatchResult` or `None`

### MatchResult Class

Returned by `RegExp.exec()` on successful matches.

**Properties:**

- `index` - The position where the match starts
- `input` - The original input string

**Methods:**

- `__getitem__(idx)` - Get capture group by index (0 = full match)
- `__len__()` - Number of groups (including group 0)
- `group(idx=0)` - Get capture group by index
- `groups()` - Get all capture groups except group 0 as a tuple

```python
result = RegExp(r"(\w+)-(\d+)").exec("item-42")
result[0]        # "item-42"
result[1]        # "item"
result[2]        # "42"
result.groups()  # ("item", "42")
result.index     # 0
```

### Convenience Functions

#### test(pattern, string, flags="")

Test if pattern matches string.

```python
from microjs.regex import test

test(r"\d+", "abc123")  # True
```

#### search(pattern, string, flags="")

Search for pattern in string.

```python
from microjs.regex import search

result = search(r"\d+", "abc123")
result[0]  # "123"
```

#### match(pattern, string, flags="")

Match pattern against string (alias for search).

```python
from microjs.regex import match

result = match(r"\d+", "abc123")
result[0]  # "123"
```

## Timeout Integration

To prevent ReDoS attacks, pass a `poll_callback` that returns `True` to abort:

```python
import time

start = time.monotonic()
timeout = 1.0  # 1 second timeout

def check_timeout() -> bool:
    return time.monotonic() - start > timeout

re = RegExp(r"(a+)+b", poll_callback=check_timeout)
try:
    # This pattern causes catastrophic backtracking
    re.test("a" * 30 + "c")
except RegexTimeoutError:
    print("Regex timed out!")
```

The poll callback is called every `poll_interval` steps (default: 100).

## Exceptions

### RegExpError

Raised for invalid regex patterns.

```python
from microjs.regex import RegExp, RegExpError

try:
    RegExp(r"[")  # Unclosed bracket
except RegExpError as e:
    print(f"Invalid pattern: {e}")
```

### RegexTimeoutError

Raised when the poll callback returns `True`.

```python
from microjs.regex import RegExp, RegexTimeoutError

def abort():
    return True

try:
    RegExp(r".*", poll_callback=abort).test("hello")
except RegexTimeoutError:
    print("Aborted!")
```

### RegexStackOverflow

Raised when the backtrack stack exceeds `stack_limit`.

```python
from microjs.regex import RegExp, RegexStackOverflow

try:
    # Very small stack limit
    RegExp(r"(a+)+b", stack_limit=10).test("aaaaac")
except RegexStackOverflow:
    print("Stack overflow!")
```

## Global Matching Example

```python
from microjs.regex import RegExp

re = RegExp(r"\w+", "g")
text = "hello world foo bar"

matches = []
while (m := re.exec(text)):
    matches.append(m[0])

print(matches)  # ["hello", "world", "foo", "bar"]
```

## Integration with microjs Context

When using the JavaScript context, regex timeout is automatically integrated:

```python
from microjs import Context, TimeLimitError

ctx = Context(time_limit=1.0)

try:
    ctx.eval('''
        var re = /(a+)+b/;
        re.test("a".repeat(30) + "c");
    ''')
except TimeLimitError:
    print("Execution timed out!")
```
