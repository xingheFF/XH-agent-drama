"""Pydantic 数据模型层。

四个角色的输出 + 最终合并包，全部在此定义。
所有字段都带描述，便于 JSON Schema 自动生成和文档化。
"""

from .director_notes import DirectorNotes
from .screenplay import Screenplay
from .shot_prompts import ShotPrompts
from .video_prompts import VideoPrompts
from .final_package import FinalPackage

__all__ = [
    "DirectorNotes",
    "Screenplay",
    "ShotPrompts",
    "VideoPrompts",
    "FinalPackage",
]
