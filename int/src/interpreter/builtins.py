"""
This module contains the implementation of 
built-in classes and their methods for the SOL26 interpreter.

Author: Jiří Lach <xlachji00@stud.fit.vut.cz>
"""
import sys

from interpreter.error_codes import ErrorCode
from interpreter.exceptions import InterpreterError
from interpreter.memory import Object, Frame
from interpreter.executor import Executor
from interpreter.environment import ClassDefinition
from typing import Any


def _get_bool(executor: Executor, value: bool) -> Object:
    """Help function to return SOL True or False based on a Python boolean value."""
    cls_name = "True" if value else "False"
    return executor.heap.allocate(executor.symbol_table.get_class(cls_name), None)


def _get_nil(executor) -> Object:
    """Help function to return SOL Nil."""
    return executor.heap.allocate(executor.symbol_table.get_class("Nil"), None)

def sol_builtin_new(receiver, args, frame, executor) -> Object:
    """Default implementation of 'new' for all objects. Creates an instance of its class."""
    return executor.heap.allocate(receiver.class_def)


class SOLObject(Object):
    attributes: dict[str, Object]

    def __init__(self, class_def: ClassDefinition):
        super().__init__(class_def)
        self.attributes = {}

    def new(self, args, frame, executor) -> Object:
        return executor.heap.allocate(self.class_def)

    def identicalTo_(self, args, frame, executor) -> Object:
        return _get_bool(executor, self is args[0])

    def equalTo_(self, args, frame, executor) -> Object:
        if not self.attributes and not args[0].attributes:
            return _get_bool(executor, self is args[0])
        return _get_bool(executor, self.attributes == args[0].attributes)

    def asString(self, args, frame, executor) -> Object:
        return executor.heap.allocate(executor.symbol_table.get_class("String"), "")

    def isNumber(self, args, frame, executor) -> Object:
        return _get_bool(executor, False)

    def isString(self, args, frame, executor) -> Object:
        return _get_bool(executor, False)

    def isNil(self, args, frame, executor) -> Object:
        return _get_bool(executor, False)

    def isBlock(self, args, frame, executor) -> Object:
        return _get_bool(executor, False)

    def isBoolean(self, args, frame, executor) -> Object:
        return _get_bool(executor, False)


class SOLNil(SOLObject):
    def asString(self, args, frame, executor) -> Object:
        return executor.heap.allocate(executor.symbol_table.get_class("String"), "nil")

    def isNil(self, args, frame, executor) -> Object:
        return _get_bool(executor, True)


class SOLInteger(SOLObject):
    value: int

    def __init__(self, class_def: ClassDefinition, value: int):
        super().__init__(class_def)
        self.value = value

    def equalTo_(self, args, frame, executor) -> Object:
        if args[0].class_def.name != "Integer":
            return _get_bool(executor, False)
        return _get_bool(executor, self.value == args[0].value)

    def plus_(self, args, frame, executor) -> Object:
        return executor.heap.allocate(
            executor.symbol_table.get_class("Integer"), self.value + args[0].value
        )

    def minus_(self, args, frame, executor) -> Object:
        return executor.heap.allocate(
            executor.symbol_table.get_class("Integer"), self.value - args[0].value
        )

    def multiplyBy_(self, args, frame, executor) -> Object:
        return executor.heap.allocate(
            executor.symbol_table.get_class("Integer"), self.value * args[0].value
        )

    def divBy_(self, args, frame, executor) -> Object:
        if args[0].value == 0:
            raise InterpreterError(ErrorCode.INT_OTHER, "Division by zero")
        return executor.heap.allocate(
            executor.symbol_table.get_class("Integer"), self.value / args[0].value
        )

    def greaterThan_(self, args, frame, executor) -> Object:
        return _get_bool(executor, self.value > args[0].value)

    def timesRepeat_(self, args, frame, executor) -> Object:
        last_val = _get_nil(executor)
        if self.value > 0:
            for i in range(self.value):
                iter_obj = executor.heap.allocate(executor.symbol_table.get_class("Integer"), i)
                last_val = executor.dispatch_message(args[0], "value:", [iter_obj], frame)
        return last_val

    def asString(self, args, frame, executor) -> Object:
        return executor.heap.allocate(executor.symbol_table.get_class("String"), str(self.value))

    def isNumber(self, args, frame, executor) -> Object:
        return _get_bool(executor, True)

    def asInteger(self, args, frame, executor) -> Object:
        return self


class SOLString(SOLObject):
    value: str

    def __init__(self, class_def: ClassDefinition, value: str):
        super().__init__(class_def)
        self.value = value

    def read(self, args, frame, executor) -> Object:
        line = sys.stdin.readline()
        if line.endswith("\n"):
            line = line[:-1]
        return executor.heap.allocate(executor.symbol_table.get_class("String"), line)

    def print(self, args, frame, executor) -> Object:
        print(self.value, end="")
        return self

    def equalTo_(self, args, frame, executor) -> Object:
        if args[0].class_def.name != "String":
            return _get_bool(executor, False)
        return _get_bool(executor, self.value == args[0].value)

    def asString(self, args, frame, executor) -> Object:
        return self

    def asInteger(self, args, frame, executor) -> Object:
        try:
            return executor.heap.allocate(
                executor.symbol_table.get_class("Integer"), int(self.value)
            )
        except ValueError:
            return _get_nil(executor)

    def concatenateWith_(self, args, frame, executor) -> Object:
        curr_class = args[0].class_def
        is_str = False
        while curr_class is not None:
            if curr_class.name == "String":
                is_str = True
                break
            curr_class = curr_class.parent
        if not is_str:
            return _get_nil(executor)
        return executor.heap.allocate(
            executor.symbol_table.get_class("String"), self.value + args[0].value
        )

    def isString(self, args, frame, executor) -> Object:
        return _get_bool(executor, True)

    def startsWith_endsBefore_(self, args, frame, executor) -> Object:
        try:
            start = int(args[0].value)
            end = int(args[1].value)
            if not isinstance(start, int) or not isinstance(end, int):
                return _get_nil(executor)
        except AttributeError:
            return _get_nil(executor)

        if end - start < 0 or start < 0 or end > len(self.value):
            return executor.heap.allocate(executor.symbol_table.get_class("String"), "")
        return executor.heap.allocate(
            executor.symbol_table.get_class("String"), self.value[start - 1 : end - 1]
        )

    def length(self, args, frame, executor) -> Object:
        return executor.heap.allocate(executor.symbol_table.get_class("Integer"), len(self.value))


class SOLBlock(SOLObject):
    block_data: tuple[Any, Any]
    def value(self, args: list[Object], frame: Frame, executor: Executor) -> Object:
        block_ast, parent_frame = self.block_data
        if len(args) != block_ast.arity:
            raise InterpreterError(ErrorCode.INT_DNU, "Incorrect number of arguments for block")
        return executor.execute_user_method(frame.receiver, block_ast, args, parent_frame)

    def whileTrue_(self, args, frame, executor) -> Object:
        last_val = _get_nil(executor)
        while True:
            condition = executor.dispatch_message(self, "value", [], frame)
            if not condition.class_def.name == "True":
                break
            last_val = executor.dispatch_message(args[0], "value", [], frame)
        return last_val

    def isBlock(self, args, frame, executor) -> Object:
        return _get_bool(executor, True)


class SOLBoolean(SOLObject):
    def asString(self, args, frame, executor) -> Object:
        return executor.heap.allocate(
            executor.symbol_table.get_class("String"), self.class_def.name.lower()
        )

    def not_(self, args, frame, executor) -> Object:
        return _get_bool(executor, not (self.class_def.name == "True"))

    def isBoolean(self, args, frame, executor) -> Object:
        return _get_bool(executor, True)


class SOLTrue(SOLBoolean):
    def and_(self, args, frame, executor) -> Object:
        return executor.dispatch_message(args[0], "value", [], frame)

    def or_(self, args, frame, executor) -> Object:
        return self

    def ifTrue_ifFalse_(self, args, frame, executor) -> Object:
        block, p_frame = args[0].value
        return executor.execute_user_method(p_frame.receiver, block, [], p_frame)


class SOLFalse(SOLBoolean):
    def and_(self, args, frame, executor) -> Object:
        return self

    def or_(self, args, frame, executor) -> Object:
        return executor.dispatch_message(args[0], "value", [], frame)

    def ifTrue_ifFalse_(self, args, frame, executor) -> Object:
        block, p_frame = args[1].value
        return executor.execute_user_method(p_frame.receiver, block, [], p_frame)
