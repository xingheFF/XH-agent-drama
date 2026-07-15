"""io 层：输入解析 + 输出写入。"""

from .input_parser import InputType, ParsedInput, parse_input
from .output_writer import write_outputs

__all__ = [
    "InputType",
    "ParsedInput",
    "parse_input",
    "write_outputs",
]
