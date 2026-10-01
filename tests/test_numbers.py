"""Number semantics, checked against results computed by Node.js.

Each case is a JavaScript expression and the value Node 22 produced for it.
"""

import math

import pytest

from microjs import Context

NAN, INF, NEG_INF, NEG_ZERO = "NaN", "Infinity", "-Infinity", "-0"


def N(value):
    """An expected number (NaN, infinities and -0 given as strings)."""
    return ("number", value if isinstance(value, str) else float(value))


def S(value):
    """An expected string."""
    return ("string", value)


def B(value):
    """An expected boolean."""
    return ("boolean", value)


def canonical(value):
    """Describe a microjs result in the same form as the expected values."""
    if isinstance(value, bool):
        return ("boolean", value)
    if isinstance(value, int):
        if abs(value) > 2**53:
            # JavaScript numbers are doubles: integers this big are inexact
            return ("number", f"unsafe int {value}")
        return ("number", float(value))
    if isinstance(value, float):
        if math.isnan(value):
            return ("number", NAN)
        if math.isinf(value):
            return ("number", INF if value > 0 else NEG_INF)
        if value == 0 and math.copysign(1.0, value) < 0:
            return ("number", NEG_ZERO)
        return ("number", value)
    if isinstance(value, str):
        return ("string", value)
    return ("other", repr(value))


CASES = [
    # Remainder
    ("-7 % 3", N(-1)),
    ("7 % -3", N(1)),
    ("-7.5 % 2", N(-1.5)),
    ("5.5 % -2", N(1.5)),
    ("-4 % 2", N(NEG_ZERO)),
    ("0 % 5", N(0)),
    ("-0 % 5", N(NEG_ZERO)),
    ("5 % 0", N(NAN)),
    ("Infinity % 5", N(NAN)),
    ("5 % Infinity", N(5)),
    ("-5 % Infinity", N(-5)),
    ("NaN % 1", N(NAN)),
    # Exponentiation
    ("2 ** 10", N(1024)),
    ("2 ** -1", N(0.5)),
    ("(-8) ** (1/3)", N(NAN)),
    ("0 ** -1", N(INF)),
    ("(-0) ** -1", N(NEG_INF)),
    ("(-0) ** -3", N(NEG_INF)),
    ("10 ** 400", N(INF)),
    ("(-10) ** 401", N(NEG_INF)),
    ("1 ** Infinity", N(NAN)),
    ("NaN ** 0", N(1)),
    ("2 ** 53 + 1", N(9007199254740992)),
    ("2 ** 0.5", N(1.4142135623730951)),
    ("(-2) ** 3", N(-8)),
    ("Infinity ** -1", N(0)),
    ("(-2) ** 0.5", N(NAN)),
    # Integer precision and overflow
    ("9007199254740993", N(9007199254740992)),
    ("2 ** 53 + 2", N(9007199254740994)),
    ("9007199254740992 + 1", N(9007199254740992)),
    ("1e21 + 1", N(1e21)),
    ("123456789 * 987654321", N(121932631112635260)),
    ("var x = 2; for (var i = 0; i < 12; i++) x = x * x; x", N(INF)),
    ("var x = 3; for (var i = 0; i < 12; i++) x = x * x * x; x", N(INF)),
    ("var f = 1; for (var i = 1; i <= 25; i++) f = f * i; f", N(1.5511210043330986e25)),
    ("-9007199254740993", N(-9007199254740992)),
    ("0x20000000000001", N(9007199254740992)),
    # Signed zero
    ("-0 + 0", N(0)),
    ("-0 - 0", N(NEG_ZERO)),
    ("0 * -1", N(NEG_ZERO)),
    ("-0 * -0", N(0)),
    ("1 / -0", N(NEG_INF)),
    ("-(0)", N(NEG_ZERO)),
    ("-0 / 1", N(NEG_ZERO)),
    ("7 / -0", N(NEG_INF)),
    # Bitwise
    ("NaN | 0", N(0)),
    ("Infinity | 0", N(0)),
    ("-Infinity | 0", N(0)),
    ("1e20 | 0", N(1661992960)),
    ("2 ** 31 | 0", N(-2147483648)),
    ("(2 ** 32 + 5) | 0", N(5)),
    ("-1 >>> 0", N(4294967295)),
    ("1.9 | 0", N(1)),
    ("-1.9 | 0", N(-1)),
    ("2 ** 53 | 0", N(0)),
    ("~NaN", N(-1)),
    ("1 << 32", N(1)),
    ("1 << 31", N(-2147483648)),
    ("-1 >> 31", N(-1)),
    ("-1 >>> 31", N(1)),
    ("5 & Infinity", N(0)),
    ('"12" | 0', N(12)),
    ("1e21 >>> 0", N(3735027712)),
    ("-1e21 >> 0", N(559939584)),
    # Math rounding
    ("Math.floor(NaN)", N(NAN)),
    ("Math.floor(Infinity)", N(INF)),
    ("Math.floor(-Infinity)", N(NEG_INF)),
    ("Math.floor(-0)", N(NEG_ZERO)),
    ("Math.floor(1e300)", N(1e300)),
    ("Math.floor(-1.5)", N(-2)),
    ("Math.ceil(-0.5)", N(NEG_ZERO)),
    ("Math.ceil(Infinity)", N(INF)),
    ("Math.ceil(1.2)", N(2)),
    ("Math.trunc(-0.7)", N(NEG_ZERO)),
    ("Math.trunc(Infinity)", N(INF)),
    ("Math.trunc(-1.5)", N(-1)),
    ("Math.round(NaN)", N(NAN)),
    ("Math.round(-0.5)", N(NEG_ZERO)),
    ("Math.round(2.5)", N(3)),
    ("Math.round(-2.5)", N(-2)),
    ("Math.round(0.49999999999999994)", N(0)),
    ("Math.round(-0)", N(NEG_ZERO)),
    ("Math.round(1e300)", N(1e300)),
    ("Math.round(Infinity)", N(INF)),
    ("Math.round(-0.2)", N(NEG_ZERO)),
    ("Math.round(4503599627370495.5)", N(4503599627370496)),
    # Math other
    ("Math.pow(-8, 1/3)", N(NAN)),
    ("Math.pow(10, 400)", N(INF)),
    ("Math.pow(0, -1)", N(INF)),
    ("Math.pow(1, Infinity)", N(NAN)),
    ("Math.pow(NaN, 0)", N(1)),
    ("Math.exp(1000)", N(INF)),
    ("Math.exp(-Infinity)", N(0)),
    ("Math.log(0)", N(NEG_INF)),
    ("Math.log(-1)", N(NAN)),
    ("Math.sqrt(-1)", N(NAN)),
    ("Math.sqrt(-0)", N(NEG_ZERO)),
    ("Math.max(1, NaN, 3)", N(NAN)),
    ("Math.max(NaN, 1)", N(NAN)),
    ("Math.max()", N(NEG_INF)),
    ("Math.min()", N(INF)),
    ("Math.max(-0, 0)", N(0)),
    ("Math.min(0, -0)", N(NEG_ZERO)),
    ("Math.min(NaN, 1)", N(NAN)),
    ('Math.max("3", 2)', N(3)),
    ("Math.abs(-Infinity)", N(INF)),
    ("Math.abs(-0)", N(0)),
    ("Math.sign(-0)", N(NEG_ZERO)),
    ("Math.sign(NaN)", N(NAN)),
    ("Math.sign(-3)", N(-1)),
    ("Math.cbrt(-8)", N(-2)),
    ("Math.hypot(3, 4)", N(5)),
    ("Math.log2(8)", N(3)),
    ("Math.log10(1000)", N(3)),
    ("Math.atan2(0, -0)", N(3.141592653589793)),
    ("Math.sin(Infinity)", N(NAN)),
    ("Math.cos(-Infinity)", N(NAN)),
    ("Math.tan(NaN)", N(NAN)),
    ("Math.asin(2)", N(NAN)),
    ("Math.atan(Infinity)", N(1.5707963267948966)),
    ("Math.fround(5.5)", N(5.5)),
    ("Math.clz32(1)", N(31)),
    ("Math.imul(0xffffffff, 5)", N(-5)),
    ("Math.expm1(0)", N(0)),
    ("Math.log1p(-1)", N(NEG_INF)),
    ("Math.sinh(-0)", N(NEG_ZERO)),
    ("Math.cosh(0)", N(1)),
    ("Math.tanh(Infinity)", N(1)),
    ("Math.asinh(-0)", N(NEG_ZERO)),
    ("Math.acosh(1)", N(0)),
    ("Math.atanh(1)", N(INF)),
    ("Math.exp(710)", N(INF)),
    ("Math.cosh(1000)", N(INF)),
    ("Math.hypot(Infinity, NaN)", N(INF)),
    ("Math.hypot()", N(0)),
    ("Math.cbrt(Infinity)", N(INF)),
    # ToNumber
    ('Number("")', N(0)),
    ('Number(" 12 ")', N(12)),
    ('Number("0x1F")', N(31)),
    ('Number("0b11")', N(3)),
    ('Number("0o17")', N(15)),
    ('Number("1e3")', N(1000)),
    ('Number(".5")', N(0.5)),
    ('Number("5.")', N(5)),
    ('Number("+5")', N(5)),
    ('Number("-5")', N(-5)),
    ('Number("Infinity")', N(INF)),
    ('Number("-Infinity")', N(NEG_INF)),
    ('Number("inf")', N(NAN)),
    ('Number("INFINITY")', N(NAN)),
    ('Number("nan")', N(NAN)),
    ('Number("1_000")', N(NAN)),
    ('Number("１２")', N(NAN)),
    ('Number("12px")', N(NAN)),
    ('Number("0x")', N(NAN)),
    ('Number("-0x10")', N(NAN)),
    ('Number(" \\n\\t 7 \\n")', N(7)),
    ('Number("99999999999999999999999")', N(1e23)),
    ('Number("1e1000")', N(INF)),
    ("Number(null)", N(0)),
    ("Number(undefined)", N(NAN)),
    ("Number(true)", N(1)),
    ('Number("-0")', N(NEG_ZERO)),
    ('Number("0.0000001")', N(1e-07)),
    ('Number("0X1f")', N(31)),
    ('Number("1e")', N(NAN)),
    ('Number("e5")', N(NAN)),
    ('Number(".")', N(NAN)),
    ('Number("+-1")', N(NAN)),
    ('+"3"', N(3)),
    ('-"3"', N(-3)),
    ('"6" / "2"', N(3)),
    ('"3" * "4"', N(12)),
    ('"10" - "4"', N(6)),
    # parseInt and parseFloat
    ('parseInt("  42abc")', N(42)),
    ('parseInt("0x1F")', N(31)),
    ('parseInt("1F", 16)', N(31)),
    ('parseInt("z", 36)', N(35)),
    ('parseInt("12", 1)', N(NAN)),
    ('parseInt("12", 37)', N(NAN)),
    ('parseInt("")', N(NAN)),
    ('parseInt("-0")', N(NEG_ZERO)),
    ('parseInt("99999999999999999999999")', N(1e23)),
    ('parseInt("1e3")', N(1)),
    ("parseInt(0.0000005)", N(5)),
    ('parseInt("  -12.9")', N(-12)),
    ('parseInt("0b11")', N(0)),
    ('parseInt("08")', N(8)),
    ('parseInt("-0x1F")', N(-31)),
    ('parseInt("0x")', N(NAN)),
    ('parseInt("１２")', N(NAN)),
    ('parseInt("12", 0)', N(12)),
    ("parseInt(null)", N(NAN)),
    ('parseInt("Infinity")', N(NAN)),
    ('parseFloat("3.14abc")', N(3.14)),
    ('parseFloat(".5")', N(0.5)),
    ('parseFloat("-.5e-3x")', N(-0.0005)),
    ('parseFloat("Infinityx")', N(INF)),
    ('parseFloat("-Infinity")', N(NEG_INF)),
    ('parseFloat("1e1000")', N(INF)),
    ('parseFloat("abc")', N(NAN)),
    ('parseFloat("  1.5  ")', N(1.5)),
    ('parseFloat("1.e2")', N(100)),
    ('parseFloat("0x10")', N(0)),
    ('parseFloat("1e")', N(1)),
    ('parseFloat("-0")', N(NEG_ZERO)),
    ('parseFloat("inf")', N(NAN)),
    ('parseFloat("１２")', N(NAN)),
    # ToString
    ("String(1e21)", S("1e+21")),
    ("String(1e-7)", S("1e-7")),
    ("String(123456789012345680000)", S("123456789012345680000")),
    ("String(0.000001)", S("0.000001")),
    ("String(-0)", S("0")),
    ("String(1.5e300)", S("1.5e+300")),
    ("String(5e-324)", S("5e-324")),
    ("String(2 ** 53)", S("9007199254740992")),
    ("String(0.1 + 0.2)", S("0.30000000000000004")),
    ("String(-1e-7)", S("-1e-7")),
    ("String(1 / 3)", S("0.3333333333333333")),
    ("String(100)", S("100")),
    ("String(1e20)", S("100000000000000000000")),
    ("String(NaN)", S("NaN")),
    ("String(-Infinity)", S("-Infinity")),
    ("String(123.456)", S("123.456")),
    ("String(2 ** 64)", S("18446744073709552000")),
    ("String(-1.5e-10)", S("-1.5e-10")),
    ("String(1e100)", S("1e+100")),
    ('"" + 1e21', S("1e+21")),
    ("[1e21, 0.1].join()", S("1e+21,0.1")),
    ("(255).toString(16)", S("ff")),
    ("(255).toString(2)", S("11111111")),
    ("(-255).toString(36)", S("-73")),
    ("(0.5).toString(2)", S("0.1")),
    ("(3.75).toString(2)", S("11.11")),
    ("(-0.25).toString(4)", S("-0.1")),
    ("(255.5).toString(16)", S("ff.8")),
    ("(1e21).toString(16)", S("3635c9adc5dea00000")),
    ("(NaN).toString(2)", S("NaN")),
    ("(10).toString()", S("10")),
    ("(1.005).toFixed(2)", S("1.00")),
    ("(2.5).toFixed(0)", S("3")),
    ("(-2.5).toFixed(0)", S("-3")),
    ("(1e21).toFixed(2)", S("1e+21")),
    ("(0).toFixed(2)", S("0.00")),
    ("(-0).toFixed(2)", S("0.00")),
    ("(1.45).toFixed(1)", S("1.4")),
    ("(123.456).toFixed(10)", S("123.4560000000")),
    ("(0.000001).toFixed(7)", S("0.0000010")),
    ("(NaN).toFixed(2)", S("NaN")),
    ("(1.5).toFixed()", S("2")),
    ("(0.5).toFixed(0)", S("1")),
    ("(-1.5).toFixed(0)", S("-2")),
    ("(1.255).toFixed(2)", S("1.25")),
    ("(123.456).toPrecision(4)", S("123.5")),
    ("(0.000123).toPrecision(2)", S("0.00012")),
    ("(123456).toPrecision(2)", S("1.2e+5")),
    ("(1.5).toPrecision(1)", S("2")),
    ("(2.5).toPrecision(1)", S("3")),
    ("(0).toPrecision(3)", S("0.00")),
    ("(1e21).toPrecision(3)", S("1.00e+21")),
    ("(123.456).toExponential(2)", S("1.23e+2")),
    ("(0).toExponential()", S("0e+0")),
    ("(12345).toExponential()", S("1.2345e+4")),
    ("(1.5).toExponential(0)", S("2e+0")),
    ("(-0.00015).toExponential(1)", S("-1.5e-4")),
    ("(NaN).toExponential(2)", S("NaN")),
    # Math edge cases
    ("Math.imul(NaN, 2)", N(0)),
    ("Math.imul(2.5, 3.9)", N(6)),
    ("Math.clz32(NaN)", N(32)),
    ("Math.clz32(-1)", N(0)),
    ("Math.clz32(0.5)", N(32)),
    ("Math.fround(1e300)", N(INF)),
    ("Math.fround(NaN)", N(NAN)),
    ("Math.fround(-0)", N(NEG_ZERO)),
    ("Math.log2(0)", N(NEG_INF)),
    ("Math.log2(-0)", N(NEG_INF)),
    ("Math.log10(0)", N(NEG_INF)),
    ("Math.log10(-1)", N(NAN)),
    ("Math.log(-0)", N(NEG_INF)),
    ("Math.cbrt(-0)", N(NEG_ZERO)),
    ("Math.cbrt(NaN)", N(NAN)),
    ("Math.cbrt(27)", N(3)),
    ("Math.expm1(1000)", N(INF)),
    ("Math.expm1(-0)", N(NEG_ZERO)),
    ("Math.atan2(NaN, 1)", N(NAN)),
    ("Math.acos(NaN)", N(NAN)),
    ("Math.max(-Infinity, -Infinity)", N(NEG_INF)),
    ("Math.hypot(-0)", N(0)),
    ("Math.hypot(1, Infinity)", N(INF)),
    ('Math.abs("-2")', N(2)),
    ('Math.floor("1.5")', N(1)),
    ("Math.floor([2.5])", N(2)),
    # Arithmetic on objects (ToPrimitive)
    ("[5] - 1", N(4)),
    ('"5" - [2]', N(3)),
    ("-[3]", N(-3)),
    ("+[]", N(0)),
    ("+{}", N(NAN)),
    ("+[1, 2]", N(NAN)),
    ("({valueOf: function () { return 3 }}) * 2", N(6)),
    ("({valueOf: function () { return 2 }}) ** 3", N(8)),
    ("({valueOf: function () { return 7 }}) % 4", N(3)),
    ("({valueOf: function () { return 6 }}) / 4", N(1.5)),
    ('({toString: function () { return "9" }}) - 1', N(8)),
    ("var x = [5]; x++; x", N(6)),
    ("var x = {valueOf: function () { return 1 }}; x--; x", N(0)),
    ("[2] * [3]", N(6)),
    ("null + 1", N(1)),
    ("undefined + 1", N(NAN)),
    ("true + true", N(2)),
    ("[] - []", N(0)),
    # Number constants and statics
    ("Number.MAX_SAFE_INTEGER", N(9007199254740991)),
    ("Number.MIN_SAFE_INTEGER", N(-9007199254740991)),
    ("Number.MAX_SAFE_INTEGER + 2", N(9007199254740992)),
    ("Number.EPSILON", N(2.220446049250313e-16)),
    ("Number.MAX_VALUE", N(1.7976931348623157e308)),
    ("Number.MIN_VALUE", N(5e-324)),
    ("Number.POSITIVE_INFINITY", N(INF)),
    ("Number.NEGATIVE_INFINITY", N(NEG_INF)),
    ("Number.NaN", N(NAN)),
    ("Number.isSafeInteger(2 ** 53)", B(False)),
    ("Number.isSafeInteger(2 ** 53 - 1)", B(True)),
    ('Number.isFinite("5")', B(False)),
    ('Number.isNaN("x")', B(False)),
    ("Number.isInteger(5.0)", B(True)),
    ("Number.isInteger(Infinity)", B(False)),
    ('Number.parseFloat("1.5x")', N(1.5)),
    ('Number.parseInt("12", 8)', N(10)),
    ("Number.MAX_VALUE * 2", N(INF)),
    ("Number.MIN_VALUE / 2", N(0)),
    # JSON numbers
    ("JSON.stringify(1 / 0)", S("null")),
    ("JSON.stringify(NaN)", S("null")),
    ("JSON.stringify(-0)", S("0")),
    ("JSON.stringify(1e-7)", S("1e-7")),
    ("JSON.stringify([0.1, 2 ** 64, -1e21])", S("[0.1,18446744073709552000,-1e+21]")),
    ("JSON.stringify({a: 1.5, b: [NaN]})", S('{"a":1.5,"b":[null]}')),
    ('JSON.parse("99999999999999999999")', N(100000000000000000000)),
    ('JSON.parse("-0")', N(NEG_ZERO)),
    ('JSON.parse("1e1000")', N(INF)),
    ('JSON.parse("[1.5, -2]")[1]', N(-2)),
    # toPrecision and toExponential
    ("(1.005).toPrecision(3)", S("1.00")),
    ("(0.00001).toPrecision(1)", S("0.00001")),
    ("(123.456).toPrecision(2)", S("1.2e+2")),
    ("(1e21).toPrecision(1)", S("1e+21")),
    ("(99.99).toPrecision(3)", S("100")),
    ("(-1.5).toPrecision(2)", S("-1.5")),
    ("(0.000001234).toPrecision(2)", S("0.0000012")),
    ("(123456789).toPrecision(9)", S("123456789")),
    ("(1.25).toExponential(1)", S("1.3e+0")),
    ("(1.35).toExponential(1)", S("1.4e+0")),
    ("(123456789).toExponential(3)", S("1.235e+8")),
    ("(5e-324).toExponential()", S("5e-324")),
    ("(1.7976931348623157e308).toExponential(5)", S("1.79769e+308")),
    ("(0.000001).toExponential()", S("1e-6")),
    ("(25).toExponential(0)", S("3e+1")),
    ("(-0).toExponential(2)", S("0.00e+0")),
    ("(Infinity).toPrecision(3)", S("Infinity")),
    ("(1/3).toPrecision(20)", S("0.33333333333333331483")),
    ("(2 ** 70).toExponential(2)", S("1.18e+21")),
    # Relational comparison
    ("NaN < 1", B(False)),
    ("NaN <= 1", B(False)),
    ("NaN > 1", B(False)),
    ("NaN >= 1", B(False)),
    ("NaN >= NaN", B(False)),
    ("1 <= NaN", B(False)),
    ("undefined <= 0", B(False)),
    ("undefined >= 0", B(False)),
    ("null <= 0", B(True)),
    ("null >= 0", B(True)),
    ("null < 1", B(True)),
    ('"10" < "9"', B(True)),
    ('"10" < 9', B(False)),
    ('"b" >= "a"', B(True)),
    ("[2] > 1", B(True)),
    ('["b"] > "a"', B(True)),
    ("({}) <= 1", B(False)),
    ("({}) >= ({})", B(True)),
    ("[1] <= [1]", B(True)),
    ('"" < 1', B(True)),
    ("true > false", B(True)),
    ("-0 >= 0", B(True)),
    ("Infinity > 1e308", B(True)),
    ('"abc" < "abd"', B(True)),
    ("2 >= 2.0", B(True)),
    ('"3" >= 3', B(True)),
]


@pytest.mark.parametrize("source,expected", CASES, ids=[c[0] for c in CASES])
def test_number_semantics(source, expected):
    assert canonical(Context(time_limit=5.0).eval(source)) == expected


def test_huge_integer_power_does_not_build_a_huge_int():
    """10 ** 3000000 is Infinity, computed without a 3-million-digit int."""
    import time

    start = time.monotonic()
    result = Context(time_limit=5.0).eval("10 ** 3000000")
    assert result == float("inf")
    assert time.monotonic() - start < 0.5


def test_repeated_squaring_overflows_to_infinity():
    import time

    start = time.monotonic()
    result = Context(time_limit=5.0).eval(
        "var x = 3; for (var i = 0; i < 40; i++) x = x * x; x"
    )
    assert result == float("inf")
    assert time.monotonic() - start < 0.5


@pytest.mark.parametrize(
    "source,expected",
    [
        # Python refuses int() on over 4300 decimal digits; JS gives a double
        ('Number("1".repeat(5000))', float("inf")),
        ('Number("0".repeat(5000) + "7")', 7),
        ('parseInt("1".repeat(5000))', float("inf")),
        ('parseInt("1".repeat(5000), 36)', float("inf")),
        ('parseInt("0".repeat(5000) + "12", 36)', 38),
        ('JSON.parse("1".repeat(5000))', float("inf")),
        ("1" * 5000, float("inf")),
        ("1" * 400 + " / 1e300", float("inf")),
        ("1" * 300 + " / 1e200", 1.1111111111111112e99),
    ],
)
def test_very_long_digit_strings(source, expected):
    assert Context(time_limit=5.0).eval(source) == expected
