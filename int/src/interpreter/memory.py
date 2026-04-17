"""
This module contains the memory management logic for the interpreter.

Author: Jiří Lach <xlachji00@stud.fit.vut.cz>
"""

from typing import TYPE_CHECKING, Any

from interpreter.error_codes import ErrorCode
from interpreter.exceptions import InterpreterError
if TYPE_CHECKING:
    from interpreter.environment import ClassDefinition


class Object:
    """Instantiation of a class. Contains reference to its class definition and its attributes."""
    class_def: ClassDefinition

    def __init__(self, class_def: ClassDefinition, value: Any = None):
        self.class_def = class_def
        self.attributes: dict[str, Object] = {}
        self.value = value
        self.method_class = None

    def __str__(self) -> str:
        if self.value is not None:
            return f"<Object {self.class_def.name}: {self.value}>"
        return f"<Object {self.class_def.name}>"


class Frame:
    """Local variable scope. Each method call creates a new frame."""

    def __init__(self, receiver: Object, parent_frame: Frame | None = None):
        self.receiver = receiver
        self.parent_frame = parent_frame
        self.variables: dict[str, Object] = {}
        self.method_class: Any = None

    def get_var(self, name: str) -> Object:
        """Gets the value of a variable. If the variable is not found in the current frame, it looks up in the parent frames."""
        if name in ("self", "super"):
            return self.receiver

        if name in self.variables:
            return self.variables[name]

        if self.parent_frame is not None:
            return self.parent_frame.get_var(name)

        raise InterpreterError(
            ErrorCode.SEM_UNDEF,  
            f"Variable '{name}' was read before being initialized.",
        )

    def set_var(self, name: str, value: Object) -> None:
        """Assign a value to a variable. If the variable already exists in the current or any parent frame, update it there. Otherwise, create it in the current frame."""
        if name in ("self", "super"):
            raise InterpreterError(
                ErrorCode.SEM_ERROR,
                "Cannot assign to pseudovariable 'self' or 'super'.",
            )

        current: Frame | None = self
        while current is not None:
            if name in current.variables:
                current.variables[name] = value
                return
            current = current.parent_frame

        self.variables[name] = value


class Heap:
    """Memory management for all objects. In a real interpreter"""
    def __init__(self) -> None:
        self.objects: list[Object] = []

    def allocate(self, class_def: ClassDefinition, value: Any = None) -> Object:
        """Vytvoří nový objekt a zapíše si ho do paměti."""
        new_obj = Object(class_def, value)
        self.objects.append(new_obj)
        return new_obj
