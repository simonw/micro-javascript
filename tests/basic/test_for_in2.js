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

function test_for_in2()
{
    var i, tab;
    tab = [];
    for(i in {x:1, y: 2, z:3}) {
        if (i === "y")
            continue;
        tab.push(i);
    }
    assert(tab.toString(), "x,z");

    tab = [];
    for(i in {x:1, y: 2, z:3}) {
        if (i === "z")
            break;
        tab.push(i);
    }
    assert(tab.toString(), "x,y");
}

test_for_in2();
