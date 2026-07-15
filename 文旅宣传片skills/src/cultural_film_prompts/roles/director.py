"""① 导演角色

从用户输入提炼核心信息，输出 DirectorNotes。
"""

from __future__ import annotations

import logging
from typing import overload

from ..config import Config
from ..llm import LLMClient, structured_call
from ..models import DirectorNotes

logger = logging.getLogger(__name__)

ROLE = "director"


@overload
def analyze(user_input: str, config: Config, client: LLMClient) -> DirectorNotes: ...


def analyze(user_input: str, config: Config, client: LLMClient) -> DirectorNotes:
    """
    导演分析用户输入，提炼核心信息。

    Args:
        user_input: 用户原始输入（剧本/灵感/混合）
        config: 全局配置
        client: LLM 客户端
    """
    system_prompt = _load_system_prompt()
    role_cfg = config.llm.role_config(ROLE)

    user_prompt = (
        f"【用户原始输入】\n{user_input}\n\n"
        f"【默认约束】\n"
        f"- 目标时长: {config.defaults.target_duration}s\n"
        f"- 画幅: {config.defaults.aspect_ratio}\n"
        f"- 分辨率: {config.defaults.resolution}\n"
        f"- 帧率: {config.defaults.fps}fps\n"
        f"- 默认视觉风格: {config.defaults.visual_style}\n"
        f"- 默认基调: {config.defaults.tone}\n"
        f"- 提示词语言: {config.defaults.prompt_lang}\n"
        f"- 描述语言: {config.defaults.desc_lang}\n\n"
        f"请输出 DirectorNotes。"
    )

    response = structured_call(
        client=client,
        model=config.llm.model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        output_model=DirectorNotes,
        temperature=role_cfg.temperature,
        max_tokens=role_cfg.max_tokens,
        structured_mode=config.llm.structured_output,
    )

    if response.parsed is None:
        raise RuntimeError(
            f"导演角色 LLM 输出解析失败，原始响应: {response.raw_text[:200]}..."
        )

    logger.info(
        f"导演分析完成: 主题={response.parsed.theme!r}, "
        f"情绪曲线={response.parsed.emotional_arc}"
    )
    return response.parsed


def _load_system_prompt() -> str:
    """加载导演角色的 system prompt"""
    from pathlib import Path

    p = Path(__file__).parent.parent / "prompts" / "director.md"
    return p.read_text(encoding="utf-8")
