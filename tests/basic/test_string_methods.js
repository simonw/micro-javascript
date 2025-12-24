// Test String methods

function assert(actual, expected, message) {
    if (arguments.length == 1)
        expected = true;
    if (actual === expected)
        return;
    throw Error("assertion failed: got |" + actual + "|" +
                ", expected |" + expected + "|" +
                (message ? " (" + message + ")" : ""));
}

// Test charAt
assert("hello".charAt(0), "h", "charAt 0");
assert("hello".charAt(1), "e", "charAt 1");
assert("hello".charAt(4), "o", "charAt 4");
assert("hello".charAt(5), "", "charAt out of range");
assert("hello".charAt(-1), "", "charAt negative");

// Test charCodeAt
assert("ABC".charCodeAt(0), 65, "charCodeAt A");
assert("ABC".charCodeAt(1), 66, "charCodeAt B");

// Test indexOf
assert("hello".indexOf("l"), 2, "indexOf found");
assert("hello".indexOf("l", 3), 3, "indexOf with start");
assert("hello".indexOf("x"), -1, "indexOf not found");
assert("hello".indexOf(""), 0, "indexOf empty string");

// Test lastIndexOf
assert("hello".lastIndexOf("l"), 3, "lastIndexOf found");
assert("hello".lastIndexOf("l", 2), 2, "lastIndexOf with end");
assert("hello".lastIndexOf("x"), -1, "lastIndexOf not found");

// Test substring
assert("hello".substring(1, 4), "ell", "substring");
assert("hello".substring(1), "ello", "substring to end");
assert("hello".substring(4, 1), "ell", "substring swapped");

// Test slice
assert("hello".slice(1, 4), "ell", "slice");
assert("hello".slice(1), "ello", "slice to end");
assert("hello".slice(-2), "lo", "slice negative start");
assert("hello".slice(1, -1), "ell", "slice negative end");

// Test split
var parts = "a,b,c".split(",");
assert(parts.length, 3, "split length");
assert(parts[0], "a", "split 0");
assert(parts[1], "b", "split 1");
assert(parts[2], "c", "split 2");

// Test split with limit
var parts2 = "a,b,c".split(",", 2);
assert(parts2.length, 2, "split limit length");
assert(parts2[0], "a", "split limit 0");
assert(parts2[1], "b", "split limit 1");

// Test toLowerCase and toUpperCase
assert("Hello".toLowerCase(), "hello", "toLowerCase");
assert("Hello".toUpperCase(), "HELLO", "toUpperCase");

// Test trim
assert("  hello  ".trim(), "hello", "trim");
assert("hello".trim(), "hello", "trim no whitespace");

// Test concat
assert("hello".concat(" ", "world"), "hello world", "concat");

// Test repeat
assert("ab".repeat(3), "ababab", "repeat");
assert("x".repeat(0), "", "repeat 0");

// Test startsWith and endsWith
assert("hello".startsWith("he"), true, "startsWith true");
assert("hello".startsWith("lo"), false, "startsWith false");
assert("hello".endsWith("lo"), true, "endsWith true");
assert("hello".endsWith("he"), false, "endsWith false");

// Test includes
assert("hello".includes("ell"), true, "includes true");
assert("hello".includes("xyz"), false, "includes false");

// Test replace
assert("hello".replace("l", "L"), "heLlo", "replace first");
assert("hello world".replace("o", "0"), "hell0 world", "replace first occurrence");
