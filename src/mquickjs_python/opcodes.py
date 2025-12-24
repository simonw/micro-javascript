"""Bytecode opcodes for the JavaScript VM."""

from enum import IntEnum, auto


class OpCode(IntEnum):
    """Bytecode operation codes."""

    # Stack operations
    POP = auto()          # Pop and discard top of stack
    DUP = auto()          # Duplicate top of stack
    SWAP = auto()         # Swap top two stack items
    ROT3 = auto()         # Rotate 3 items: a, b, c -> b, c, a

    # Constants
    LOAD_CONST = auto()   # Load constant from pool: arg = constant index
    LOAD_UNDEFINED = auto()
    LOAD_NULL = auto()
    LOAD_TRUE = auto()
    LOAD_FALSE = auto()

    # Variables
    LOAD_NAME = auto()    # Load variable by name: arg = name index
    STORE_NAME = auto()   # Store variable by name: arg = name index
    LOAD_LOCAL = auto()   # Load local variable: arg = slot index
    STORE_LOCAL = auto()  # Store local variable: arg = slot index

    # Properties
    GET_PROP = auto()     # Get property: obj, key -> value
    SET_PROP = auto()     # Set property: obj, key, value -> value
    DELETE_PROP = auto()  # Delete property: obj, key -> bool

    # Arrays/Objects
    BUILD_ARRAY = auto()  # Build array from stack: arg = element count
    BUILD_OBJECT = auto() # Build object from stack: arg = property count

    # Arithmetic
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    MOD = auto()
    POW = auto()
    NEG = auto()          # Unary minus
    POS = auto()          # Unary plus

    # Bitwise
    BAND = auto()         # Bitwise AND
    BOR = auto()          # Bitwise OR
    BXOR = auto()         # Bitwise XOR
    BNOT = auto()         # Bitwise NOT
    SHL = auto()          # Shift left
    SHR = auto()          # Shift right (signed)
    USHR = auto()         # Shift right (unsigned)

    # Comparison
    LT = auto()           # Less than
    LE = auto()           # Less than or equal
    GT = auto()           # Greater than
    GE = auto()           # Greater than or equal
    EQ = auto()           # Equal (==)
    NE = auto()           # Not equal (!=)
    SEQ = auto()          # Strict equal (===)
    SNE = auto()          # Strict not equal (!==)

    # Logical
    NOT = auto()          # Logical NOT
    # && and || are handled by conditional jumps

    # Type operations
    TYPEOF = auto()       # typeof operator
    INSTANCEOF = auto()   # instanceof operator
    IN = auto()           # in operator

    # Control flow
    JUMP = auto()         # Unconditional jump: arg = offset
    JUMP_IF_FALSE = auto() # Conditional jump: arg = offset
    JUMP_IF_TRUE = auto()  # Conditional jump: arg = offset

    # Function operations
    CALL = auto()         # Call function: arg = argument count
    CALL_METHOD = auto()  # Call method: arg = argument count
    RETURN = auto()       # Return from function
    RETURN_UNDEFINED = auto()  # Return undefined from function

    # Object operations
    NEW = auto()          # New object: arg = argument count
    THIS = auto()         # Load 'this' value

    # Exception handling
    THROW = auto()        # Throw exception
    TRY_START = auto()    # Start try block: arg = catch offset
    TRY_END = auto()      # End try block
    CATCH = auto()        # Catch handler

    # Iteration
    FOR_IN_INIT = auto()  # Initialize for-in: obj -> iterator
    FOR_IN_NEXT = auto()  # Get next for-in: iterator -> key, done

    # Increment/Decrement
    INC = auto()          # Increment
    DEC = auto()          # Decrement
    POST_INC = auto()     # Post-increment (returns old value)
    POST_DEC = auto()     # Post-decrement (returns old value)

    # Closures
    MAKE_CLOSURE = auto() # Create closure: arg = function index


def disassemble(bytecode: bytes, constants: list) -> str:
    """Disassemble bytecode for debugging."""
    lines = []
    i = 0
    while i < len(bytecode):
        op = OpCode(bytecode[i])
        line = f"{i:4d}: {op.name}"

        if op in (
            OpCode.LOAD_CONST, OpCode.LOAD_NAME, OpCode.STORE_NAME,
            OpCode.LOAD_LOCAL, OpCode.STORE_LOCAL,
            OpCode.JUMP, OpCode.JUMP_IF_FALSE, OpCode.JUMP_IF_TRUE,
            OpCode.CALL, OpCode.CALL_METHOD, OpCode.NEW,
            OpCode.BUILD_ARRAY, OpCode.BUILD_OBJECT,
            OpCode.TRY_START, OpCode.MAKE_CLOSURE,
        ):
            # Has argument
            if i + 1 < len(bytecode):
                arg = bytecode[i + 1]
                if op == OpCode.LOAD_CONST and arg < len(constants):
                    line += f" {arg} ({constants[arg]!r})"
                else:
                    line += f" {arg}"
                i += 2
            else:
                i += 1
        else:
            i += 1

        lines.append(line)

    return "\n".join(lines)
