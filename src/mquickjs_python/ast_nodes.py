"""AST node types for JavaScript parser."""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Union


@dataclass
class Node:
    """Base class for all AST nodes."""

    def to_dict(self) -> dict:
        """Convert node to dictionary for testing/serialization."""
        result = {"type": self.__class__.__name__}
        for key, value in self.__dict__.items():
            if isinstance(value, Node):
                result[key] = value.to_dict()
            elif isinstance(value, list):
                result[key] = [
                    v.to_dict() if isinstance(v, Node) else v
                    for v in value
                ]
            else:
                result[key] = value
        return result


# Literals
@dataclass
class NumericLiteral(Node):
    """Numeric literal: 42, 3.14, etc."""
    value: Union[int, float]


@dataclass
class StringLiteral(Node):
    """String literal: "hello", 'world'"""
    value: str


@dataclass
class BooleanLiteral(Node):
    """Boolean literal: true, false"""
    value: bool


@dataclass
class NullLiteral(Node):
    """Null literal: null"""
    pass


@dataclass
class Identifier(Node):
    """Identifier: variable names, property names"""
    name: str


@dataclass
class ThisExpression(Node):
    """The 'this' keyword."""
    pass


# Expressions
@dataclass
class ArrayExpression(Node):
    """Array literal: [1, 2, 3]"""
    elements: List[Node]


@dataclass
class ObjectExpression(Node):
    """Object literal: {a: 1, b: 2}"""
    properties: List["Property"]


@dataclass
class Property(Node):
    """Object property: key: value"""
    key: Node  # Identifier or Literal
    value: Node
    kind: str = "init"  # "init", "get", or "set"
    computed: bool = False
    shorthand: bool = False


@dataclass
class UnaryExpression(Node):
    """Unary expression: -x, !x, typeof x, etc."""
    operator: str
    argument: Node
    prefix: bool = True


@dataclass
class UpdateExpression(Node):
    """Update expression: ++x, x++, --x, x--"""
    operator: str  # "++" or "--"
    argument: Node
    prefix: bool


@dataclass
class BinaryExpression(Node):
    """Binary expression: a + b, a * b, etc."""
    operator: str
    left: Node
    right: Node


@dataclass
class LogicalExpression(Node):
    """Logical expression: a && b, a || b"""
    operator: str  # "&&" or "||"
    left: Node
    right: Node


@dataclass
class ConditionalExpression(Node):
    """Conditional (ternary) expression: a ? b : c"""
    test: Node
    consequent: Node
    alternate: Node


@dataclass
class AssignmentExpression(Node):
    """Assignment expression: a = b, a += b, etc."""
    operator: str
    left: Node
    right: Node


@dataclass
class SequenceExpression(Node):
    """Sequence expression: a, b, c"""
    expressions: List[Node]


@dataclass
class MemberExpression(Node):
    """Member expression: a.b, a[b]"""
    object: Node
    property: Node
    computed: bool  # True for a[b], False for a.b


@dataclass
class CallExpression(Node):
    """Call expression: f(a, b)"""
    callee: Node
    arguments: List[Node]


@dataclass
class NewExpression(Node):
    """New expression: new Foo(a, b)"""
    callee: Node
    arguments: List[Node]


# Statements
@dataclass
class Program(Node):
    """Program node - root of AST."""
    body: List[Node]


@dataclass
class ExpressionStatement(Node):
    """Expression statement: expression;"""
    expression: Node


@dataclass
class BlockStatement(Node):
    """Block statement: { ... }"""
    body: List[Node]


@dataclass
class EmptyStatement(Node):
    """Empty statement: ;"""
    pass


@dataclass
class VariableDeclaration(Node):
    """Variable declaration: var a = 1, b = 2;"""
    declarations: List["VariableDeclarator"]
    kind: str = "var"


@dataclass
class VariableDeclarator(Node):
    """Variable declarator: a = 1"""
    id: Identifier
    init: Optional[Node]


@dataclass
class IfStatement(Node):
    """If statement: if (test) consequent else alternate"""
    test: Node
    consequent: Node
    alternate: Optional[Node]


@dataclass
class WhileStatement(Node):
    """While statement: while (test) body"""
    test: Node
    body: Node


@dataclass
class DoWhileStatement(Node):
    """Do-while statement: do body while (test)"""
    body: Node
    test: Node


@dataclass
class ForStatement(Node):
    """For statement: for (init; test; update) body"""
    init: Optional[Node]  # VariableDeclaration or Expression
    test: Optional[Node]
    update: Optional[Node]
    body: Node


@dataclass
class ForInStatement(Node):
    """For-in statement: for (left in right) body"""
    left: Node  # VariableDeclaration or Pattern
    right: Node
    body: Node


@dataclass
class ForOfStatement(Node):
    """For-of statement: for (left of right) body"""
    left: Node
    right: Node
    body: Node


@dataclass
class BreakStatement(Node):
    """Break statement: break; or break label;"""
    label: Optional[Identifier]


@dataclass
class ContinueStatement(Node):
    """Continue statement: continue; or continue label;"""
    label: Optional[Identifier]


@dataclass
class ReturnStatement(Node):
    """Return statement: return; or return expr;"""
    argument: Optional[Node]


@dataclass
class ThrowStatement(Node):
    """Throw statement: throw expr;"""
    argument: Node


@dataclass
class TryStatement(Node):
    """Try statement: try { } catch (e) { } finally { }"""
    block: BlockStatement
    handler: Optional["CatchClause"]
    finalizer: Optional[BlockStatement]


@dataclass
class CatchClause(Node):
    """Catch clause: catch (param) { body }"""
    param: Identifier
    body: BlockStatement


@dataclass
class SwitchStatement(Node):
    """Switch statement: switch (discriminant) { cases }"""
    discriminant: Node
    cases: List["SwitchCase"]


@dataclass
class SwitchCase(Node):
    """Switch case: case test: consequent or default: consequent"""
    test: Optional[Node]  # None for default
    consequent: List[Node]


@dataclass
class LabeledStatement(Node):
    """Labeled statement: label: statement"""
    label: Identifier
    body: Node


@dataclass
class FunctionDeclaration(Node):
    """Function declaration: function name(params) { body }"""
    id: Identifier
    params: List[Identifier]
    body: BlockStatement


@dataclass
class FunctionExpression(Node):
    """Function expression: function name(params) { body }"""
    id: Optional[Identifier]
    params: List[Identifier]
    body: BlockStatement
