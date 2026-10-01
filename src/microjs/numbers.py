"""JavaScript number semantics: conversions, formatting and arithmetic.

JavaScript numbers are IEEE 754 doubles. The engine represents them as
Python floats, or as Python ints when integral - but only within the range
a double holds exactly (+/- 2**53). js_number() enforces that limit, which
also stops scripts from building enormous Python integers.
"""

import math
import re
import struct
from fractions import Fraction
from typing import List, Tuple, Union

Number = Union[int, float]

NAN = float("nan")
INF = float("inf")

MAX_SAFE_INTEGER = 2**53 - 1
_EXACT_INT_LIMIT = 2**53

# StrWhiteSpaceChar: WhiteSpace and LineTerminator
WHITESPACE = "\t\n\v\f\r          " "        　﻿"

_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"

# StrDecimalLiteral, matched against ASCII only
_DECIMAL = re.compile(
    r"[+-]?(?:Infinity|(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)"
)
_NON_DECIMAL = {
    "0x": (16, re.compile(r"[0-9a-fA-F]+")),
    "0o": (8, re.compile(r"[0-7]+")),
    "0b": (2, re.compile(r"[01]+")),
}


def js_number(n: Number) -> Number:
    """Round an integer outside +/- 2**53 to the nearest double."""
    if type(n) is int and not -_EXACT_INT_LIMIT <= n <= _EXACT_INT_LIMIT:
        try:
            return float(n)
        except OverflowError:
            return INF if n > 0 else -INF
    return n


def is_finite(n: Number) -> bool:
    return type(n) is int or math.isfinite(n)


def is_negative_zero(n: Number) -> bool:
    return type(n) is float and n == 0 and math.copysign(1.0, n) < 0


# ---- String to number ----


def string_to_number(text: str) -> Number:
    """ToNumber applied to a string."""
    s = text.strip(WHITESPACE)
    if not s:
        return 0
    radix_info = _NON_DECIMAL.get(s[:2].lower())
    if radix_info is not None:
        radix, digits = radix_info
        if digits.fullmatch(s, 2):
            return js_number(int(s[2:], radix))
        return NAN
    if not _DECIMAL.fullmatch(s):
        return NAN
    return _decimal_value(s)


def _decimal_value(text: str) -> Number:
    """The value of a StrDecimalLiteral that has already been validated."""
    if text.lstrip("+-") == "Infinity":
        return -INF if text.startswith("-") else INF
    if "." in text or "e" in text or "E" in text:
        return float(text)
    n = int(text)
    if n == 0 and text.startswith("-"):
        return -0.0
    return js_number(n)


def parse_float(text: str) -> Number:
    """The global parseFloat()."""
    match = _DECIMAL.match(text.lstrip(WHITESPACE))
    if not match:
        return NAN
    return _decimal_value(match.group())


def parse_int(text: str, radix: Number) -> Number:
    """The global parseInt()."""
    s = text.lstrip(WHITESPACE)
    negative = s.startswith("-")
    if s[:1] in ("+", "-"):
        s = s[1:]
    radix = to_int32(radix)
    strip_prefix = True
    if radix != 0:
        if not 2 <= radix <= 36:
            return NAN
        strip_prefix = radix == 16
    else:
        radix = 10
    if strip_prefix and s[:2] in ("0x", "0X"):
        s = s[2:]
        radix = 16
    end = 0
    while end < len(s) and _digit_value(s[end]) < radix:
        end += 1
    if end == 0:
        return NAN
    n = int(s[:end], radix)
    if negative:
        return -0.0 if n == 0 else js_number(-n)
    return js_number(n)


def _digit_value(ch: str) -> int:
    """The value of an ASCII digit or letter (36 or more if not a digit)."""
    if "0" <= ch <= "9":
        return ord(ch) - 48
    if "a" <= ch <= "z":
        return ord(ch) - 87
    if "A" <= ch <= "Z":
        return ord(ch) - 55
    return 99


# ---- Number to string ----


def number_to_string(x: Number) -> str:
    """Number::toString(x) with radix 10."""
    if type(x) is int:
        if -_EXACT_INT_LIMIT <= x <= _EXACT_INT_LIMIT:
            return str(x)
        x = js_number(x)
    if x != x:
        return "NaN"
    if x == 0:
        return "0"
    if x < 0:
        return "-" + number_to_string(-x)
    if x == INF:
        return "Infinity"
    digits, n = _shortest_digits(x)
    k = len(digits)
    if k <= n <= 21:
        return digits + "0" * (n - k)
    if 0 < n <= 21:
        return digits[:n] + "." + digits[n:]
    if -6 < n <= 0:
        return "0." + "0" * -n + digits
    e = n - 1
    exponent = f"e{'+' if e >= 0 else '-'}{abs(e)}"
    if k == 1:
        return digits + exponent
    return digits[0] + "." + digits[1:] + exponent


def _shortest_digits(x: float) -> Tuple[str, int]:
    """Shortest round-trip digits of positive x and n, with x = 0.DIGITS * 10**n."""
    mantissa, _, exponent = repr(float(x)).partition("e")
    int_part, _, frac_part = mantissa.partition(".")
    all_digits = int_part + frac_part
    point = len(int_part) + (int(exponent) if exponent else 0)
    stripped = all_digits.lstrip("0")
    point -= len(all_digits) - len(stripped)
    return stripped.rstrip("0"), point


def number_to_radix_string(x: Number, radix: int) -> str:
    """Number::toString(x, radix) for radix 2-36, as V8 computes it."""
    if type(x) is int and abs(x) <= _EXACT_INT_LIMIT:
        if x < 0:
            return "-" + number_to_radix_string(-x, radix)
        out = []
        while True:
            x, digit = divmod(x, radix)
            out.append(_DIGITS[digit])
            if x == 0:
                return "".join(reversed(out))
    x = float(x)
    if x != x:
        return "NaN"
    if x == 0:
        return "0"
    if x < 0:
        return "-" + number_to_radix_string(-x, radix)
    if x == INF:
        return "Infinity"
    integer = math.floor(x)
    fraction = x - integer
    # Only compute fraction digits up to the precision of the double
    delta = max(0.5 * (math.nextafter(x, INF) - x), math.nextafter(0.0, 1.0))
    integer = float(integer)
    fraction_digits: List[str] = []
    if fraction >= delta:
        while True:
            fraction *= radix
            delta *= radix
            digit = int(fraction)
            fraction_digits.append(_DIGITS[digit])
            fraction -= digit
            # Round to even, carrying into earlier digits if needed
            if fraction > 0.5 or (fraction == 0.5 and digit & 1):
                if fraction + delta > 1:
                    while True:
                        if not fraction_digits:
                            integer += 1
                            break
                        last = _digit_value(fraction_digits.pop())
                        if last + 1 < radix:
                            fraction_digits.append(_DIGITS[last + 1])
                            break
                    break
            if fraction < delta:
                break
    # Integer digits; those beyond the double's precision are zero
    integer_digits = []
    while math.frexp(integer / radix)[1] > 53:
        integer /= radix
        integer_digits.append("0")
    while True:
        remainder = math.fmod(integer, radix)
        integer_digits.append(_DIGITS[int(remainder)])
        integer = (integer - remainder) / radix
        if integer <= 0:
            break
    result = "".join(reversed(integer_digits))
    if fraction_digits:
        result += "." + "".join(fraction_digits)
    return result


def to_fixed(x: Number, digits: int) -> str:
    """Number.prototype.toFixed: round half up on the exact binary value."""
    if x != x:
        return "NaN"
    if abs(x) >= 1e21:
        return number_to_string(x)
    sign = ""
    if x < 0:
        sign = "-"
        x = -x
    n = math.floor(Fraction(x) * 10**digits + Fraction(1, 2))
    text = str(n)
    if digits:
        text = text.rjust(digits + 1, "0")
        text = text[:-digits] + "." + text[-digits:]
    return sign + text


def _round_to_digits(x: float, count: int) -> Tuple[str, int]:
    """Round positive x to count significant digits.

    Returns the digits and the decimal exponent e of the first one, choosing
    the value closest to x and the larger one on a tie.
    """
    exact = Fraction(x)
    e = math.floor(math.log10(x))  # May be off by one; corrected below
    while True:
        n = math.floor(exact / Fraction(10) ** (e - count + 1) + Fraction(1, 2))
        if n >= 10**count:
            e += 1
        elif n < 10 ** (count - 1):
            e -= 1
        else:
            return str(n), e


def _exponent_suffix(e: int) -> str:
    return f"e{'+' if e >= 0 else '-'}{abs(e)}"


def to_exponential(x: Number, fraction_digits) -> str:
    """Number.prototype.toExponential; fraction_digits None means as many as needed."""
    if x != x:
        return "NaN"
    sign = "-" if x < 0 else ""
    x = abs(x)
    if x == INF:
        return sign + "Infinity"
    if x == 0:
        digits, e = "0" * ((fraction_digits or 0) + 1), 0
    elif fraction_digits is None:
        digits, n = _shortest_digits(x)
        e = n - 1
    else:
        digits, e = _round_to_digits(x, fraction_digits + 1)
    mantissa = digits[0] + ("." + digits[1:] if len(digits) > 1 else "")
    return sign + mantissa + _exponent_suffix(e)


def to_precision(x: Number, precision: int) -> str:
    """Number.prototype.toPrecision with a precision of 1 to 100."""
    if x != x:
        return "NaN"
    sign = "-" if x < 0 else ""
    x = abs(x)
    if x == INF:
        return sign + "Infinity"
    if x == 0:
        digits, e = "0" * precision, 0
    else:
        digits, e = _round_to_digits(x, precision)
    if e < -6 or e >= precision:
        mantissa = digits[0] + ("." + digits[1:] if precision > 1 else "")
        return sign + mantissa + _exponent_suffix(e)
    if e == precision - 1:
        return sign + digits
    if e >= 0:
        return sign + digits[: e + 1] + "." + digits[e + 1 :]
    return sign + "0." + "0" * (-(e + 1)) + digits


# ---- Integer conversions ----


def to_uint32(x: Number) -> int:
    if type(x) is int:
        return x & 0xFFFFFFFF
    if not math.isfinite(x):
        return 0
    return math.trunc(x) & 0xFFFFFFFF


def to_int32(x: Number) -> int:
    n = to_uint32(x)
    return n - 0x100000000 if n >= 0x80000000 else n


# ---- Arithmetic ----


def js_remainder(a: Number, b: Number) -> Number:
    """The % operator: the result takes the sign of the dividend."""
    if a != a or b != b or b == 0 or not is_finite(a):
        return NAN
    if not is_finite(b) or a == 0:
        return a
    if type(a) is int and type(b) is int:
        r = abs(a) % abs(b)
        if a < 0:
            return -r if r else -0.0
        return r
    return math.fmod(a, b)


def js_pow(base: Number, exponent: Number) -> Number:
    """The ** operator and Math.pow()."""
    if exponent != exponent:
        return NAN
    if exponent == 0:
        return 1
    if base != base:
        return NAN
    if abs(base) == 1 and not is_finite(exponent):
        return NAN
    if type(base) is int and type(exponent) is int and exponent > 0:
        # Exact integer power, unless the result would overflow a double
        if base == 0 or exponent * math.log2(abs(base)) < 1025:
            return js_number(base**exponent)
        return -INF if base < 0 and exponent % 2 else INF
    odd_integer = is_finite(exponent) and float(exponent).is_integer()
    odd_integer = odd_integer and int(exponent) % 2 == 1
    try:
        return math.pow(base, exponent)
    except OverflowError:
        return -INF if base < 0 and odd_integer else INF
    except ValueError:
        if base == 0:
            # Zero to a negative power
            return -INF if odd_integer and math.copysign(1.0, base) < 0 else INF
        # Negative base to a non-integer power
        return NAN


# ---- Math functions ----


def _integral(x: Number, op) -> Number:
    """Apply an integer-rounding op, keeping NaN, infinities and signed zero."""
    if type(x) is int:
        return x
    if not math.isfinite(x) or x == 0:
        return x
    result = op(x)
    if result == 0 and x < 0:
        return -0.0
    return js_number(result)


def _round_half_up(x: float) -> int:
    floor = math.floor(x)
    return floor + 1 if x - floor >= 0.5 else floor


def math_floor(x: Number) -> Number:
    return _integral(x, math.floor)


def math_ceil(x: Number) -> Number:
    return _integral(x, math.ceil)


def math_trunc(x: Number) -> Number:
    return _integral(x, math.trunc)


def math_round(x: Number) -> Number:
    return _integral(x, _round_half_up)


def math_sign(x: Number) -> Number:
    if x != x or x == 0:
        return x
    return 1 if x > 0 else -1


def math_max(values: List[Number]) -> Number:
    result = -INF
    for n in values:
        if n != n:
            return NAN
        if n > result or (n == 0 and result == 0 and is_negative_zero(result)):
            result = n
    return result


def math_min(values: List[Number]) -> Number:
    result = INF
    for n in values:
        if n != n:
            return NAN
        if n < result or (n == 0 and result == 0 and is_negative_zero(n)):
            result = n
    return result


def _guarded(fn, on_overflow=lambda x: INF):
    """Wrap a math function: domain errors give NaN, overflow on_overflow(x)."""

    def call(x: Number) -> Number:
        try:
            return fn(x)
        except OverflowError:
            return on_overflow(x)
        except ValueError:
            return NAN

    return call


def _logarithm(fn):
    def call(x: Number) -> Number:
        if x == 0:
            return -INF
        if x < 0:
            return NAN
        return fn(x)

    return call


def _cbrt(x: Number) -> Number:
    if not math.isfinite(x) or x == 0:
        return x
    # Neither ** (1/3) nor every platform's cbrt is correctly rounded, so
    # pick whichever neighbouring double has the cube closest to |x|
    target = Fraction(abs(x))
    root = abs(x) ** (1 / 3)
    candidates = [math.nextafter(root, 0.0), root, math.nextafter(root, INF)]
    best = min(candidates, key=lambda c: abs(Fraction(c) ** 3 - target))
    return math.copysign(best, x)


def _log1p(x: Number) -> Number:
    if x == -1:
        return -INF
    if x < -1:
        return NAN
    return math.log1p(x)


def _atanh(x: Number) -> Number:
    if abs(x) == 1:
        return math.copysign(INF, x)
    return math.atanh(x)


def _fround(x: Number) -> Number:
    try:
        return struct.unpack("f", struct.pack("f", x))[0]
    except OverflowError:
        return math.copysign(INF, x)


def _sqrt(x: Number) -> Number:
    if x < 0:
        return NAN
    return math.sqrt(x)


def _clz32(x: Number) -> int:
    return 32 - to_uint32(x).bit_length()


def _imul(a: Number, b: Number) -> int:
    return to_int32(to_int32(a) * to_int32(b))


def _hypot(*values: Number) -> Number:
    if any(v in (INF, -INF) for v in values):
        return INF
    return math.hypot(*values)


# Math functions of one number argument
UNARY_MATH = {
    "abs": abs,
    "floor": math_floor,
    "ceil": math_ceil,
    "round": math_round,
    "trunc": math_trunc,
    "sign": math_sign,
    "sqrt": _sqrt,
    "cbrt": _cbrt,
    "exp": _guarded(math.exp),
    "expm1": _guarded(math.expm1),
    "log": _logarithm(math.log),
    "log2": _logarithm(math.log2),
    "log10": _logarithm(math.log10),
    "log1p": _log1p,
    "sin": _guarded(math.sin),
    "cos": _guarded(math.cos),
    "tan": _guarded(math.tan),
    "asin": _guarded(math.asin),
    "acos": _guarded(math.acos),
    "atan": math.atan,
    "sinh": _guarded(math.sinh, lambda x: math.copysign(INF, x)),
    "cosh": _guarded(math.cosh),
    "tanh": math.tanh,
    "asinh": math.asinh,
    "acosh": _guarded(math.acosh),
    "atanh": _guarded(_atanh),
    "fround": _fround,
    "clz32": _clz32,
}

# Math functions of two number arguments
BINARY_MATH = {
    "atan2": math.atan2,
    "pow": js_pow,
    "imul": _imul,
}

# Math functions of any number of number arguments
VARIADIC_MATH = {
    "max": math_max,
    "min": math_min,
    "hypot": lambda values: _hypot(*values),
}
