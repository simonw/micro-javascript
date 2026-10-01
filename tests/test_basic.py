def test_basic_addition():
    """Basic test to verify pytest harness works correctly."""
    assert 1 + 1 == 2


def test_version_matches_package_metadata():
    """microjs.__version__ should match the installed package version."""
    from importlib.metadata import version

    import microjs

    assert microjs.__version__ == version("micro-javascript")
