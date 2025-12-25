Uses uv. Run tests like this:

    uv run pytest

Run the development version of the tool like this:

    uv run python -c '
    from microjs import JSContext
    ctx = JSContext(memory_limit=1024*1024, time_limit=5.0)
    print(ctx.eval("1 + 2"))
    '
Always practice TDD: write a faliing test, watch it fail, then make it pass.

Commit early and often. Commits should bundle the test, implementation, and documentation changes together.

Run Black to format code before you commit:

    uv run black .
