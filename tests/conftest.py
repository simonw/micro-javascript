"""Pytest configuration for mquickjs-python tests."""

import pytest
import signal
import sys


def timeout_handler(signum, frame):
    """Handle timeout signal."""
    pytest.fail("Test timed out")


@pytest.fixture(autouse=True)
def test_timeout():
    """Apply a 10-second timeout to all tests."""
    if sys.platform != "win32":
        # Set up timeout handler (Unix only)
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(10)  # 10 second timeout
        yield
        signal.alarm(0)  # Cancel the alarm
        signal.signal(signal.SIGALRM, old_handler)
    else:
        yield
