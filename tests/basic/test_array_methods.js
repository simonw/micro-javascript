// Test Array methods

function assert(actual, expected, message) {
    if (arguments.length == 1)
        expected = true;
    if (actual === expected)
        return;
    throw Error("assertion failed: got |" + actual + "|" +
                ", expected |" + expected + "|" +
                (message ? " (" + message + ")" : ""));
}

// Test map
var doubled = [1, 2, 3].map(function(x) { return x * 2; });
assert(doubled.length, 3, "map length");
assert(doubled[0], 2, "map 0");
assert(doubled[1], 4, "map 1");
assert(doubled[2], 6, "map 2");

// Test filter
var evens = [1, 2, 3, 4].filter(function(x) { return x % 2 === 0; });
assert(evens.length, 2, "filter length");
assert(evens[0], 2, "filter 0");
assert(evens[1], 4, "filter 1");

// Test reduce
var sum = [1, 2, 3, 4].reduce(function(acc, x) { return acc + x; }, 0);
assert(sum, 10, "reduce sum");

var product = [1, 2, 3, 4].reduce(function(acc, x) { return acc * x; }, 1);
assert(product, 24, "reduce product");

// Test forEach
var total = 0;
[1, 2, 3].forEach(function(x) { total = total + x; });
assert(total, 6, "forEach");

// Test indexOf
assert([1, 2, 3, 2].indexOf(2), 1, "indexOf found");
assert([1, 2, 3].indexOf(4), -1, "indexOf not found");
assert([1, 2, 3, 2].indexOf(2, 2), 3, "indexOf with start");

// Test lastIndexOf
assert([1, 2, 3, 2].lastIndexOf(2), 3, "lastIndexOf found");
assert([1, 2, 3].lastIndexOf(4), -1, "lastIndexOf not found");

// Test find
var found = [1, 2, 3, 4].find(function(x) { return x > 2; });
assert(found, 3, "find");

var notFound = [1, 2, 3].find(function(x) { return x > 10; });
assert(notFound, undefined, "find not found");

// Test findIndex
var foundIdx = [1, 2, 3, 4].findIndex(function(x) { return x > 2; });
assert(foundIdx, 2, "findIndex");

var notFoundIdx = [1, 2, 3].findIndex(function(x) { return x > 10; });
assert(notFoundIdx, -1, "findIndex not found");

// Test some
assert([1, 2, 3].some(function(x) { return x > 2; }), true, "some true");
assert([1, 2, 3].some(function(x) { return x > 10; }), false, "some false");

// Test every
assert([2, 4, 6].every(function(x) { return x % 2 === 0; }), true, "every true");
assert([2, 3, 4].every(function(x) { return x % 2 === 0; }), false, "every false");

// Test concat
var arr1 = [1, 2];
var arr2 = [3, 4];
var combined = arr1.concat(arr2);
assert(combined.length, 4, "concat length");
assert(combined[0], 1, "concat 0");
assert(combined[2], 3, "concat 2");

// Test slice
var sliced = [1, 2, 3, 4, 5].slice(1, 4);
assert(sliced.length, 3, "slice length");
assert(sliced[0], 2, "slice 0");
assert(sliced[2], 4, "slice 2");

var sliceNeg = [1, 2, 3, 4, 5].slice(-2);
assert(sliceNeg.length, 2, "slice negative length");
assert(sliceNeg[0], 4, "slice negative 0");

// Test reverse
var rev = [1, 2, 3].reverse();
assert(rev[0], 3, "reverse 0");
assert(rev[1], 2, "reverse 1");
assert(rev[2], 1, "reverse 2");

// Test includes
assert([1, 2, 3].includes(2), true, "includes true");
assert([1, 2, 3].includes(4), false, "includes false");

// Test shift and unshift
var shiftArr = [1, 2, 3];
var shifted = shiftArr.shift();
assert(shifted, 1, "shift return");
assert(shiftArr.length, 2, "shift length");
assert(shiftArr[0], 2, "shift first element");

var unshiftArr = [2, 3];
var newLen = unshiftArr.unshift(1);
assert(newLen, 3, "unshift return");
assert(unshiftArr[0], 1, "unshift first");
