"""Tests for bytecode encoding limits and the disassembler."""

import re

from microjs import Context
from microjs.compiler import Compiler
from microjs.opcodes import disassemble
from microjs.parser import Parser


def test_more_than_255_constants():
    source = "var a = [" + ",".join(f'"s{i}"' for i in range(300)) + "]; a[299]"
    assert Context(time_limit=10.0).eval(source) == "s299"


def test_more_than_255_locals():
    body = "".join(f"var v{i} = {i};" for i in range(300))
    source = f"function f() {{ {body} return v0 + v299 }} f()"
    assert Context(time_limit=10.0).eval(source) == 299


def test_more_than_255_globals():
    source = "".join(f"var g{i} = {i};" for i in range(300)) + "g299"
    assert Context(time_limit=10.0).eval(source) == 299


def test_forward_jump_over_64k_of_bytecode():
    body = "x = x + 1;\n" * 15000
    source = "var x = 0; if (false) {\n" + body + "}\n x"
    assert Context(time_limit=30.0).eval(source) == 0


def test_backward_jump_over_64k_of_bytecode():
    body = "x = x + 1;\n" * 15000
    source = "var x = 0; for (var i = 0; i < 2; i++) {\n" + body + "}\n x"
    assert Context(time_limit=30.0).eval(source) == 30000


def test_catch_handler_beyond_64k_of_bytecode():
    body = "x = x + 1;\n" * 15000
    source = "var x = 0, r; try {\n" + body + "throw 1 } catch (e) { r = x }\n r"
    assert Context(time_limit=30.0).eval(source) == 15000


def _all_functions(compiled):
    """Yield compiled and every function compiled inside it."""
    yield compiled
    for const in compiled.constants:
        if hasattr(const, "bytecode"):
            yield from _all_functions(const)


def test_disassemble_decodes_every_operand():
    source = """
        function outer() {
            var n = 0;
            return function () { n = n + 1; return n };
        }
        for (var i = 0; i < 2; i++) { try { outer()() } catch (e) {} }
    """
    compiled = Compiler().compile(Parser(source).parse())
    listings = [disassemble(f.bytecode, f.constants) for f in _all_functions(compiled)]
    text = "\n".join(listings)
    assert re.search(r"STORE_CELL \d+", text)
    assert re.search(r"LOAD_CLOSURE \d+", text)
    # Jump targets land on instruction boundaries
    for listing in listings:
        lines = [line.split() for line in listing.splitlines()]
        offsets = {int(parts[0].rstrip(":")) for parts in lines}
        for parts in lines:
            if parts[1] in ("JUMP", "JUMP_IF_FALSE", "JUMP_IF_TRUE", "TRY_START"):
                assert int(parts[2]) in offsets, parts
