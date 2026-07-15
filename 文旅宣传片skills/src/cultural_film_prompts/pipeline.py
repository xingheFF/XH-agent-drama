"""流水线编排 —— 四角色串行 + 质检。

run_pipeline():
    用户输入
        ↓
    ① director.analyze  → DirectorNotes
        ↓
    ② screenwriter.write → Screenplay
        ↓
    ③ storyboard.draw   → ShotPrompts
        ↓
    ④ videographer.direct → VideoPrompts
        ↓
    quality_check + FinalPackage
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from .config import Config
from .llm import LLMClient
from .models import (
    DirectorNotes,
    FinalPackage,
    Screenplay,
    ShotPrompts,
    VideoPrompts,
)
from .roles import director, screenwriter, storyboard, videographer

logger = logging.getLogger(__name__)

PIPELINE_VERSION = "0.1.0"


def run_pipeline(
    user_input: str,
    config: Config,
    client: LLMClient | None = None,
) -> FinalPackage:
    """
    一键全流程：用户输入 → 成套提示词包。

    Args:
        user_input: 用户原始输入（剧本/灵感/混合）
        config: 全局配置
        client: LLM 客户端（可选；不传则新建）

    Returns:
        FinalPackage 包含四个角色的输出
    """
    owns_client = client is None
    if owns_client:
        client = LLMClient(
            base_url=config.llm.base_url,
            api_key=config.llm.api_key,
            timeout=config.llm.timeout,
        )

    try:
        # —— ① 导演 ——
        logger.info("阶段 1/4: 导演分析输入...")
        director_notes: DirectorNotes = director.analyze(
            user_input=user_input,
            config=config,
            client=client,
        )
        logger.info(
            f"✓ 导演完成: 主题={director_notes.theme!r}, "
            f"目标时长={director_notes.target_duration}s"
        )

        # —— ② 编剧 ——
        logger.info("阶段 2/4: 编剧创作脚本...")
        screenplay: Screenplay = screenwriter.write(
            director_notes=director_notes,
            config=config,
            client=client,
        )
        logger.info(
            f"✓ 编剧完成: 片名={screenplay.title!r}, "
            f"镜头数={sum(len(s.shots) for s in screenplay.scenes)}, "
            f"预估时长={screenplay.total_duration_estimate}s"
        )

        # —— ③ 分镜师 ——
        logger.info("阶段 3/4: 分镜师建锚点+写画面提示词...")
        shot_prompts: ShotPrompts = storyboard.draw(
            screenplay=screenplay,
            director_notes=director_notes,
            config=config,
            client=client,
        )
        logger.info(
            f"✓ 分镜完成: 锚点数={len(shot_prompts.visual_anchors)}, "
            f"镜头提示词数={len(shot_prompts.shots)}"
        )

        # —— ④ 视频师 ——
        logger.info("阶段 4/4: 视频师出运动提示词+选型...")
        video_prompts: VideoPrompts = videographer.direct(
            shot_prompts=shot_prompts,
            screenplay=screenplay,
            director_notes=director_notes,
            config=config,
            client=client,
        )
        logger.info(
            f"✓ 视频师完成: 运动提示词数={len(video_prompts.shots)}, "
            f"节奏建议={video_prompts.pacing_note[:40] if video_prompts.pacing_note else '—'}"
        )

        # —— 质检 ——
        logger.info("阶段 5/5: 质检...")
        quality_report = run_quality_check(
            director_notes=director_notes,
            screenplay=screenplay,
            shot_prompts=shot_prompts,
            video_prompts=video_prompts,
            config=config,
        )
        passed = quality_report.get("passed", False)
        issues = quality_report.get("issues", [])
        if passed:
            logger.info(f"✓ 质检通过")
        else:
            logger.warning(
                f"⚠ 质检发现 {len(issues)} 个问题: {issues}"
            )

        # —— 组装 FinalPackage ——
        package = FinalPackage(
            project_id=f"proj_{uuid.uuid4().hex[:8]}",
            created_at=datetime.now().isoformat(),
            director_notes=director_notes,
            screenplay=screenplay,
            shot_prompts=shot_prompts,
            video_prompts=video_prompts,
            quality_report=quality_report,
            pipeline_version=PIPELINE_VERSION,
            notes="",
        )

        logger.info(f"✓ 流水线完成: {package.project_id}")
        return package

    finally:
        if owns_client and client is not None:
            client.close()


# —— 单角色重跑（迭代回路）——


def rerun_role(
    role: str,
    upstream_data: dict,
    config: Config,
    client: LLMClient | None = None,
):
    """
    单角色重跑。

    Args:
        role: director / screenwriter / storyboard / videographer
        upstream_data: 该角色所需的上游产物（dict 形式）
        config: 全局配置
        client: LLM 客户端

    Returns:
        该角色的输出（对应 Pydantic 模型）
    """
    owns_client = client is None
    if owns_client:
        client = LLMClient(
            base_url=config.llm.base_url,
            api_key=config.llm.api_key,
            timeout=config.llm.timeout,
        )

    try:
        if role == "director":
            return director.analyze(
                user_input=upstream_data["user_input"],
                config=config,
                client=client,
            )
        elif role == "screenwriter":
            dn = DirectorNotes.model_validate(upstream_data["director_notes"])
            return screenwriter.write(
                director_notes=dn,
                config=config,
                client=client,
            )
        elif role == "storyboard":
            dn = DirectorNotes.model_validate(upstream_data["director_notes"])
            sp = Screenplay.model_validate(upstream_data["screenplay"])
            return storyboard.draw(
                screenplay=sp,
                director_notes=dn,
                config=config,
                client=client,
            )
        elif role == "videographer":
            dn = DirectorNotes.model_validate(upstream_data["director_notes"])
            sp = Screenplay.model_validate(upstream_data["screenplay"])
            shp = ShotPrompts.model_validate(upstream_data["shot_prompts"])
            return videographer.direct(
                shot_prompts=shp,
                screenplay=sp,
                director_notes=dn,
                config=config,
                client=client,
            )
        else:
            raise ValueError(
                f"未知角色 {role!r}，可选: director/screenwriter/storyboard/videographer"
            )
    finally:
        if owns_client and client is not None:
            client.close()


# —— 质检 ——


def run_quality_check(
    director_notes: DirectorNotes,
    screenplay: Screenplay,
    shot_prompts: ShotPrompts,
    video_prompts: VideoPrompts,
    config: Config,
) -> dict:
    """
    自动质检。

    检查项（由 config.quality_check 控制）：
    1. 总时长是否在目标 ±duration_tolerance 内
    2. 旁白字数 / 语速 是否匹配镜头时长
    3. 视觉锚点完整性（角色/场景是否都有锚点）
    4. 镜头数 ≥ min_shots
    5. 情绪曲线完整性（emotional_arc 节点 ≥ 3）

    Returns:
        {
            "passed": bool,
            "issues": list[str],
            "checks": {...}
        }
    """
    qc = config.quality_check
    issues: list[str] = []
    checks: dict[str, bool | float | str] = {}

    # —— 1. 时长检查 ——
    if qc.check_duration:
        target = director_notes.target_duration
        actual = sum(s.duration for sc in screenplay.scenes for s in sc.shots)
        tolerance = config.defaults.duration_tolerance
        diff_pct = abs(actual - target) / target

        checks["duration"] = {
            "target": target,
            "actual": actual,
            "diff_pct": round(diff_pct * 100, 1),
        }
        if diff_pct > tolerance:
            issues.append(
                f"时长偏差 {diff_pct*100:.1f}% 超过容差 {tolerance*100:.0f}% "
                f"(目标 {target}s, 实际 {actual}s)"
            )

    # —— 2. 旁白字数检查 ——
    if qc.check_voiceover_length:
        speed_presets = config.voiceover.speed_presets
        tolerance = qc.voiceover_tolerance
        bad_segments: list[str] = []

        for vo in screenplay.voiceover:
            shot = None
            for sc in screenplay.scenes:
                for s in sc.shots:
                    if s.shot_id == vo.shot_id:
                        shot = s
                        break
                if shot:
                    break

            if shot is None:
                continue

            expected_chars = shot.duration * speed_presets.get(vo.speed_preset, 3.5)
            actual_chars = len(vo.text)
            if expected_chars > 0:
                vo_diff = abs(actual_chars - expected_chars) / expected_chars
                if vo_diff > tolerance:
                    bad_segments.append(
                        f"{vo.shot_id}: 字数 {actual_chars} vs 预期 {expected_chars:.0f}"
                    )

        checks["voiceover_length"] = {
            "total_segments": len(screenplay.voiceover),
            "bad_segments_count": len(bad_segments),
        }
        if bad_segments:
            issues.append(
                f"旁白字数不匹配的镜头: {bad_segments[:3]}"
                f"{'...' if len(bad_segments) > 3 else ''}"
            )

    # —— 3. 视觉锚点完整性 ——
    if qc.check_anchors:
        char_anchors = [
            a for a in shot_prompts.visual_anchors if a.kind == "character"
        ]
        loc_anchors = [
            a for a in shot_prompts.visual_anchors if a.kind == "location"
        ]

        # 检查每个角色是否有锚点
        char_names_in_anchors = {a.ref_name for a in char_anchors}
        char_names_in_director = {c.name for c in director_notes.characters}
        missing_char_anchors = char_names_in_director - char_names_in_anchors

        checks["anchors"] = {
            "character_anchors": len(char_anchors),
            "location_anchors": len(loc_anchors),
            "missing_char_anchors": list(missing_char_anchors),
        }
        if (
            config.visual_anchors.enforce_character_anchors
            and missing_char_anchors
        ):
            issues.append(
                f"缺少角色锚点: {missing_char_anchors}"
            )

    # —— 4. 镜头数检查 ——
    if qc.check_shot_count:
        shot_count = sum(len(sc.shots) for sc in screenplay.scenes)
        checks["shot_count"] = shot_count
        if shot_count < qc.min_shots:
            issues.append(
                f"镜头数 {shot_count} 少于最小值 {qc.min_shots}"
            )

    # —— 5. 情绪曲线完整性 ——
    if qc.check_emotional_arc:
        arc = director_notes.emotional_arc
        checks["emotional_arc"] = {
            "nodes": len(arc),
            "arc": arc,
        }
        if len(arc) < 3:
            issues.append(
                f"情绪曲线节点数 {len(arc)} 少于最小值 3"
            )
        if arc and arc[0] == arc[-1]:
            issues.append(
                f"情绪曲线首尾相同 ({arc[0]})，缺乏变化"
            )

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "checks": checks,
    }
