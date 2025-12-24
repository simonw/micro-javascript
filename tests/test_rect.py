"""
Test for exposing Python classes to JavaScript.

This replicates the test_rect.js test but exposes Python Rectangle and FilledRectangle
classes to the JavaScript context, demonstrating Python/JS interop.
"""
import pytest
from pathlib import Path

from mquickjs_python import JSContext
from mquickjs_python.values import JSObject, JSCallableObject, JSFunction, UNDEFINED


def create_rectangle_constructor(ctx, object_prototype):
    """Create a Rectangle constructor that can be used from JavaScript."""

    # Create the Rectangle prototype
    rectangle_prototype = JSObject(object_prototype)

    # Constructor function - new Rectangle(x, y)
    def rectangle_constructor(*args):
        obj = JSObject(rectangle_prototype)
        obj.set("x", args[0] if len(args) > 0 else UNDEFINED)
        obj.set("y", args[1] if len(args) > 1 else UNDEFINED)
        return obj

    # Create a callable object that acts as constructor
    rect_constructor = JSCallableObject(rectangle_constructor)
    rect_constructor._name = "Rectangle"
    rect_constructor.set("prototype", rectangle_prototype)
    rectangle_prototype.set("constructor", rect_constructor)

    # Static method: Rectangle.getClosure(str) returns a function that returns str
    def get_closure(*args):
        captured = args[0] if args else UNDEFINED
        def closure_fn(*inner_args):
            return captured
        return closure_fn

    rect_constructor.set("getClosure", get_closure)

    # Static method: Rectangle.call(callback, arg) calls callback with arg
    def call_fn(*args):
        callback = args[0] if len(args) > 0 else UNDEFINED
        arg = args[1] if len(args) > 1 else UNDEFINED
        if isinstance(callback, JSFunction):
            # Call JS function through context
            return ctx._call_function(callback, [arg])
        elif callable(callback):
            return callback(arg)
        return UNDEFINED

    rect_constructor.set("call", call_fn)

    return rect_constructor, rectangle_prototype


def create_filled_rectangle_constructor(object_prototype, rectangle_prototype):
    """Create a FilledRectangle constructor that inherits from Rectangle."""

    # Create the FilledRectangle prototype inheriting from Rectangle
    filled_rect_prototype = JSObject(rectangle_prototype)

    # Constructor function - new FilledRectangle(x, y, color)
    def filled_rect_constructor(*args):
        obj = JSObject(filled_rect_prototype)
        obj.set("x", args[0] if len(args) > 0 else UNDEFINED)
        obj.set("y", args[1] if len(args) > 1 else UNDEFINED)
        obj.set("color", args[2] if len(args) > 2 else UNDEFINED)
        return obj

    # Create a callable object that acts as constructor
    filled_constructor = JSCallableObject(filled_rect_constructor)
    filled_constructor._name = "FilledRectangle"
    filled_constructor.set("prototype", filled_rect_prototype)
    filled_rect_prototype.set("constructor", filled_constructor)

    return filled_constructor


class TestRectangle:
    """Tests for Rectangle class interop between Python and JavaScript."""

    def test_rectangle_basic(self):
        """Test creating a Rectangle from JavaScript."""
        ctx = JSContext()

        # Create and expose Rectangle constructor
        rect_constructor, rect_prototype = create_rectangle_constructor(ctx, ctx._object_prototype)
        ctx.set("Rectangle", rect_constructor)

        # Test from JavaScript
        result = ctx.eval("""
            var r = new Rectangle(100, 200);
            r.x + ',' + r.y;
        """)
        assert result == "100,200"

    def test_rectangle_x_y_properties(self):
        """Test Rectangle x and y properties individually."""
        ctx = JSContext()

        rect_constructor, rect_prototype = create_rectangle_constructor(ctx, ctx._object_prototype)
        ctx.set("Rectangle", rect_constructor)

        assert ctx.eval("new Rectangle(100, 200).x") == 100
        assert ctx.eval("new Rectangle(100, 200).y") == 200

    def test_filled_rectangle_inheritance(self):
        """Test FilledRectangle inheriting from Rectangle."""
        ctx = JSContext()

        rect_constructor, rect_prototype = create_rectangle_constructor(ctx, ctx._object_prototype)
        filled_constructor = create_filled_rectangle_constructor(ctx._object_prototype, rect_prototype)

        ctx.set("Rectangle", rect_constructor)
        ctx.set("FilledRectangle", filled_constructor)

        result = ctx.eval("""
            var r2 = new FilledRectangle(100, 200, 0x123456);
            r2.x + ',' + r2.y + ',' + r2.color;
        """)
        assert result == "100,200,1193046"

    def test_rectangle_get_closure(self):
        """Test Rectangle.getClosure static method."""
        ctx = JSContext()

        rect_constructor, rect_prototype = create_rectangle_constructor(ctx, ctx._object_prototype)
        ctx.set("Rectangle", rect_constructor)

        result = ctx.eval("""
            var func = Rectangle.getClosure("abcd");
            func();
        """)
        assert result == "abcd"

    def test_rectangle_call_callback(self):
        """Test Rectangle.call static method with JavaScript callback."""
        ctx = JSContext()

        rect_constructor, rect_prototype = create_rectangle_constructor(ctx, ctx._object_prototype)
        ctx.set("Rectangle", rect_constructor)

        result = ctx.eval("""
            function cb(param) {
                return "test" + param;
            }
            Rectangle.call(cb, "abc");
        """)
        assert result == "testabc"

    def test_full_test_rect_js(self):
        """Run the full test_rect.js test file with Python-exposed classes."""
        ctx = JSContext()

        # Create and expose both constructors
        rect_constructor, rect_prototype = create_rectangle_constructor(ctx, ctx._object_prototype)
        filled_constructor = create_filled_rectangle_constructor(ctx._object_prototype, rect_prototype)

        ctx.set("Rectangle", rect_constructor)
        ctx.set("FilledRectangle", filled_constructor)

        # Read and run the test_rect.js file
        test_file = Path(__file__).parent / "test_rect.js"
        source = test_file.read_text(encoding="utf-8")

        # Run the test - if it throws, the test fails
        ctx.eval(source)
