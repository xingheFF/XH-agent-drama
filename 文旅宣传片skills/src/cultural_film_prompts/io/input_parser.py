"""输入解析器。

识别用户输入类型：
- full_script:   完整剧本（字符多 + 含场景/分镜标记）
- inspiration:   灵感描述（字符少）
- asset_pack:    素材包（目录含图片/视频/音频）
- mixed:         混合（灵感 + 参考脚本）

返回归一化后的纯文本 + 元数据。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class InputType(str, Enum):
    FULL_SCRIPT = "full_script"
    INSPIRATION = "inspiration"
    ASSET_PACK = "asset_pack"
    MIXED = "mixed"
    UNKNOWN = "unknown"


@dataclass
class ParsedInput:
    raw_text: str
    input_type: InputType
    source_path: str | None = None  # 文件/目录路径
    asset_files: list[str] | None = None  # 若是素材包，列出素材文件
    char_count: int = 0


def parse_input(
    source: str | Path,
    full_script_min_chars: int = 500,
    full_script_markers: list[str] | None = None,
    inspiration_max_chars: int = 800,
    asset_extensions: list[str] | None = None,
) -> ParsedInput:
    """
    解析用户输入。

    Args:
        source: 文件路径 / 目录路径 / 纯文本字符串
        其余参数来自 config.input
    """

    if full_script_markers is None:
        full_script_markers = ["场景", "分镜", "FADE", "CUT", "内景", "外景", "INT.", "EXT."]
    if asset_extensions is None:
        asset_extensions = [".jpg", ".jpeg", ".png", ".mp4", ".mov", ".wav", ".mp3"]

    src = Path(source) if isinstance(source, str) and (
        Path(source).exists() or "/" in source or "\\" in source
    ) else None

    # —— 素材包（目录）——
    if src and src.is_dir():
        asset_files = [
            str(p)
            for p in src.rglob("*")
            if p.is_file() and p.suffix.lower() in asset_extensions
        ]
        # 也尝试读目录下的文本文件作为灵感
        text_files = list(src.glob("*.txt")) + list(src.glob("*.md"))
        raw_text = "\n\n".join(p.read_text(encoding="utf-8") for p in text_files) if text_files else ""
        return ParsedInput(
            raw_text=raw_text,
            input_type=InputType.ASSET_PACK,
            source_path=str(src),
            asset_files=asset_files,
            char_count=len(raw_text),
        )

    # —— 文件输入 ——
    if src and src.is_file():
        raw_text = src.read_text(encoding="utf-8")
        return _classify_text(raw_text, str(src))

    # —— 纯文本字符串 ——
    if isinstance(source, str):
        return _classify_text(source, None)

    return ParsedInput(raw_text="", input_type=InputType.UNKNOWN, char_count=0)


def _classify_text(text: str, source_path: str | None) -> ParsedInput:
    """根据字符数和标记词分类"""

    n = len(text)

    # 检测场景标记
    marker_hits = sum(1 for m in full_script_markers_global if m in text)

    # 完整剧本：字符多 + 有场景标记，或字符非常多
    if (n >= 500 and marker_hits >= 2) or n >= 1500:
        return ParsedInput(
            raw_text=text,
            input_type=InputType.FULL_SCRIPT,
            source_path=source_path,
            char_count=n,
        )

    # 灵感：字符少且无场景标记
    if n <= 800 and marker_hits == 0:
        return ParsedInput(
            raw_text=text,
            input_type=InputType.INSPIRATION,
            source_path=source_path,
            char_count=n,
        )

    # 混合：介于两者之间
    return ParsedInput(
        raw_text=text,
        input_type=InputType.MIXED,
        source_path=source_path,
        char_count=n,
    )


# 模块级常量（_classify_text 用），避免每次调用都重新构造
full_script_markers_global = [
    "场景", "分镜", "FADE", "CUT", "内景", "外景", "INT.", "EXT.",
]
