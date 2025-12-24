// Test try-finally - what's currently working

function assert(actual, expected, message) {
    if (arguments.length == 1)
        expected = true;
    if (actual === expected)
        return;
    throw "assertion failed: got |" + actual + "|" +
                ", expected |" + expected + "|" +
                (message ? " (" + message + ")" : "");
}

// Test 1: Finally runs on normal exit
function test_normal() {
    var result = [];
    try {
        result.push(1);
    } finally {
        result.push(2);
    }
    result.push(3);
    return result.join(',');
}
assert(test_normal(), "1,2,3", "finally on normal exit");

// Test 2: Try-catch-finally together
function test_catch_finally() {
    var result = [];
    try {
        result.push(1);
        throw "error";
    } catch (e) {
        result.push(2);
    } finally {
        result.push(3);
    }
    return result.join(',');
}
assert(test_catch_finally(), "1,2,3", "try-catch-finally");
