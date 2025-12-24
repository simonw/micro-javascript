"""Pytest configuration for mquickjs-python tests."""

import pytest
import signal
import sys


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "timeout(seconds): set custom timeout for test")


def timeout_handler(signum, frame):
    """Handle timeout signal."""
    pytest.fail("Test timed out")


@pytest.fixture(autouse=True)
def test_timeout(request):
    """Apply a timeout to all tests.

    Default is 10 seconds, but tests can use a longer timeout by marking them:
    @pytest.mark.timeout(30)  # 30 second timeout
    """
    if sys.platform != "win32":
        # Check for custom timeout marker
        marker = request.node.get_closest_marker("timeout")
        timeout_seconds = marker.args[0] if marker else 10

        # Set up timeout handler (Unix only)
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout_seconds)
        yield
        signal.alarm(0)  # Cancel the alarm
        signal.signal(signal.SIGALRM, old_handler)
    else:
        yield
