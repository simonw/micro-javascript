// Test Object methods

function assert(actual, expected, message) {
    if (arguments.length == 1)
        expected = true;
    if (actual === expected)
        return;
    throw Error("assertion failed: got |" + actual + "|" +
                ", expected |" + expected + "|" +
                (message ? " (" + message + ")" : ""));
}

// Test Object.keys
var obj = {a: 1, b: 2, c: 3};
var keys = Object.keys(obj);
assert(keys.length, 3, "Object.keys length");
assert(keys.indexOf("a") >= 0, true, "Object.keys has a");
assert(keys.indexOf("b") >= 0, true, "Object.keys has b");
assert(keys.indexOf("c") >= 0, true, "Object.keys has c");

// Test Object.values
var vals = Object.values(obj);
assert(vals.length, 3, "Object.values length");
assert(vals.indexOf(1) >= 0, true, "Object.values has 1");
assert(vals.indexOf(2) >= 0, true, "Object.values has 2");
assert(vals.indexOf(3) >= 0, true, "Object.values has 3");

// Test Object.entries
var entries = Object.entries(obj);
assert(entries.length, 3, "Object.entries length");
// Each entry is [key, value]
var found = false;
for (var i = 0; i < entries.length; i++) {
    if (entries[i][0] === "a" && entries[i][1] === 1) {
        found = true;
    }
}
assert(found, true, "Object.entries has [a, 1]");

// Test hasOwnProperty
assert(obj.hasOwnProperty("a"), true, "hasOwnProperty true");
assert(obj.hasOwnProperty("x"), false, "hasOwnProperty false");

// Test Object.assign
var target = {a: 1};
var source = {b: 2, c: 3};
var result = Object.assign(target, source);
assert(target.a, 1, "assign target.a");
assert(target.b, 2, "assign target.b");
assert(target.c, 3, "assign target.c");
assert(result === target, true, "assign returns target");
