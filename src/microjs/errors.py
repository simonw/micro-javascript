"""JavaScript error types and exceptions."""

from typing import Optional


class JSError(Exception):
    """Base class for all JavaScript errors."""

    def __init__(self, message: str = "", name: str = "Error"):
        self.message = message
        self.name = name
        super().__init__(f"{name}: {message}" if message else name)


class JSSyntaxError(JSError):
    """JavaScript syntax error during parsing."""

    def __init__(self, message: str = "", line: int = 0, column: int = 0):
        self.line = line
        self.column = column
        # Include position in error message if line is specified
        if line > 0:
            formatted_message = f"{message} (line {line}, column {column})"
        else:
            formatted_message = message
        super().__init__(formatted_message, "SyntaxError")


class JSTypeError(JSError):
    """JavaScript type error."""

    def __init__(self, message: str = ""):
        super().__init__(message, "TypeError")


class JSReferenceError(JSError):
    """JavaScript reference error (undefined variable)."""

    def __init__(self, message: str = ""):
        super().__init__(message, "ReferenceError")


class JSRangeError(JSError):
    """JavaScript range error."""

    def __init__(self, message: str = ""):
        super().__init__(message, "RangeError")


class MemoryLimitError(JSError):
    """Raised when memory limit is exceeded."""

    def __init__(self, message: str = "Memory limit exceeded"):
        super().__init__(message, "InternalError")


class TimeLimitError(JSError):
    """Raised when execution time limit is exceeded."""

    def __init__(self, message: str = "Execution timeout"):
        super().__init__(message, "InternalError")
