"""
This module contains the main logic of the interpreter.

IPP: You must definitely modify this file. Bend it to your will.

Author: Ondřej Ondryáš <iondryas@fit.vut.cz>
Author: Jiří Lach <xlachji00@stud.fit.vut.cz>
"""

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TextIO

from pydantic import ValidationError

from interpreter.environment import ClassDefinition, SymbolTable
from interpreter.error_codes import ErrorCode
from interpreter.exceptions import InterpreterError
from interpreter.executor import Executor
from interpreter.input_model import Program
from interpreter.memory import Frame, Heap

logger = logging.getLogger(__name__)


class Interpreter:
    """
    The main interpreter class, responsible for loading the source file and executing the program.
    """

    def __init__(self) -> None:
        self.current_program: Program | None = None

    def load_program(self, source_file_path: Path) -> None:
        """
        Reads the source SOL-XML file and stores it as the target program for this interpreter.
        """
        logger.info("Opening source file: %s", source_file_path)
        
        try:
            xml_content = source_file_path.read_bytes()
        except Exception as e:
            raise InterpreterError(
                error_code=ErrorCode.INT_OTHER, message=f"Could not read file: {e}"
            ) from e

        try:
            self.current_program = Program.from_xml(xml_content)
        except ValidationError as e:
            raise InterpreterError(
                error_code=ErrorCode.INT_STRUCTURE, message="Invalid SOL-XML structure or syntax"
            ) from e
        except Exception as e:
            raise InterpreterError(
                error_code=ErrorCode.INT_XML, message=f"XML Parse error: {e}"
            ) from e

    def execute(self, input_io: TextIO) -> None:
        """
        Executes the currently loaded program, using the provided input stream as standard input.
        """
        logger.info("Executing program")

        if not self.current_program:
            raise InterpreterError(ErrorCode.INT_STRUCTURE, "No program loaded")

        symbol_table = SymbolTable()
        heap = Heap()
        executor = Executor(symbol_table, heap)
        executor.input_io = input_io

        for class_node in self.current_program.classes:
            new_class = ClassDefinition(class_node.name)
            symbol_table.register_class(new_class)

        for class_node in self.current_program.classes:
            register_class = symbol_table.get_class(class_node.name)
            if class_node.parent:
                try:
                    register_class.parent = symbol_table.get_class(class_node.parent)
                except Exception:
                    raise InterpreterError(
                        ErrorCode.INT_OTHER, f"Parent class {class_node.parent} not found"
                    )

            for method_node in class_node.methods:
                register_class.add_method(method_node.selector, method_node.block)

        try:
            main_class = symbol_table.get_class("Main")
        except Exception:
            raise InterpreterError(ErrorCode.SEM_MAIN, "Main class not found")

        main_instance = heap.allocate(main_class)

        root_frame = Frame(receiver=main_instance, parent_frame=None)

        try:
            executor.dispatch_message(
                receiver=main_instance, selector="run", args=[], frame=root_frame
            )
        except InterpreterError as e:
            raise e
