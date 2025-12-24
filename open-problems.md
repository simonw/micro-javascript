# Open Problems in mquickjs-python

This document describes the known issues and limitations that remain as xfail tests in the mquickjs-python implementation.

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

## SyntaxError Position Tracking

**Tests affected:**
- `test_syntax_error_position`

**Problem:**
When a SyntaxError occurs during parsing, the error message should include the line and column where the error occurred.

**Current behavior:**
The parser throws `JSSyntaxError` with line/column information, but this may not be propagated correctly to the final error message format.

**Potential solution:**
Update the error message formatting in `JSSyntaxError` to include position in a standard format like "SyntaxError at line 2, column 5: unexpected token".

**Complexity:** Low

---

## Optional Lookahead Capture Semantics

**Tests affected:**
- `test_optional_lookahead_no_match`
- `test_repeated_optional_lookahead`

**Problem:**
Pattern `/(?:(?=(abc)))?a/` on string `"abc"` should return `['a', None]` but returns `['a', 'abc']`.

**Explanation:**
The pattern has an optional non-capturing group containing a lookahead with a capture:
1. `(?:...)?` - optional group
2. `(?=(abc))` - lookahead that captures 'abc'
3. `a` - literal match

The lookahead succeeds (there's 'abc' ahead), captures 'abc', and the match proceeds. But the test expects the capture to be `None`.

**Root cause:**
This appears to be an edge case in ECMAScript regex semantics where captures inside optional groups that don't "contribute" to advancing the match should be reset. The exact semantics are complex and may require deeper ECMAScript spec analysis.

**Current behavior:**
- The lookahead runs and captures
- The capture is preserved because we don't backtrack (the match succeeds)

**Expected behavior (per test):**
- Even though the lookahead "succeeded", because it's inside an optional group that could have been skipped, the capture should be undefined

**Potential solutions:**
1. Research ECMAScript spec section 21.2.2 (RegExp semantics) for exact rules
2. Compare with test262 tests for conformance
3. May require tracking whether an optional path was "necessary" vs "optional"

**Complexity:** High - requires deep understanding of ECMAScript regex semantics

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
| Error location tracking | 3 | Low-Medium |
| Lookahead capture semantics | 2 | High |
| Comprehensive test suites | 4 | Varies |

**Total xfail tests:** 14

Most issues fall into two categories:
1. **Architectural limitations** (recursion, location tracking) - require significant refactoring
2. **Spec edge cases** (lookahead captures) - require careful ECMAScript spec analysis
