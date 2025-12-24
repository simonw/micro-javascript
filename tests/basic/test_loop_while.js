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

function test_while()
{
    var i, c;
    i = 0;
    c = 0;
    while (i < 3) {
        c++;
        i++;
    }
    assert(c === 3);
}

function test_while_break()
{
    var i, c;
    i = 0;
    c = 0;
    while (i < 3) {
        c++;
        if (i == 1)
            break;
        i++;
    }
    assert(c === 2 && i === 1);
}

function test_do_while()
{
    var i, c;
    i = 0;
    c = 0;
    do {
        c++;
        i++;
    } while (i < 3);
    assert(c === 3 && i === 3);
}

test_while();
test_while_break();
test_do_while();
