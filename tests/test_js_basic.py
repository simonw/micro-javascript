"""
Parameterized pytest tests for basic JavaScript files.

Each .js file in tests/basic/ is run as a test case.
A test passes if the script executes without throwing an exception.
"""
import os
from pathlib import Path

import pytest

from microjs import JSContext


def get_basic_test_files():
    """Discover all .js files in tests/basic/ directory."""
    basic_dir = Path(__file__).parent / "basic"
    if not basic_dir.exists():
        return []
    js_files = sorted(basic_dir.glob("*.js"))
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
