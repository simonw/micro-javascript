// Test RegExp in JavaScript context

function assert(actual, expected, message) {
    if (arguments.length == 1)
        expected = true;
    if (actual === expected)
        return;
    throw Error("assertion failed: got |" + actual + "|" +
                ", expected |" + expected + "|" +
                (message ? " (" + message + ")" : ""));
}

// Test RegExp constructor
var re = new RegExp("abc");
assert(re.source, "abc", "source property");

// Test flags
var re2 = new RegExp("abc", "gi");
assert(re2.flags, "gi", "flags property");
assert(re2.global, true, "global flag");
assert(re2.ignoreCase, true, "ignoreCase flag");

// Test test() method
var re3 = new RegExp("hello");
assert(re3.test("hello world"), true, "test match");
assert(re3.test("goodbye"), false, "test no match");

// Test case insensitive
var re4 = new RegExp("hello", "i");
assert(re4.test("HELLO"), true, "case insensitive");

// Test exec() method
var re5 = new RegExp("(\\w+)@(\\w+)");
var result = re5.exec("user@host");
assert(result !== null, true, "exec found match");
assert(result[0], "user@host", "exec full match");
assert(result[1], "user", "exec group 1");
assert(result[2], "host", "exec group 2");

// Test exec() no match
var re6 = new RegExp("xyz");
assert(re6.exec("abc"), null, "exec no match");

// Test global flag with exec
var re7 = new RegExp("a", "g");
var s = "abab";
result = re7.exec(s);
assert(result[0], "a", "global exec first");
assert(result.index, 0, "global exec first index");

result = re7.exec(s);
assert(result[0], "a", "global exec second");
assert(result.index, 2, "global exec second index");

result = re7.exec(s);
assert(result, null, "global exec exhausted");

// Test lastIndex property
var re8 = new RegExp("a", "g");
assert(re8.lastIndex, 0, "initial lastIndex");
re8.exec("abab");
assert(re8.lastIndex, 1, "lastIndex after exec");

// Test multiline
var re9 = new RegExp("^line", "m");
assert(re9.test("first\nline two"), true, "multiline start");

// Test character classes
var re10 = new RegExp("\\d+");
assert(re10.test("abc123def"), true, "digit class");
assert(re10.test("abc"), false, "no digits");

// Test quantifiers
var re11 = new RegExp("a+");
assert(re11.test("aaa"), true, "plus quantifier");
assert(re11.test("b"), false, "plus needs match");
