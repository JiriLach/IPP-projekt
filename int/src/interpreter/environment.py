"""
This module contains the implementation of the Environment class,
which is responsible for storing variable bindings and function definitions
during the interpretation of the source code.

Author: Jiří Lach <xlachji00@stud.fit.vut.cz>
"""

from typing import Any

from interpreter.error_codes import ErrorCode
from interpreter.exceptions import InterpreterError


class ClassDefinition:
    """
    Represents a class definition in the SOL26 language. Contains the class name,
    reference to its parent class (for inheritance),
    and a dictionary of methods defined in this class.
    """

    def __init__(self, name: str, parent: ClassDefinition | None = None):
        self.name = name
        self.parent = parent
        self.methods: dict[str, Any] = {}

    def add_method(self, selector: str, implementation: Any) -> None:
        """Registers a method implementation for a given selector in this class."""
        self.methods[selector] = implementation

    def lookup_method(self, selector: str) -> Any:
        """
        Tryes to find a method implementation for the given selector.
        If the method is not found in the current class,
        it looks up in the parent class recursively
        """
        if selector in self.methods:
            return self.methods[selector]

        if self.parent is not None:
            return self.parent.lookup_method(selector)

        return None

    def lookup_method_with_class(self, selector: str) -> tuple[Any, ClassDefinition | None]:
        """Same as lookup_method, but returns a tuple: (method_code, class_where_found)"""
        if selector in self.methods:
            return self.methods[selector], self

        if self.parent is not None:
            return self.parent.lookup_method_with_class(selector)

        return None, None

    def __str__(self) -> str:
        parent_name = self.parent.name if self.parent else "None"
        return f"<ClassDef: {self.name} : {parent_name}>"


class SymbolTable:
    """Global registry of all class definitions. Provides methods to register and retrieve classes."""

    def __init__(self) -> None:
        self.classes: dict[str, ClassDefinition] = {}
        self._bootstrap_builtins()

    def register_class(self, class_def: ClassDefinition) -> None:
        self.classes[class_def.name] = class_def

    def get_class(self, name: str) -> ClassDefinition:
        if name not in self.classes:
            raise InterpreterError(ErrorCode.SEM_UNDEF, f"Class '{name}' is not defined.")
        return self.classes[name]

    def _bootstrap_builtins(self) -> None:
        """Inicialization of built-in classes and their methods."""
        obj_class = ClassDefinition("Object", parent=None)
        self.register_class(obj_class)

        integer_class = ClassDefinition("Integer", parent=obj_class)
        self.register_class(integer_class)

        string_class = ClassDefinition("String", parent=obj_class)
        self.register_class(string_class)

        nil_class = ClassDefinition("Nil", parent=obj_class)
        self.register_class(nil_class)

        true_class = ClassDefinition("True", parent=obj_class)
        self.register_class(true_class)

        false_class = ClassDefinition("False", parent=obj_class)
        self.register_class(false_class)

        block_class = ClassDefinition("Block", parent=obj_class)
        self.register_class(block_class)

        import interpreter.builtins as b

        # Object
        obj_class.add_method("new", b.SOLObject.new)
        obj_class.add_method("identicalTo:", b.SOLObject.identicalTo_)
        obj_class.add_method("equalTo:", b.SOLObject.equalTo_)
        obj_class.add_method("asString", b.SOLObject.asString)
        obj_class.add_method("isNumber", b.SOLObject.isNumber)
        obj_class.add_method("isString", b.SOLObject.isString)
        obj_class.add_method("isBlock", b.SOLObject.isBlock)
        obj_class.add_method("isNil", b.SOLObject.isNil)
        obj_class.add_method("isBoolean", b.SOLObject.isBoolean)

        # Nil
        nil_class.add_method("asString", b.SOLNil.asString)
        nil_class.add_method("isNil", b.SOLNil.isNil)

        # Integer
        integer_class.add_method("equalTo:", b.SOLInteger.equalTo_)
        integer_class.add_method("plus:", b.SOLInteger.plus_)
        integer_class.add_method("minus:", b.SOLInteger.minus_)
        integer_class.add_method("multiplyBy:", b.SOLInteger.multiplyBy_)
        integer_class.add_method("divBy:", b.SOLInteger.divBy_)
        integer_class.add_method("greaterThan:", b.SOLInteger.greaterThan_)
        integer_class.add_method("asString", b.SOLInteger.asString)
        integer_class.add_method("asInteger", b.SOLInteger.asInteger)
        integer_class.add_method("isNumber", b.SOLInteger.isNumber)
        integer_class.add_method("timesRepeat:", b.SOLInteger.timesRepeat_)

        # String
        string_class.add_method("read", b.SOLString.read)
        string_class.add_method("print", b.SOLString.print)
        string_class.add_method("equalTo:", b.SOLString.equalTo_)
        string_class.add_method("asString", b.SOLString.asString)
        string_class.add_method("asInteger", b.SOLString.asInteger)
        string_class.add_method("concatenateWith:", b.SOLString.concatenateWith_)
        string_class.add_method("startsWith:endsBefore:", b.SOLString.startsWith_endsBefore_)
        string_class.add_method("length", b.SOLString.length)
        string_class.add_method("isString", b.SOLString.isString)

        # Block
        block_class.add_method("value", b.SOLBlock.value)
        block_class.add_method("value:", b.SOLBlock.value)
        block_class.add_method("value:value:", b.SOLBlock.value)
        block_class.add_method("whileTrue:", b.SOLBlock.whileTrue_)
        block_class.add_method("isBlock", b.SOLBlock.isBlock)

        # Booleans
        true_class.add_method("asString", b.SOLBoolean.asString)
        false_class.add_method("asString", b.SOLBoolean.asString)
        true_class.add_method("not", b.SOLBoolean.not_)
        false_class.add_method("not", b.SOLBoolean.not_)
        true_class.add_method("isBoolean", b.SOLBoolean.isBoolean)
        false_class.add_method("isBoolean", b.SOLBoolean.isBoolean)
        true_class.add_method("and:", b.SOLTrue.and_)
        false_class.add_method("and:", b.SOLFalse.and_)
        true_class.add_method("or:", b.SOLTrue.or_)
        false_class.add_method("or:", b.SOLFalse.or_)
        true_class.add_method("ifTrue:ifFalse:", b.SOLTrue.ifTrue_ifFalse_)
        false_class.add_method("ifTrue:ifFalse:", b.SOLFalse.ifTrue_ifFalse_)
