"""③ 分镜师角色

拿着 DirectorNotes + Screenplay，建视觉锚点表，逐镜头输出画面提示词 ShotPrompts。
"""

from __future__ import annotations

import logging

from ..config import Config
from ..llm import LLMClient, structured_call
from ..models import DirectorNotes, Screenplay, ShotPrompts

logger = logging.getLogger(__name__)

ROLE = "storyboard"


def draw(
    screenplay: Screenplay,
    director_notes: DirectorNotes,
    config: Config,
    client: LLMClient,
) -> ShotPrompts:
    """
    分镜师产出画面提示词。

    Args:
        screenplay: 编剧脚本
        director_notes: 导演手记
        config: 全局配置
        client: LLM 客户端
    """
    system_prompt = _load_system_prompt()
    role_cfg = config.llm.role_config(ROLE)

    sp_json = screenplay.model_dump_json(indent=2)
    dn_json = director_notes.model_dump_json(indent=2)

    # 注入视觉锚点强制要求
    anchor_constraints = (
        f"- 强制角色锚点: {config.visual_anchors.enforce_character_anchors}\n"
        f"- 强制场景锚点: {config.visual_anchors.enforce_location_anchors}\n"
        f"- 一致性标签模板: {config.visual_anchors.consistency_tag_template}\n"
        f"- 负向一致性模板: {config.visual_anchors.negative_consistency_template}\n"
    )

    # 注入关键意象要求
    motif_constraint = (
        f"- 导演要求的关键意象: {director_notes.key_motifs}\n"
        f"- 每个意象必须出现在至少一个镜头的 image_prompt 里\n"
    )

    user_prompt = (
        f"【导演手记 DirectorNotes】\n{dn_json}\n\n"
        f"【编剧脚本 Screenplay】\n{sp_json}\n\n"
        f"【视觉锚点约束】\n{anchor_constraints}\n\n"
        f"【关键意象约束】\n{motif_constraint}\n\n"
        f"请先建 visual_anchors（角色/场景/道具锚点），"
        f"再为每个 shot 写 ShotPrompt。"
        f"image_prompt 和 negative_prompt 用英文。"
    )

    response = structured_call(
        client=client,
        model=config.llm.model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        output_model=ShotPrompts,
        temperature=role_cfg.temperature,
        max_tokens=role_cfg.max_tokens,
        structured_mode=config.llm.structured_output,
    )

    if response.parsed is None:
        raise RuntimeError(
            f"分镜师角色 LLM 输出解析失败，原始响应: {response.raw_text[:200]}..."
        )

    shp = response.parsed
    logger.info(
        f"分镜完成: 锚点数={len(shp.visual_anchors)}, "
        f"镜头提示词数={len(shp.shots)}"
    )

    # 校验：每个 screenplay 的 shot_id 在 shot_prompts 里都有对应
    sp_shot_ids = {s.shot_id for sc in screenplay.scenes for s in sc.shots}
    shp_shot_ids = {s.shot_id for s in shp.shots}
    missing = sp_shot_ids - shp_shot_ids
    extra = shp_shot_ids - sp_shot_ids
    if missing:
        logger.warning(f"分镜师缺少这些镜头的提示词: {missing}")
    if extra:
        logger.warning(f"分镜师多了这些镜头（不在编剧脚本里）: {extra}")

    return shp


def _load_system_prompt() -> str:
    from pathlib import Path

    p = Path(__file__).parent.parent / "prompts" / "storyboard.md"
    return p.read_text(encoding="utf-8")
