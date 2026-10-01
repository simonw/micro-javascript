# Open Problems in microjs

This document describes the known issues and limitations that remain as xfail tests in the microjs implementation.

## Deep Nesting / Recursion Limits ✅ RESOLVED

**Tests affected:**
- `test_deep_nested_parens` ✅ Now passing
- `test_deep_nested_braces` ✅ Now passing
- `test_deep_nested_arrays` ✅ Now passing
- `test_deep_nested_regex_groups` (regex parser, still xfail)
- `test_large_eval_parse_stack` ✅ Now passing (in `test_builtin_funcs.py`)

**Solution implemented:**
Converted key parsing paths to use iterative approaches with explicit stacks:

1. **Parser changes (`parser.py`):**
   - Consecutive parentheses `((((1))))` are now handled iteratively
   - Nested array literals `[[[[1]]]]` use a stack-based approach
   - Block statements `{{{{1;}}}}` are parsed iteratively
   - Added `_parse_block_statement_iterative()` and `_parse_nested_arrays()` methods
   - Added `_continue_parsing_expression()` for handling operators between nested parens

2. **Compiler changes (`compiler.py`):**
   - `MemberExpression` chains are compiled iteratively (for deep `a[0][0][0]...`)
   - `ArrayExpression` compilation uses a work stack instead of recursion
   - `BlockStatement` compilation is iterative
   - `_compile_statement_for_value()` drills through nested blocks iteratively

**Inspiration:**
The approach was inspired by mquickjs's continuation-passing style parser,
though we use a simpler Python-friendly stack-based approach rather than
the full CPS transformation.

**Remaining issue:**
- Regex parser (`regex/parser.py`) still uses recursion for nested groups
- This affects `test_deep_nested_regex_groups`

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


## Upstream Test Suite Failures

**Tests affected:**
- `test_regexp` and `test_mquickjs_js[test_builtin.js]`: the regex tests now
  pass up to a pattern with thousands of nested groups, which exceeds the
  recursion of the regex parser (the same issue as
  `test_deep_nested_regex_groups` above).
- `test_line_column_numbers`: reports error positions through
  `Error.prototype.stack`, which is not implemented. The positions themselves
  (`lineNumber`, `columnNumber` and syntax error locations) are correct.
- `test_mquickjs_js[microbench.js]`: the benchmark expects `scriptArgs`, a
  global provided by the QuickJS command-line shell, rather than failing on an
  engine bug.

**Known issues that were fixed:**
- Capture group reset in repetitions
- Empty alternative in repetition
- Surrogate pair handling in unicode mode
- Backspace escape in string literals
- Case-insensitive negated character classes (`/[^A-B]/i` matched `"a"`)

---

## Summary

Remaining xfail tests (pytest runs with `xfail_strict = true`, so any of these
starting to pass will fail the suite until the marker is removed):

| Test | Category |
|------|----------|
| `test_known_issues.py::TestDeepNesting::test_deep_nested_regex_groups` | Regex parser recursion |
| `test_known_issues.py::TestErrorLineColumn::test_error_constructor_has_line_number` | Error location tracking |
| `test_known_issues.py::TestErrorLineColumn::test_error_constructor_has_column_number` | Error location tracking |
| `test_builtin_funcs.py::test_builtin_function[test_regexp]` | Regex edge cases |
| `test_builtin_funcs.py::test_builtin_function[test_line_column_numbers]` | Error location tracking |
| `test_js_basic.py::test_mquickjs_js[test_builtin.js]` | Full upstream suite |
| `test_js_basic.py::test_mquickjs_js[microbench.js]` | Full upstream suite |

**Total xfail tests:** 7

**Resolved:**
- Deep nesting for parentheses, arrays, and block statements now works with 1000+ levels
- `test_large_eval_parse_stack` from `test_builtin.js` now passes
