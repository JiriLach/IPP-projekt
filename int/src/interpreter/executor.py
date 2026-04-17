"""
This module contains the implementation of the Executor class,
which is responsible for executing the AST nodes and managing the flow of the program.

Author: Jiří Lach <xlachji00@stud.fit.vut.cz>
"""
from typing import Any

from interpreter.environment import SymbolTable
from interpreter.error_codes import ErrorCode
from interpreter.exceptions import InterpreterError
from interpreter.input_model import Assign, Block, Expr, Literal, Send
from interpreter.memory import Frame, Heap, Object
from typing import Optional, Any, TextIO


class Executor:
    """The main execution egine of the interpreter."""

    def __init__(self, symbol_table: SymbolTable, heap: Heap):
        self.symbol_table = symbol_table
        self.heap = heap
        self.input_io: Optional[TextIO] = None

    def execute_expr(self, expr: Expr, frame: Frame) -> Object:
        """The core of the evaluator. Decides what to do with an expression."""
        if hasattr(expr, 'self_ref') and expr.self_ref is not None:
            return frame.receiver

        if expr.literal is not None:
            return self._eval_literal(expr.literal)

        if expr.var is not None:
            return frame.get_var(expr.var.name)

        if expr.block is not None:
            return self._eval_block(expr.block, frame)

        if expr.send is not None:
            return self._eval_send(expr.send, frame)

        raise InterpreterError(ErrorCode.INT_STRUCTURE, "Empty or invalid <expr>")

    def _eval_literal(self, literal: Literal) -> Object:
        """Converts an XML literal to a SOLObject instance."""

        if literal.class_id == "class":
            target_class = self.symbol_table.get_class(literal.value)
            return self.heap.allocate(target_class, value="CLASS_REF")

        class_def = self.symbol_table.get_class(literal.class_id)
        match literal.class_id:
            case "Integer":
                return self.heap.allocate(class_def, int(literal.value))
            case "String":
                return self.heap.allocate(class_def, str(literal.value))
            case "Nil" | "True" | "False":
                return self.heap.allocate(class_def, None)
            case _:
                raise InterpreterError(
                    ErrorCode.INT_STRUCTURE, f"Unknown literal type: {literal.class_id}"
                )

    def _eval_block(self, block: Block, current_frame: Frame) -> Object:
        """Creates a closure."""
        block_class = self.symbol_table.get_class("Block")
        return self.heap.allocate(block_class, value=(block, current_frame))

    def _eval_send(self, send: Send, frame: Frame) -> Object:
        """Processes a message send (method call or attribute access)."""
        is_super = send.receiver.var is not None and send.receiver.var.name == "super"

        if is_super:
            receiver = frame.receiver
        else:
            receiver = self.execute_expr(send.receiver, frame)

        args = [self.execute_expr(arg.expr, frame) for arg in send.args]
        return self.dispatch_message(receiver, send.selector, args, frame, is_super)

    def execute_assign(self, assign: Assign, frame: Frame) -> Object:
        """Evaluates an expression and stores it in a variable."""
        result_obj = self.execute_expr(assign.expr, frame)
        frame.set_var(assign.target.name, result_obj)
        return result_obj

    def dispatch_message(
        self,
        receiver: Object,
        selector: str,
        args: list[Object],
        frame: Frame,
        is_super: bool = False,
    ) -> Object:
        """Decides how an object should respond to a message."""

        if is_super:
            start_class = frame.method_class.parent
        else:
            start_class = receiver.class_def

        method, owner_class = start_class.lookup_method_with_class(selector)

        if method is not None:
            if callable(method):
                return method(receiver, args, frame, self)
            return self.execute_user_method(receiver, method, args, frame, owner_class)

        if len(args) == 0:
            if selector in receiver.attributes:
                return receiver.attributes[selector]
            raise InterpreterError(
                ErrorCode.INT_DNU,
                f"Message '{selector}' not understood by {receiver.class_def.name}.",
            )

        if len(args) == 1:
            bezparam_selector = selector[:-1]
            if receiver.class_def.lookup_method(bezparam_selector) is not None:
                raise InterpreterError(
                    ErrorCode.INT_INST_ATTR,
                    f"Attribute name collision with method '{bezparam_selector}'.",
                )

            receiver.attributes[bezparam_selector] = args[0]
            return receiver

        raise InterpreterError(ErrorCode.INT_DNU, f"Message '{selector}' not understood.")

    def execute_user_method(
        self,
        receiver: Object,
        block_ast: Block,
        args: list[Object],
        parent_frame: Frame,
        owner_class: Any = None,
    ) -> Object:
        """Executes a user-defined method (block)."""
        new_frame = Frame(receiver=receiver, parent_frame=parent_frame)
        new_frame.method_class = owner_class

        for param, arg_obj in zip(block_ast.parameters, args, strict=False):
            new_frame.variables[param.name] = arg_obj

        last_result = self.heap.allocate(self.symbol_table.get_class("Nil"))

        for instr in block_ast.assigns: 
            if isinstance(instr, Assign):
                last_result = self.execute_assign(instr, new_frame)
            else:
                last_result = self.execute_expr(instr, new_frame)

        return last_result
