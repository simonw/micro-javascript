// Test closures - functions capturing outer scope variables

function assert(actual, expected, message) {
    if (arguments.length == 1)
        expected = true;
    if (actual === expected)
        return;
    throw Error("assertion failed: got |" + actual + "|" +
                ", expected |" + expected + "|" +
                (message ? " (" + message + ")" : ""));
}

// Test 1: Simple closure
function test_simple_closure() {
    var x = 10;
    function inner() {
        return x;
    }
    assert(inner(), 10, "simple closure");
}

// Test 2: Closure modifying outer variable
function test_closure_modify() {
    var count = 0;
    function inc() {
        count = count + 1;
        return count;
    }
    assert(inc(), 1, "closure modify 1");
    assert(inc(), 2, "closure modify 2");
    assert(count, 2, "outer var modified");
}

// Test 3: Multiple closures sharing variable
function test_shared_closure() {
    var value = 0;
    function get() { return value; }
    function set(v) { value = v; }
    set(42);
    assert(get(), 42, "shared closure");
}

// Test 4: Nested closures
function test_nested_closure() {
    var a = 1;
    function level1() {
        var b = 2;
        function level2() {
            return a + b;
        }
        return level2();
    }
    assert(level1(), 3, "nested closure");
}

// Test 5: Closure returned from function
function test_returned_closure() {
    function makeCounter() {
        var count = 0;
        return function() {
            count = count + 1;
            return count;
        };
    }
    var counter = makeCounter();
    assert(counter(), 1, "returned closure 1");
    assert(counter(), 2, "returned closure 2");
}

test_simple_closure();
test_closure_modify();
test_shared_closure();
test_nested_closure();
test_returned_closure();
