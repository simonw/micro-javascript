"""
Parameterized pytest tests for test_builtin.js functions.

This file loads test_builtin.js and runs each test function as a separate
pytest test case, providing better visibility into which specific tests pass/fail.
"""
import re
from pathlib import Path

import pytest

from microjs import JSContext


def get_test_functions_from_js(js_file_path: Path) -> list[tuple[str, str]]:
    """
    Extract test function names from a JavaScript file.

    Detects files that define test functions and call them at the end.
    Returns list of (function_name, js_code) tuples.
    """
    content = js_file_path.read_text(encoding="utf-8")

    # Find all function declarations that start with "test"
    func_pattern = re.compile(r'function\s+(test\w*)\s*\(')
    test_funcs = func_pattern.findall(content)

    if not test_funcs:
        return []

    # Remove the test invocations at the end of the file
    # These are lines like "test();" or "test_string();" at module level
    lines = content.split('\n')
    func_only_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip lines that are just test function calls (not inside a function)
        if stripped and re.match(r'^test\w*\(\);?$', stripped):
            continue
        func_only_lines.append(line)

    func_code = '\n'.join(func_only_lines)

    return [(name, func_code) for name in test_funcs]


def get_builtin_test_cases():
    """Get test cases from test_builtin.js."""
    tests_dir = Path(__file__).parent
    builtin_js = tests_dir / "test_builtin.js"

    if not builtin_js.exists():
        return []

    return get_test_functions_from_js(builtin_js)


# Get the function code once (it's the same for all tests)
_TEST_CASES = get_builtin_test_cases()
_FUNC_CODE = _TEST_CASES[0][1] if _TEST_CASES else ""

# Tests that are known to pass
PASSING_TESTS = {
    "test",
    "test_string",
    "test_string2",
    "test_array",
    "test_array_ext",
    "test_enum",
    "test_function",
    "test_number",
    "test_math",
    "test_json",
    "test_typed_array",
}

# Tests that are known to fail (with reasons)
FAILING_TESTS = {
    "test_global_eval": "Indirect eval doesn't run in global scope",
    "test_regexp": "Capture groups inside repetitions not reset correctly",
    "test_line_column_numbers": "Line/column tracking not implemented",
    "test_large_eval_parse_stack": "Deeply nested parsing not implemented",
}


@pytest.mark.parametrize(
    "func_name",
    [name for name, _ in _TEST_CASES],
    ids=lambda x: x,
)
def test_builtin_function(func_name: str):
    """Run an individual test function from test_builtin.js."""
    if func_name in FAILING_TESTS:
        pytest.xfail(FAILING_TESTS[func_name])

    ctx = JSContext(time_limit=5.0)

    # Load all the function definitions
    ctx.eval(_FUNC_CODE)

    # Run the specific test function
    ctx.eval(f"{func_name}()")
