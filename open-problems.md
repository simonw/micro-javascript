# Open Problems in microjs

This document describes the known issues and limitations that remain as xfail tests in the microjs implementation.

## Deep Nesting / Recursion Limits ✅ RESOLVED

**Tests affected:**
- `test_deep_nested_parens` ✅ Now passing
- `test_deep_nested_braces` ✅ Now passing
- `test_deep_nested_arrays` ✅ Now passing
- `test_deep_nested_regex_groups` (regex parser, still xfail)
- `test_large_eval_parse_stack` ✅ Now passing

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

| Category | Issue Count | Status |
|----------|-------------|--------|
| Deep nesting/recursion | 5 → 1 | ✅ Mostly resolved |
| Error location tracking | 2 | Medium complexity |
| Lookahead capture semantics | 2 | High complexity |
| Comprehensive test suites | 4 | Varies |

**Total xfail tests:** 10 (down from 14)

Most remaining issues fall into two categories:
1. **Spec edge cases** (lookahead captures) - require careful ECMAScript spec analysis
2. **Location tracking** - requires threading location info through constructor calls

**Resolved:**
- Deep nesting for parentheses, arrays, and block statements now works with 1000+ levels
