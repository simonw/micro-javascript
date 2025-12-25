# Open Problems in microjs

This document describes the known issues and limitations that remain as xfail tests in the microjs implementation.

## Deep Nesting / Recursion Limits

**Tests affected:**
- `test_deep_nested_parens`
- `test_deep_nested_braces`
- `test_deep_nested_arrays`
- `test_deep_nested_regex_groups`
- `test_large_eval_parse_stack` (from test_builtin.js)

**Problem:**
The parser uses recursive descent parsing, which relies on Python's call stack. When parsing deeply nested expressions (1000+ levels of parentheses, braces, or arrays), Python's recursion limit is exceeded.

**Root cause:**
Each level of nesting results in a recursive call to the parser:
- `(((1)))` → `_parse_expression` → `_parse_primary` → `_parse_expression` → ...
- `[[[1]]]` → `_parse_array` → `_parse_expression` → `_parse_array` → ...

Python's default recursion limit is ~1000, which limits nesting depth.

**Potential solutions:**
1. **Increase recursion limit:** `sys.setrecursionlimit(10000)` - simple but can cause stack overflow crashes
2. **Convert to iterative parsing:** Use explicit stacks instead of call stack. The original C QuickJS uses this approach with manual memory management
3. **Trampoline/CPS transformation:** Convert recursive calls to continuation-passing style with a trampoline loop

**Complexity:** High - requires significant parser restructuring

---

## Error Constructor Location Tracking

**Tests affected:**
- `test_error_constructor_has_line_number`
- `test_error_constructor_has_column_number`

**Problem:**
When creating an Error object with `new Error("message")`, the `lineNumber` and `columnNumber` properties should indicate where the Error was constructed. Currently they are `None` until the error is thrown.

**Root cause:**
The Error constructor is a Python function that doesn't have access to the VM's current source location. Only the `_throw` method in the VM sets line/column from the source map.

**Implemented behavior:**
- Thrown errors (`throw new Error(...)`) correctly get lineNumber/columnNumber from the throw statement location
- Constructed but not thrown errors have `None` for these properties

**Potential solutions:**
1. Pass a callback to the Error constructor that retrieves the current VM source location
2. Make Error construction go through a special VM opcode that captures location
3. Use Python stack introspection to find the calling location (hacky)

**Complexity:** Medium - requires threading location info through constructor calls

---


## Regex Test Suite Failures

**Tests affected:**
- `test_regexp` (from test_builtin.js)
- `test_mquickjs_js[test_builtin.js]`
- `test_mquickjs_js[microbench.js]`

**Problem:**
The comprehensive regex test suites from the original QuickJS contain tests that exercise edge cases not fully implemented.

**Known issues that were fixed:**
- Capture group reset in repetitions
- Empty alternative in repetition
- Surrogate pair handling in unicode mode
- Backspace escape in string literals

**Remaining issues:**
- Some edge cases with lookahead captures in optional groups
- Possible issues with complex backreference scenarios
- Unicode property escapes (if used in tests)

**Complexity:** Varies per issue

---

## Summary

| Category | Issue Count | Complexity |
|----------|-------------|------------|
| Deep nesting/recursion | 5 | High |
| Error location tracking | 2 | Medium |
| Comprehensive test suites | 4 | Varies |

**Total xfail tests:** 11

Most issues fall into two categories:
1. **Architectural limitations** (recursion, location tracking) - require significant refactoring
2. **Spec edge cases** - require careful ECMAScript spec analysis
