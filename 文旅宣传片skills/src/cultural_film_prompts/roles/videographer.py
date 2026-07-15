"""④ 视频师角色

整合 DirectorNotes + Screenplay + ShotPrompts，
逐镜头输出运动提示词 + 视频模型选型 VideoPrompts。
"""

from __future__ import annotations

import json
import logging

from ..config import Config
from ..llm import LLMClient, structured_call
from ..models import (
    DirectorNotes,
    Screenplay,
    ShotPrompts,
    VideoPrompts,
)

logger = logging.getLogger(__name__)

ROLE = "videographer"


def direct(
    shot_prompts: ShotPrompts,
    screenplay: Screenplay,
    director_notes: DirectorNotes,
    config: Config,
    client: LLMClient,
) -> VideoPrompts:
    """
    视频师产出运动提示词。

    Args:
        shot_prompts: 分镜师画面提示词
        screenplay: 编剧脚本
        director_notes: 导演手记
        config: 全局配置
        client: LLM 客户端
    """
    system_prompt = _load_system_prompt()
    role_cfg = config.llm.role_config(ROLE)

    # 序列化上游产物
    dn_json = director_notes.model_dump_json(indent=2)
    sp_json = screenplay.model_dump_json(indent=2)
    shp_json = shot_prompts.model_dump_json(indent=2)

    # 注入视频模型能力表（视频师选型依据）
    models_table = {}
    for k, v in config.video_models.items():
        models_table[k] = {
            "name": v.name,
            "api_hint": v.api_hint,
            "strengths": v.strengths,
            "weaknesses": v.weaknesses,
            "max_duration": v.max_duration,
            "cost_tier": v.cost_tier,
            "priority": v.priority,
        }
    models_table_json = json.dumps(models_table, ensure_ascii=False, indent=2)

    # 注入运动类型
    motion_types = config.motion_types or [
        "camera_movement",
        "character_action",
        "environment_atmosphere",
        "still_ken_burns",
    ]

    constraint_block = (
        f"【视频模型能力表】\n{models_table_json}\n\n"
        f"【可用运动类型 motion_type】\n{motion_types}\n\n"
        f"【全片节奏提示】\n"
        f"- 导演情绪曲线: {director_notes.emotional_arc}\n"
        f"- 三幕: 起={director_notes.three_act.setup[:30]}... / "
        f"转={director_notes.three_act.conflict[:30]}... / "
        f"合={director_notes.three_act.resolve[:30]}...\n\n"
        f"请为每个 shot 输出 VideoShotPrompt，包含：\n"
        f"1. motion_prompt（英文，含时长）\n"
        f"2. motion_type 分类\n"
        f"3. motion_params 运动参数\n"
        f"4. model_suggestion 选型（主推+备选+理由）\n"
        f"5. risk_notes 风险预判\n"
        f"6. fallback_motion 兜底\n"
        f"7. 若分镜师 image_prompt 里有动起来会很怪的元素，"
        f"用 image_prompt_revision + revised_image_prompt 修订\n"
    )

    user_prompt = (
        f"【导演手记】\n{dn_json}\n\n"
        f"【编剧脚本】\n{sp_json}\n\n"
        f"【分镜师画面提示词】\n{shp_json}\n\n"
        f"{constraint_block}"
    )

    response = structured_call(
        client=client,
        model=config.llm.model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        output_model=VideoPrompts,
        temperature=role_cfg.temperature,
        max_tokens=role_cfg.max_tokens,
        structured_mode=config.llm.structured_output,
    )

    if response.parsed is None:
        raise RuntimeError(
            f"视频师角色 LLM 输出解析失败，原始响应: {response.raw_text[:200]}..."
        )

    vp = response.parsed
    logger.info(
        f"视频提示词完成: 镜头数={len(vp.shots)}, "
        f"运动类型分布={_motion_type_dist(vp)}"
    )

    # 校验：每个 screenplay 的 shot_id 都有对应视频提示词
    sp_shot_ids = {s.shot_id for sc in screenplay.scenes for s in sc.shots}
    vp_shot_ids = {s.shot_id for s in vp.shots}
    missing = sp_shot_ids - vp_shot_ids
    if missing:
        logger.warning(f"视频师缺少这些镜头的运动提示词: {missing}")

    return vp


def _motion_type_dist(vp: VideoPrompts) -> dict[str, int]:
    dist: dict[str, int] = {}
    for s in vp.shots:
        dist[s.motion_type] = dist.get(s.motion_type, 0) + 1
    return dist


def _load_system_prompt() -> str:
    from pathlib import Path

    p = Path(__file__).parent.parent / "prompts" / "videographer.md"
    return p.read_text(encoding="utf-8")
