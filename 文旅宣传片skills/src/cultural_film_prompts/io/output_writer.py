"""输出写入器。

把四个角色的产物 + FinalPackage 写成多种格式：
- JSON（各阶段独立 + 全量合并）
- Markdown（人类可读）
- TXT（只抽提示词，便于批量粘贴）
- CSV（镜头表）
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from ..config import Config
from ..models import (
    DirectorNotes,
    FinalPackage,
    Screenplay,
    ShotPrompts,
    VideoPrompts,
)

logger = logging.getLogger(__name__)


def write_outputs(
    package: FinalPackage,
    config: Config,
    base_dir: str | Path | None = None,
) -> dict[str, str]:
    """
    把 FinalPackage 写成多种格式。

    Returns:
        写入文件路径字典 {文件类型: 路径}
    """

    out_dir = Path(base_dir) if base_dir else Path(config.output.dir)
    proj_dir = out_dir / package.project_id
    proj_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, str] = {}

    # —— 各阶段独立 JSON ——
    if config.output.write_stage_json:
        stages = {
            "00_director_notes": package.director_notes,
            "01_screenplay": package.screenplay,
            "02_shot_prompts": package.shot_prompts,
            "03_video_prompts": package.video_prompts,
        }
        for name, model in stages.items():
            p = proj_dir / f"{name}.json"
            p.write_text(
                json.dumps(model.model_dump(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            written[name] = str(p)

    # —— 全量合并 JSON ——
    if config.output.write_final_package:
        p = proj_dir / "final_package.json"
        p.write_text(
            json.dumps(package.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        written["final_package"] = str(p)

    # —— 人类可读 Markdown ——
    if config.output.write_markdown:
        p = proj_dir / "human_readable.md"
        p.write_text(_render_markdown(package), encoding="utf-8")
        written["markdown"] = str(p)

    # —— 只抽提示词 TXT ——
    if config.output.write_prompts_only:
        p = proj_dir / "prompts_only.txt"
        p.write_text(_render_prompts_only(package), encoding="utf-8")
        written["prompts_only"] = str(p)

    # —— 镜头表 CSV ——
    if config.output.write_shot_table:
        p = proj_dir / "shot_table.csv"
        _write_shot_table(package, p)
        written["shot_table"] = str(p)

    logger.info(f"输出已写入 {proj_dir}")
    return written


# —— Markdown 渲染 ——


def _render_markdown(pkg: FinalPackage) -> str:
    dn = pkg.director_notes
    sp = pkg.screenplay
    shp = pkg.shot_prompts
    vp = pkg.video_prompts

    lines: list[str] = []

    # 标题
    lines.append(f"# 《{sp.title}》— 文旅剧情宣传片提示词包")
    lines.append("")
    lines.append(f"> {sp.logline}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 导演手记
    lines.append("## 导演手记")
    lines.append("")
    lines.append(f"- **主题**: {dn.theme}")
    lines.append(f"- **次级主题**: {', '.join(dn.sub_themes) or '—'}")
    lines.append(f"- **叙事类型**: {dn.story_type}")
    lines.append(f"- **三幕骨架**:")
    lines.append(f"  - 起: {dn.three_act.setup}")
    lines.append(f"  - 承/转: {dn.three_act.conflict}")
    lines.append(f"  - 合: {dn.three_act.resolve}")
    lines.append(f"- **情绪曲线**: {' → '.join(dn.emotional_arc) or '—'}")
    lines.append(f"- **取景地**: {dn.location}")
    lines.append(f"- **文化标签**: {', '.join(dn.cultural_tags) or '—'}")
    lines.append(f"- **文旅卖点**: {', '.join(dn.tourism_selling) or '—'}")
    lines.append(
        f"- **创作约束**: 时长 {dn.target_duration}s | "
        f"画幅 {dn.aspect_ratio} | 分辨率 {dn.resolution} | "
        f"帧率 {dn.fps}fps"
    )
    lines.append(f"- **视觉风格**: {dn.visual_style}")
    lines.append(f"- **基调**: {dn.tone}")
    lines.append("")

    # 人物
    if dn.characters:
        lines.append("### 人物")
        lines.append("")
        lines.append("| 名字 | 定位 | 年龄 | 外貌 | 性格 | 弧线 |")
        lines.append("|---|---|---|---|---|---|")
        for c in dn.characters:
            lines.append(
                f"| {c.name} | {c.role} | {c.age} | "
                f"{c.appearance} | {c.personality} | {c.arc} |"
            )
        lines.append("")

    # 关键意象
    if dn.key_motifs:
        lines.append(f"### 关键意象\n")
        lines.append(", ".join(dn.key_motifs))
        lines.append("")

    if dn.director_note:
        lines.append(f"### 导演备注\n")
        lines.append(dn.director_note)
        lines.append("")

    # 视觉一致性锚点
    lines.append("## 视觉一致性锚点")
    lines.append("")
    lines.append("| 锚点ID | 类型 | 名称 | 参考描述(EN) | 一致性标签 |")
    lines.append("|---|---|---|---|---|")
    for a in shp.visual_anchors:
        kind_cn = {"character": "角色", "location": "场景", "prop": "道具"}.get(
            a.kind, a.kind
        )
        # 截断长描述
        desc_short = a.ref_desc[:80] + "..." if len(a.ref_desc) > 80 else a.ref_desc
        lines.append(
            f"| {a.anchor_id} | {kind_cn} | {a.ref_name} | "
            f"{desc_short} | {a.consistency_tags} |"
        )
    lines.append("")

    # 逐镜头
    lines.append("## 分镜提示词")
    lines.append("")

    # 索引镜头
    shots_by_id: dict[str, dict] = {}
    for sc in sp.scenes:
        for s in sc.shots:
            shots_by_id[s.shot_id] = {
                "screenplay": s,
                "scene": sc,
            }
    shot_prompt_by_id = {s.shot_id: s for s in shp.shots}
    video_prompt_by_id = {s.shot_id: s for s in vp.shots}
    vo_by_shot = {v.shot_id: v for v in sp.voiceover}

    for sc in sp.scenes:
        lines.append(f"### 场景 {sc.scene_id}：{sc.location}")
        lines.append(f"- 时间: {sc.time or '—'}")
        lines.append(f"- 情绪: {sc.mood}")
        lines.append(f"- 事件: {sc.action}")
        lines.append(f"- 功能: {sc.purpose}")
        lines.append("")

        for s in sc.shots:
            sid = s.shot_id
            shp_shot = shot_prompt_by_id.get(sid)
            vp_shot = video_prompt_by_id.get(sid)
            vo = vo_by_shot.get(sid)

            lines.append(f"#### {sid} | {s.shot_type} | {s.camera_move} | {s.duration}s")
            lines.append(f"- **画面描述**: {s.desc}")
            lines.append(f"- **叙事功能**: {s.purpose}")
            lines.append(f"- **转场**: {s.transition_out}")
            if s.characters_in_shot:
                lines.append(f"- **人物**: {', '.join(s.characters_in_shot)}")
            lines.append("")

            # 画面提示词
            if shp_shot:
                lines.append("**画面提示词 (image_prompt)**:")
                lines.append("```")
                lines.append(shp_shot.image_prompt)
                lines.append("```")
                lines.append("")
                lines.append("**负向提示词 (negative_prompt)**:")
                lines.append("```")
                lines.append(shp_shot.negative_prompt)
                lines.append("```")
                lines.append("")
                cp = shp_shot.camera_params
                lines.append(
                    f"- 镜头参数: {cp.shot_size} | {cp.lens} | "
                    f"{cp.angle} | {cp.lighting} ({cp.lighting_direction}) | "
                    f"景深 {cp.depth_of_field}"
                )
                if cp.film_stock_hint:
                    lines.append(f"- 质感: {cp.film_stock_hint}")
                lines.append(f"- 构图: {shp_shot.composition}")
                if shp_shot.anchors_used:
                    lines.append(f"- 锚点: {', '.join(shp_shot.anchors_used)}")
                if shp_shot.storyboard_note:
                    lines.append(f"- 分镜师备注: {shp_shot.storyboard_note}")
                lines.append("")

            # 视频提示词
            if vp_shot:
                lines.append("**视频提示词 (motion_prompt)**:")
                lines.append("```")
                lines.append(vp_shot.motion_prompt)
                lines.append("```")
                lines.append("")
                lines.append(
                    f"- 运动类型: `{vp_shot.motion_type}` | "
                    f"兜底: `{vp_shot.fallback_motion}`"
                )
                mp = vp_shot.motion_params
                lines.append(
                    f"- 运动参数: camera={mp.camera_move}({mp.camera_speed}) | "
                    f"subject={mp.subject_motion} | env={','.join(mp.environmental_motion) or 'none'}"
                )
                ms = vp_shot.model_suggestion
                lines.append(
                    f"- 模型选型: **{ms.primary}** ({ms.reason}) | "
                    f"备选: {ms.fallback} ({ms.fallback_reason})"
                )
                if vp_shot.risk_notes:
                    lines.append(f"- 风险: {vp_shot.risk_notes}")
                if vp_shot.image_prompt_revision:
                    lines.append(f"- **画面修订建议**: {vp_shot.image_prompt_revision}")
                    if vp_shot.revised_image_prompt:
                        lines.append("  修订后:")
                        lines.append("  ```")
                        lines.append(vp_shot.revised_image_prompt)
                        lines.append("  ```")
                lines.append("")

            # 旁白
            if vo:
                lines.append(f"- **旁白** ({vo.emotion}, {vo.speed_preset}): ")
                lines.append(f"  > {vo.text}")
                lines.append("")

    # 字幕
    if sp.subtitles:
        lines.append("## 字幕")
        lines.append("")
        lines.append("| 时机 | 关联镜头 | 文本 | 样式 |")
        lines.append("|---|---|---|---|")
        for sub in sp.subtitles:
            lines.append(
                f"| {sub.timing} | {sub.shot_id or '—'} | "
                f"{sub.text} | {sub.style_hint or '—'} |"
            )
        lines.append("")

    # 全片节奏建议
    if vp.pacing_note:
        lines.append("## 全片节奏建议")
        lines.append("")
        lines.append(vp.pacing_note)
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        f"*由 文旅宣传片提示词工坊 v{pkg.pipeline_version} 生成 | "
        f"项目 {pkg.project_id} | 创建于 {pkg.created_at}*"
    )

    return "\n".join(lines)


# —— Prompts-only TXT ——


def _render_prompts_only(pkg: FinalPackage) -> str:
    """只抽 image_prompt 和 motion_prompt，便于批量粘贴到生成工具"""

    lines: list[str] = []
    shp_by_id = {s.shot_id: s for s in pkg.shot_prompts.shots}
    vp_by_id = {s.shot_id: s for s in pkg.video_prompts.shots}

    for sc in pkg.screenplay.scenes:
        for s in sc.shots:
            sid = s.shot_id
            lines.append(f"===== {sid} =====")
            lines.append(f"[DURATION] {s.duration}s")
            lines.append(f"[SHOT_TYPE] {s.shot_type}")
            lines.append(f"[CAMERA_MOVE] {s.camera_move}")

            shp_shot = shp_by_id.get(sid)
            if shp_shot:
                lines.append("[IMAGE_PROMPT]")
                lines.append(shp_shot.image_prompt)
                lines.append("[NEGATIVE_PROMPT]")
                lines.append(shp_shot.negative_prompt)

            vp_shot = vp_by_id.get(sid)
            if vp_shot:
                lines.append("[MOTION_PROMPT]")
                lines.append(vp_shot.motion_prompt)
                lines.append("[MOTION_TYPE]")
                lines.append(vp_shot.motion_type)
                ms = vp_shot.model_suggestion
                lines.append(f"[MODEL] {ms.primary} (fallback: {ms.fallback})")
                lines.append("[FALLBACK_MOTION]")
                lines.append(vp_shot.fallback_motion)

            lines.append("")

    return "\n".join(lines)


# —— Shot table CSV ——


def _write_shot_table(pkg: FinalPackage, path: Path) -> None:
    shp_by_id = {s.shot_id: s for s in pkg.shot_prompts.shots}
    vp_by_id = {s.shot_id: s for s in pkg.video_prompts.shots}
    vo_by_id = {v.shot_id: v for v in pkg.screenplay.voiceover}

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "shot_id", "scene_id", "shot_type", "camera_move",
            "duration", "desc", "purpose", "transition_out",
            "characters", "image_prompt", "negative_prompt",
            "motion_type", "motion_prompt", "model_primary",
            "model_fallback", "voiceover_text", "voiceover_emotion",
        ])
        for sc in pkg.screenplay.scenes:
            for s in sc.shots:
                sid = s.shot_id
                shp_shot = shp_by_id.get(sid)
                vp_shot = vp_by_id.get(sid)
                vo = vo_by_id.get(sid)
                w.writerow([
                    sid,
                    s.scene_id,
                    s.shot_type,
                    s.camera_move,
                    s.duration,
                    s.desc,
                    s.purpose,
                    s.transition_out,
                    "|".join(s.characters_in_shot),
                    shp_shot.image_prompt if shp_shot else "",
                    shp_shot.negative_prompt if shp_shot else "",
                    vp_shot.motion_type if vp_shot else "",
                    vp_shot.motion_prompt if vp_shot else "",
                    vp_shot.model_suggestion.primary if vp_shot else "",
                    vp_shot.model_suggestion.fallback if vp_shot else "",
                    vo.text if vo else "",
                    vo.emotion if vo else "",
                ])
