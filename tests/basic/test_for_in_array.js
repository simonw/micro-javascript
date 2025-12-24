function assert(actual, expected, message) {
    if (arguments.length == 1)
        expected = true;

    if (actual === expected)
        return;

    if (actual !== null && expected !== null
    &&  typeof actual == 'object' && typeof expected == 'object'
    &&  actual.toString() === expected.toString())
        return;

    throw Error("assertion failed: got |" + actual + "|" +
                ", expected |" + expected + "|" +
                (message ? " (" + message + ")" : ""));
}

// Test for-in over array
var a = [];
for(var i = 0; i < 10; i++)
    a.push(i);
var tab = [];
for(i in a) {
    tab.push(i);
}
assert(tab.toString(), "0,1,2,3,4,5,6,7,8,9", "for_in");
