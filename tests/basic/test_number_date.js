// Test Number methods and Date.now()

function assert(actual, expected, message) {
    if (arguments.length == 1)
        expected = true;
    if (actual === expected)
        return;
    throw Error("assertion failed: got |" + actual + "|" +
                ", expected |" + expected + "|" +
                (message ? " (" + message + ")" : ""));
}

// Test Number.isNaN
assert(Number.isNaN(NaN), true, "isNaN NaN");
assert(Number.isNaN(123), false, "isNaN number");
assert(Number.isNaN("hello"), false, "isNaN string");

// Test Number.isFinite
assert(Number.isFinite(123), true, "isFinite number");
assert(Number.isFinite(Infinity), false, "isFinite Infinity");
assert(Number.isFinite(-Infinity), false, "isFinite -Infinity");
assert(Number.isFinite(NaN), false, "isFinite NaN");

// Test Number.isInteger
assert(Number.isInteger(123), true, "isInteger integer");
assert(Number.isInteger(123.5), false, "isInteger float");
assert(Number.isInteger(0), true, "isInteger zero");

// Test Number.parseInt
assert(Number.parseInt("123"), 123, "parseInt");
assert(Number.parseInt("123abc"), 123, "parseInt with trailing");
assert(Number.isNaN(Number.parseInt("abc")), true, "parseInt NaN");

// Test Number.parseFloat
assert(Number.parseFloat("123.45"), 123.45, "parseFloat");
assert(Number.parseFloat("123.45abc"), 123.45, "parseFloat with trailing");

// Test global isNaN
assert(isNaN(NaN), true, "global isNaN NaN");
assert(isNaN(123), false, "global isNaN number");
assert(isNaN("hello"), true, "global isNaN string converts");

// Test global isFinite
assert(isFinite(123), true, "global isFinite");
assert(isFinite(Infinity), false, "global isFinite infinity");

// Test global parseInt and parseFloat
assert(parseInt("42"), 42, "global parseInt");
assert(parseFloat("3.14"), 3.14, "global parseFloat");

// Test toFixed
var n = 3.14159;
assert(n.toFixed(2), "3.14", "toFixed 2");
assert(n.toFixed(0), "3", "toFixed 0");

// Test toString on numbers
assert((123).toString(), "123", "number toString");
assert((255).toString(16), "ff", "number toString base 16");

// Test Date.now() returns a number
var now = Date.now();
assert(typeof now, "number", "Date.now returns number");
assert(now > 0, true, "Date.now is positive");
