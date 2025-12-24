// Test Math object

function assert(actual, expected, message) {
    if (arguments.length == 1)
        expected = true;
    if (actual === expected)
        return;
    // For floating point comparisons, allow small differences
    if (typeof actual === 'number' && typeof expected === 'number') {
        if (Math.abs(actual - expected) < 0.0001)
            return;
    }
    throw Error("assertion failed: got |" + actual + "|" +
                ", expected |" + expected + "|" +
                (message ? " (" + message + ")" : ""));
}

// Test Math constants
assert(Math.PI > 3.14 && Math.PI < 3.15, true, "Math.PI");
assert(Math.E > 2.71 && Math.E < 2.72, true, "Math.E");

// Test Math.abs
assert(Math.abs(-5), 5, "abs negative");
assert(Math.abs(5), 5, "abs positive");
assert(Math.abs(0), 0, "abs zero");

// Test Math.floor and Math.ceil
assert(Math.floor(3.7), 3, "floor");
assert(Math.floor(-3.7), -4, "floor negative");
assert(Math.ceil(3.2), 4, "ceil");
assert(Math.ceil(-3.2), -3, "ceil negative");

// Test Math.round
assert(Math.round(3.5), 4, "round up");
assert(Math.round(3.4), 3, "round down");
assert(Math.round(-3.5), -3, "round negative");

// Test Math.trunc
assert(Math.trunc(3.7), 3, "trunc positive");
assert(Math.trunc(-3.7), -3, "trunc negative");

// Test Math.min and Math.max
assert(Math.min(1, 2, 3), 1, "min");
assert(Math.max(1, 2, 3), 3, "max");
assert(Math.min(-1, -2, -3), -3, "min negative");
assert(Math.max(-1, -2, -3), -1, "max negative");

// Test Math.pow
assert(Math.pow(2, 3), 8, "pow");
assert(Math.pow(3, 2), 9, "pow 3^2");

// Test Math.sqrt
assert(Math.sqrt(4), 2, "sqrt 4");
assert(Math.sqrt(9), 3, "sqrt 9");

// Test Math.sin, Math.cos, Math.tan
assert(Math.sin(0), 0, "sin 0");
assert(Math.cos(0), 1, "cos 0");
assert(Math.tan(0), 0, "tan 0");

// Test Math.log and Math.exp
assert(Math.log(1), 0, "log 1");
assert(Math.exp(0), 1, "exp 0");

// Test Math.random returns number between 0 and 1
var r = Math.random();
assert(r >= 0 && r < 1, true, "random range");

// Test Math.sign
assert(Math.sign(5), 1, "sign positive");
assert(Math.sign(-5), -1, "sign negative");
assert(Math.sign(0), 0, "sign zero");
