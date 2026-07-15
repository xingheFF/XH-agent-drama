"""② 编剧角色

拿着 DirectorNotes，展开为可拍摄的脚本 + 镜头清单，输出 Screenplay。
"""

from __future__ import annotations

import logging

from ..config import Config
from ..llm import LLMClient, structured_call
from ..models import DirectorNotes, Screenplay

logger = logging.getLogger(__name__)

ROLE = "screenwriter"


def write(
    director_notes: DirectorNotes,
    config: Config,
    client: LLMClient,
) -> Screenplay:
    """
    编剧根据导演手记创作脚本。

    Args:
        director_notes: 导演手记
        config: 全局配置
        client: LLM 客户端
    """
    system_prompt = _load_system_prompt()
    role_cfg = config.llm.role_config(ROLE)

    # 把 DirectorNotes 序列化为 JSON 喂给 LLM
    dn_json = director_notes.model_dump_json(indent=2)

    # 注入分镜参数约束
    shot_constraints = (
        f"- 单镜头时长区间: {config.shot.min_duration}-{config.shot.max_duration}s\n"
        f"- 每场景镜头数区间: {config.shot.shots_per_scene_min}-"
        f"{config.shot.shots_per_scene_max}\n"
        f"- 景别分布参考: {config.shot.shot_type_weights}\n"
        f"- 旁白语速档位: {config.voiceover.speed_presets}\n"
        f"- 情绪-语速映射: {config.voiceover.emotion_speed_map}\n"
        f"- 时长容差: ±{config.defaults.duration_tolerance*100:.0f}%\n"
        f"- 可用转场: {config.transitions}\n"
    )

    user_prompt = (
        f"【导演手记 DirectorNotes】\n{dn_json}\n\n"
        f"【分镜约束】\n{shot_constraints}\n\n"
        f"请根据导演手记，创作完整 Screenplay。"
        f"注意：所有镜头 duration 之和应接近 {director_notes.target_duration}s。"
    )

    response = structured_call(
        client=client,
        model=config.llm.model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        output_model=Screenplay,
        temperature=role_cfg.temperature,
        max_tokens=role_cfg.max_tokens,
        structured_mode=config.llm.structured_output,
    )

    if response.parsed is None:
        raise RuntimeError(
            f"编剧角色 LLM 输出解析失败，原始响应: {response.raw_text[:200]}..."
        )

    sp = response.parsed
    logger.info(
        f"编剧创作完成: 片名={sp.title!r}, "
        f"场景数={len(sp.scenes)}, "
        f"镜头数={sum(len(s.shots) for s in sp.scenes)}, "
        f"总时长={sp.total_duration_estimate}s"
    )
    return sp


def _load_system_prompt() -> str:
    from pathlib import Path

    p = Path(__file__).parent.parent / "prompts" / "screenwriter.md"
    return p.read_text(encoding="utf-8")
