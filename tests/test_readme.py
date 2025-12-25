"""Test that code examples in README.md work correctly."""

import re
from pathlib import Path

import pytest


def extract_python_blocks(readme_content: str) -> list[str]:
    """Extract all Python code blocks from markdown content."""
    pattern = r"```python\n(.*?)```"
    matches = re.findall(pattern, readme_content, re.DOTALL)
    return matches


def find_return_comments(code_block: str) -> list[tuple[int, str, str]]:
    """Find lines with '# Returns X' comments.

    Returns a list of (line_index, var_name, expected_value) tuples.
    """
    results = []
    for i, line in enumerate(code_block.split("\n")):
        match = re.search(r"^(\w+)\s*=.*#\s*Returns\s+(.+?)\s*$", line)
        if match:
            var_name = match.group(1)
            expected = match.group(2)
            results.append((i, var_name, expected))
    return results


def get_base_namespace() -> dict:
    """Get a namespace with common imports for README examples."""
    namespace = {}
    exec("from microjs import Context", namespace)
    exec("from microjs.values import JSObject, JSArray", namespace)
    return namespace


def compare_values(actual, expected) -> bool:
    """Compare values, handling float/int equivalence."""
    if isinstance(actual, float) and isinstance(expected, int):
        return actual == float(expected)
    if isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            return False
        for a, e in zip(actual, expected):
            if not compare_values(a, e):
                return False
        return True
    return actual == expected


class TestReadmeExamples:
    """Test that README examples work correctly."""

    @pytest.fixture
    def readme_content(self) -> str:
        """Load README.md content."""
        readme_path = Path(__file__).parent.parent / "README.md"
        return readme_path.read_text()

    def test_extract_python_blocks(self, readme_content):
        """Test that we can extract Python blocks from README."""
        blocks = extract_python_blocks(readme_content)
        assert len(blocks) > 0, "Should find at least one Python block"
        # First block should contain Context
        assert "Context" in blocks[0]

    def test_find_return_comments(self):
        """Test that we can find return comments in code."""
        code = """
result = ctx.eval("1 + 2")  # Returns 3
other = ctx.eval("x")  # Returns 42
no_comment = ctx.eval("y")
"""
        results = find_return_comments(code)
        assert results == [(1, "result", "3"), (2, "other", "42")]

    def test_readme_examples_execute(self, readme_content):
        """Test that all README Python examples execute without error."""
        blocks = extract_python_blocks(readme_content)

        for i, block in enumerate(blocks):
            # Create a namespace with common imports
            namespace = get_base_namespace()
            try:
                exec(block, namespace)
            except Exception as e:
                pytest.fail(f"Block {i + 1} failed to execute:\n{block}\n\nError: {e}")

    def test_readme_return_comments_are_correct(self, readme_content):
        """Test that all '# Returns X' comments in README are accurate."""
        blocks = extract_python_blocks(readme_content)

        for i, block in enumerate(blocks):
            return_comments = find_return_comments(block)
            if not return_comments:
                continue

            lines = block.split("\n")

            # For each return comment, execute all lines up to and including it,
            # then check the value
            for comment_line_idx, var_name, expected_str in return_comments:
                # Build code up to and including this line
                code_to_execute = "\n".join(lines[: comment_line_idx + 1])

                namespace = get_base_namespace()
                try:
                    exec(code_to_execute, namespace)
                except Exception as e:
                    pytest.fail(
                        f"Block {i + 1}, line {comment_line_idx + 1}: "
                        f"Failed to execute.\n"
                        f"Code:\n{code_to_execute}\n\nError: {e}"
                    )

                # Parse the expected value
                try:
                    expected = eval(expected_str)
                except:
                    expected = expected_str

                if var_name not in namespace:
                    pytest.fail(
                        f"Block {i + 1}, line {comment_line_idx + 1}: "
                        f"Variable '{var_name}' not found.\n"
                        f"Line: {lines[comment_line_idx]}"
                    )

                actual = namespace[var_name]

                if not compare_values(actual, expected):
                    pytest.fail(
                        f"Block {i + 1}, line {comment_line_idx + 1}: "
                        f"{var_name} = {actual!r}, expected {expected!r}\n"
                        f"Line: {lines[comment_line_idx]}"
                    )
