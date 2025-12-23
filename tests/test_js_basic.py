"""
Parameterized pytest tests for JavaScript files.

- Each .js file in tests/basic/ is run as a test case (should pass)
- Each .js file in tests/ (original mquickjs tests) is run with xfail (expected to fail)
"""
from pathlib import Path

import pytest

from mquickjs_python import JSContext


def get_basic_test_files():
    """Discover all .js files in tests/basic/ directory."""
    basic_dir = Path(__file__).parent / "basic"
    if not basic_dir.exists():
        return []
    js_files = sorted(basic_dir.glob("*.js"))
    return [(f.name, f) for f in js_files]


def get_mquickjs_test_files():
    """Discover original mquickjs .js test files in tests/ directory."""
    tests_dir = Path(__file__).parent
    # Get all .js files directly in tests/ (not in subdirectories)
    js_files = sorted(tests_dir.glob("*.js"))
    return [(f.name, f) for f in js_files]


@pytest.mark.parametrize(
    "name,path",
    get_basic_test_files(),
    ids=lambda x: x if isinstance(x, str) else None,
)
def test_basic_js(name: str, path: Path):
    """Run a basic JavaScript test file."""
    source = path.read_text(encoding="utf-8")
    ctx = JSContext()
    # Execute the script - if it throws, the test fails
    ctx.eval(source)


@pytest.mark.parametrize(
    "name,path",
    get_mquickjs_test_files(),
    ids=lambda x: x if isinstance(x, str) else None,
)
@pytest.mark.xfail(reason="Original mquickjs tests - not yet passing")
def test_mquickjs_js(name: str, path: Path):
    """Run an original mquickjs JavaScript test file.

    These tests are expected to fail until the VM is complete.
    Watch for xfail tests that start passing!
    """
    source = path.read_text(encoding="utf-8")
    ctx = JSContext()
    # Execute the script - if it throws, the test fails
    ctx.eval(source)
