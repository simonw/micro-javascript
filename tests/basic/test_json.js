// Test JSON object

function assert(actual, expected, message) {
    if (arguments.length == 1)
        expected = true;
    if (actual === expected)
        return;
    throw Error("assertion failed: got |" + actual + "|" +
                ", expected |" + expected + "|" +
                (message ? " (" + message + ")" : ""));
}

// Test JSON.parse with primitives
assert(JSON.parse("123"), 123, "parse number");
assert(JSON.parse("true"), true, "parse true");
assert(JSON.parse("false"), false, "parse false");
assert(JSON.parse("null"), null, "parse null");
assert(JSON.parse('"hello"'), "hello", "parse string");

// Test JSON.parse with array
var arr = JSON.parse("[1, 2, 3]");
assert(arr.length, 3, "parse array length");
assert(arr[0], 1, "parse array 0");
assert(arr[2], 3, "parse array 2");

// Test JSON.parse with object
var obj = JSON.parse('{"a": 1, "b": "hello"}');
assert(obj.a, 1, "parse object a");
assert(obj.b, "hello", "parse object b");

// Test JSON.stringify with primitives
assert(JSON.stringify(123), "123", "stringify number");
assert(JSON.stringify(true), "true", "stringify true");
assert(JSON.stringify(false), "false", "stringify false");
assert(JSON.stringify(null), "null", "stringify null");
assert(JSON.stringify("hello"), '"hello"', "stringify string");

// Test JSON.stringify with array
var strArr = JSON.stringify([1, 2, 3]);
assert(strArr, "[1,2,3]", "stringify array");

// Test JSON.stringify with object
var strObj = JSON.stringify({a: 1, b: "hello"});
// Object key order may vary, check contains
assert(strObj.indexOf('"a":1') >= 0 || strObj.indexOf('"a": 1') >= 0, true, "stringify object has a");
assert(strObj.indexOf('"b":"hello"') >= 0 || strObj.indexOf('"b": "hello"') >= 0, true, "stringify object has b");

// Test nested structures
var nested = JSON.parse('{"arr": [1, 2], "obj": {"x": 10}}');
assert(nested.arr.length, 2, "parse nested array length");
assert(nested.obj.x, 10, "parse nested object");
