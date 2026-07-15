"""
Skill: cultural-film-zh
文旅剧情宣传片提示词工坊 —— 剧本/灵感到成套影视级提示词一键生成。

四角色串行流水线：
  ① 导演 → 从输入提炼主题/情绪/文旅要素/创作约束
  ② 编剧 → 把重点信息展开为脚本+分镜清单
  ③ 分镜师 → 建视觉锚点，逐镜头出画面提示词
  ④ 视频师 → 整合上下文，出运动提示词+模型选型
  ⑤ 质检 → 时长/旁白/锚点/镜头数/情绪曲线自动检查

基于 文旅宣传片skills/src/cultural_film_prompts 实现。
原项目使用同步 httpx + Pydantic function_calling，本技能改用项目自身的 llm_json 异步调用。
"""
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.agents.llm_utils import llm_json
from app.skills.base import BaseSkill, SkillInfo, SkillOutput, SkillParam

logger = logging.getLogger(__name__)

# ─── 参考文件加载 ────────────────────────────────────────
_REF_DIR = Path(__file__).resolve().parent.parent / "data" / "prompts" / "cultural_film"


def _load_prompt(filename: str) -> str:
    """加载角色 system prompt 文件。"""
    filepath = _REF_DIR / filename
    try:
        return filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("提示词文件不存在: %s", filepath)
        return ""


# ─── 参数选项 ────────────────────────────────────────────
ASPECT_OPTIONS = ["9:16竖屏", "16:9横屏", "1:1方形"]

STYLE_PRESETS = [
    "胶片质感,暖黄调,逆光,电影感",
    "清新明亮,自然光,日系治愈",
    "暗调低饱和,冷色,悬疑氛围",
    "高饱和浓郁,民族色彩,艳丽",
    "黑白水墨,留白,东方意境",
    "赛博朋克,霓虹,未来感",
]

DURATION_OPTIONS = ["60秒", "90秒", "120秒", "180秒"]

# ─── 视频模型能力表（内置，替代原 config.yaml）──────────────
VIDEO_MODELS = {
    "kling_v1_5": {
        "name": "Kling v1.5 (即梦/可灵)",
        "strengths": ["camera_movement", "environment_atmosphere", "long_take"],
        "weaknesses": ["复杂多体运动", "手指细节"],
        "max_duration": 10,
        "cost_tier": 2,
        "priority": 1,
    },
    "runway_gen3": {
        "name": "Runway Gen-3 Alpha",
        "strengths": ["character_action", "stylized", "portrait_motion"],
        "weaknesses": ["长镜头运镜稳定性"],
        "max_duration": 10,
        "cost_tier": 3,
        "priority": 2,
    },
    "pika_v1": {
        "name": "Pika v1.0",
        "strengths": ["stylized", "short_loop", "特效转场"],
        "weaknesses": ["写实人物", "长时长"],
        "max_duration": 3,
        "cost_tier": 1,
        "priority": 3,
    },
    "svd_v1_1": {
        "name": "Stable Video Diffusion 1.1",
        "strengths": ["environment_atmosphere", "still_ken_burns"],
        "weaknesses": ["人物动作", "无明确镜头控制"],
        "max_duration": 4,
        "cost_tier": 0,
        "priority": 4,
    },
    "seedance_2": {
        "name": "Seedance 2.0 (即梦)",
        "strengths": ["camera_movement", "character_action", "environment_atmosphere", "multi_shot", "native_audio"],
        "weaknesses": ["写实真人脸部"],
        "max_duration": 15,
        "cost_tier": 2,
        "priority": 0,
    },
}


class CulturalFilmSkill(BaseSkill):
    info = SkillInfo(
        skill_id="cultural-film-zh",
        skill_name="文旅宣传片提示词工坊",
        tags=["文旅", "宣传片", "提示词", "分镜", "导演", "编剧", "视频生成", "Seedance"],
        supported_outputs=[
            "导演手记", "编剧脚本", "分镜画面提示词",
            "视频运动提示词", "模型选型建议", "质检报告",
        ],
        version="1.0.0",
        category="视频制作类",
        params=[
            SkillParam(
                "内容描述", "text", required=True,
                description="输入你的剧本、灵感或文旅主题描述（如：皖南古村落的乡愁故事）",
            ),
            SkillParam(
                "目标时长", "select", options=DURATION_OPTIONS, default="90秒",
                description="宣传片目标总时长",
            ),
            SkillParam(
                "画幅比例", "select", options=ASPECT_OPTIONS, default="9:16竖屏",
                description="输出画幅比例，竖屏适合抖音/视频号，横屏适合宣传片",
            ),
            SkillParam(
                "视觉风格", "select", options=STYLE_PRESETS, default="胶片质感,暖黄调,逆光,电影感",
                description="整体视觉风格基调",
            ),
            SkillParam(
                "全片基调", "text", default="克制、留白、诗意",
                description="全片情绪基调，2-4个词，如'温暖、治愈、明亮'",
            ),
        ],
    )

    async def run(
        self,
        user_input: str,
        params: Optional[Dict[str, Any]] = None,
        global_params: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> SkillOutput:
        merged = self.merge_params(params)

        # 解析参数
        duration_str = str(merged.get("目标时长", "90秒"))
        target_duration = int(duration_str.replace("秒", ""))
        aspect_str = str(merged.get("画幅比例", "9:16竖屏"))
        aspect_ratio = aspect_str.split("竖")[0].split("横")[0].split("方")[0] if any(
            x in aspect_str for x in ["竖", "横", "方"]
        ) else "9:16"
        visual_style = str(merged.get("视觉风格", "胶片质感,暖黄调,逆光,电影感"))
        tone = str(merged.get("全片基调", "克制、留白、诗意"))

        # 分辨率映射
        resolution_map = {"9:16": "1080x1920", "16:9": "1920x1080", "1:1": "1080x1080"}
        resolution = resolution_map.get(aspect_ratio, "1080x1920")

        try:
            # ── ① 导演 ──
            director_notes = await self._run_director(
                user_input, target_duration, aspect_ratio, resolution,
                visual_style, tone,
            )

            if director_notes.get("_is_fallback"):
                return SkillOutput(
                    skill_id=self.info.skill_id,
                    status="failed",
                    data=director_notes,
                    error="导演角色 LLM 调用失败",
                )

            # ── ② 编剧 ──
            screenplay = await self._run_screenwriter(
                director_notes, target_duration, aspect_ratio,
            )

            if screenplay.get("_is_fallback"):
                return SkillOutput(
                    skill_id=self.info.skill_id,
                    status="failed",
                    data=screenplay,
                    error="编剧角色 LLM 调用失败",
                )

            # ── ③ 分镜师 ──
            shot_prompts = await self._run_storyboard(
                director_notes, screenplay, visual_style,
            )

            if shot_prompts.get("_is_fallback"):
                return SkillOutput(
                    skill_id=self.info.skill_id,
                    status="failed",
                    data=shot_prompts,
                    error="分镜师角色 LLM 调用失败",
                )

            # ── ④ 视频师 ──
            video_prompts = await self._run_videographer(
                director_notes, screenplay, shot_prompts,
            )

            if video_prompts.get("_is_fallback"):
                return SkillOutput(
                    skill_id=self.info.skill_id,
                    status="failed",
                    data=video_prompts,
                    error="视频师角色 LLM 调用失败",
                )

            # ── ⑤ 质检 ──
            quality_report = self._quality_check(
                director_notes, screenplay, shot_prompts, video_prompts,
                target_duration,
            )

            # ── 组装最终包 ──
            project_id = f"film_{uuid.uuid4().hex[:8]}"
            result = {
                "skill_id": self.info.skill_id,
                "skill_name": self.info.skill_name,
                "project_id": project_id,
                "created_at": datetime.now().isoformat(),
                "director_notes": director_notes,
                "screenplay": screenplay,
                "shot_prompts": shot_prompts,
                "video_prompts": video_prompts,
                "quality_report": quality_report,
                "pipeline_version": "1.0.0",
                "full_markdown": "",
            }

            result["full_markdown"] = self._build_full_markdown(result)

            return SkillOutput(
                skill_id=self.info.skill_id,
                status="success",
                data=result,
            )

        except Exception as e:
            logger.exception("[cultural-film] 流水线执行失败")
            return SkillOutput(
                skill_id=self.info.skill_id,
                status="failed",
                data={"_error": str(e)},
                error=str(e),
            )

    # ──────────────────────────────────────────────────────
    #  ① 导演
    # ──────────────────────────────────────────────────────
    async def _run_director(
        self,
        user_input: str,
        target_duration: int,
        aspect_ratio: str,
        resolution: str,
        visual_style: str,
        tone: str,
    ) -> Dict[str, Any]:
        system_prompt = _load_prompt("director.md")

        user_content = f"""\
【用户原始输入】
{user_input}

【默认约束】
- 目标时长: {target_duration}s
- 画幅: {aspect_ratio}
- 分辨率: {resolution}
- 帧率: 30fps
- 默认视觉风格: {visual_style}
- 默认基调: {tone}
- 提示词语言: en（画面/视频提示词用英文）
- 描述语言: zh-CN（给用户看的描述用中文）

请输出 DirectorNotes JSON，包含以下字段：
- theme: 一句话主题
- sub_themes: 次级主题列表
- story_type: 叙事类型
- three_act: {{setup, conflict, resolve}} 三幕结构
- emotional_arc: 情绪曲线节点列表
- location: 主取景地
- cultural_tags: 文化标签列表
- tourism_selling: 文旅卖点列表
- target_duration: {target_duration}
- aspect_ratio: "{aspect_ratio}"
- resolution: "{resolution}"
- fps: 30
- visual_style: "{visual_style}"
- tone: "{tone}"
- characters: [{{name, role, age, appearance, personality, arc}}]
- key_motifs: 关键意象列表
- director_note: 导演给下游的特别叮嘱

只输出 JSON，不要输出任何其他文字。
"""
        return await llm_json(
            system_prompt,
            user_content,
            model=self._llm_model,
            max_tokens=4096,
            temperature=0.7,
            fallback={
                "theme": "",
                "sub_themes": [],
                "story_type": "",
                "three_act": {"setup": "", "conflict": "", "resolve": ""},
                "emotional_arc": [],
                "location": "",
                "cultural_tags": [],
                "tourism_selling": [],
                "target_duration": target_duration,
                "aspect_ratio": aspect_ratio,
                "visual_style": visual_style,
                "tone": tone,
                "characters": [],
                "key_motifs": [],
                "director_note": "",
                "_error": "导演角色 LLM 调用失败",
            },
        )

    # ──────────────────────────────────────────────────────
    #  ② 编剧
    # ──────────────────────────────────────────────────────
    async def _run_screenwriter(
        self,
        director_notes: Dict[str, Any],
        target_duration: int,
        aspect_ratio: str,
    ) -> Dict[str, Any]:
        system_prompt = _load_prompt("screenwriter.md")
        dn_json = json.dumps(director_notes, ensure_ascii=False, indent=2)

        user_content = f"""\
【导演手记 DirectorNotes】
{dn_json}

【分镜约束】
- 单镜头时长区间: 2-6s
- 每场景镜头数区间: 2-5
- 旁白语速档位: slow=3.0字/秒, normal=3.5字/秒, fast=4.5字/秒
- 时长容差: ±10%
- 可用转场: cut, crossfade, wipe, dissolve, whip_pan, match_cut

请根据导演手记，创作完整 Screenplay JSON，包含以下字段：
- title: 片名（1-4字）
- logline: 一句话故事梗概
- genre: 类型
- total_duration_estimate: 预估总时长（秒）
- scenes: [{{scene_id, location, time, mood, action, purpose, shots: [{{shot_id, scene_id, shot_type, camera_move, duration, desc, purpose, transition_out, characters_in_shot, location_in_shot}}]}}]
- voiceover: [{{shot_id, text, emotion, speed_preset}}]
- subtitles: [{{timing, shot_id, text, style_hint}}]
- screenwriter_note: 编剧备注

注意：所有镜头 duration 之和应接近 {target_duration}s。
shot_id 格式为 {{场景号}}-{{镜头序号}}，如 S1-01。

只输出 JSON，不要输出任何其他文字。
"""
        return await llm_json(
            system_prompt,
            user_content,
            model=self._llm_model,
            max_tokens=8192,
            temperature=0.85,
            fallback={
                "title": "",
                "logline": "",
                "genre": "文旅剧情短片",
                "total_duration_estimate": 0,
                "scenes": [],
                "voiceover": [],
                "subtitles": [],
                "screenwriter_note": "",
                "_error": "编剧角色 LLM 调用失败",
            },
        )

    # ──────────────────────────────────────────────────────
    #  ③ 分镜师
    # ──────────────────────────────────────────────────────
    async def _run_storyboard(
        self,
        director_notes: Dict[str, Any],
        screenplay: Dict[str, Any],
        visual_style: str,
    ) -> Dict[str, Any]:
        system_prompt = _load_prompt("storyboard.md")
        dn_json = json.dumps(director_notes, ensure_ascii=False, indent=2)
        sp_json = json.dumps(screenplay, ensure_ascii=False, indent=2)

        user_content = f"""\
【导演手记 DirectorNotes】
{dn_json}

【编剧脚本 Screenplay】
{sp_json}

【视觉锚点约束】
- 强制角色锚点: true
- 强制场景锚点: true
- 一致性标签模板: "same {{kind}}, consistent {{feature}}, {{anchor_ref}}"
- 负向一致性模板: "inconsistent {{feature}}, different {{kind}}, style drift"

【关键意象约束】
- 导演要求的关键意象: {director_notes.get('key_motifs', [])}
- 每个意象必须出现在至少一个镜头的 image_prompt 里

请先建 visual_anchors（角色/场景/道具锚点），再为每个 shot 写 ShotPrompt。
image_prompt 和 negative_prompt 用英文。

输出 ShotPrompts JSON，包含以下字段：
- visual_anchors: [{{anchor_id, kind, ref_name, ref_desc, consistency_tags, negative_consistency}}]
- shots: [{{shot_id, desc_cn, image_prompt, negative_prompt, camera_params: {{shot_size, lens, angle, lighting, lighting_direction, color_grade, depth_of_field, film_stock_hint}}, composition, composition_rules, anchors_used, reference_images, storyboard_note}}]
- global_style_suffix: 全局风格后缀词
- global_negative_suffix: 全局负向后缀词

只输出 JSON，不要输出任何其他文字。
"""
        return await llm_json(
            system_prompt,
            user_content,
            model=self._llm_model,
            max_tokens=8192,
            temperature=0.6,
            fallback={
                "visual_anchors": [],
                "shots": [],
                "global_style_suffix": "cinematic, film grain, highly detailed",
                "global_negative_suffix": "lowres, blurry, deformed, ugly, text, watermark",
                "_error": "分镜师角色 LLM 调用失败",
            },
        )

    # ──────────────────────────────────────────────────────
    #  ④ 视频师
    # ──────────────────────────────────────────────────────
    async def _run_videographer(
        self,
        director_notes: Dict[str, Any],
        screenplay: Dict[str, Any],
        shot_prompts: Dict[str, Any],
    ) -> Dict[str, Any]:
        system_prompt = _load_prompt("videographer.md")
        dn_json = json.dumps(director_notes, ensure_ascii=False, indent=2)
        sp_json = json.dumps(screenplay, ensure_ascii=False, indent=2)
        shp_json = json.dumps(shot_prompts, ensure_ascii=False, indent=2)

        models_table = json.dumps(VIDEO_MODELS, ensure_ascii=False, indent=2)
        motion_types = ["camera_movement", "character_action", "environment_atmosphere", "still_ken_burns"]

        user_content = f"""\
【导演手记】
{dn_json}

【编剧脚本】
{sp_json}

【分镜师画面提示词】
{shp_json}

【视频模型能力表】
{models_table}

【可用运动类型 motion_type】
{motion_types}

【全片节奏提示】
- 导演情绪曲线: {director_notes.get('emotional_arc', [])}

请为每个 shot 输出 VideoShotPrompt，包含：
1. motion_prompt（英文，含时长）
2. motion_type 分类
3. motion_params 运动参数
4. model_suggestion 选型（主推+备选+理由）
5. risk_notes 风险预判
6. fallback_motion 兜底
7. 若分镜师 image_prompt 里有动起来会很怪的元素，用 image_prompt_revision + revised_image_prompt 修订

输出 VideoPrompts JSON，包含以下字段：
- shots: [{{shot_id, motion_prompt, motion_type, motion_params: {{camera_move, camera_speed, subject_motion, subject_motion_desc, environmental_motion, environmental_direction, particle_effect, duration}}, model_suggestion: {{primary, reason, fallback, fallback_reason}}, risk_notes, fallback_motion, image_prompt_revision, revised_image_prompt, videographer_note}}]
- global_video_style_suffix: 全局视频风格后缀词
- pacing_note: 全片节奏建议

只输出 JSON，不要输出任何其他文字。
"""
        return await llm_json(
            system_prompt,
            user_content,
            model=self._llm_model,
            max_tokens=8192,
            temperature=0.5,
            fallback={
                "shots": [],
                "global_video_style_suffix": "cinematic motion, smooth, natural physics, film look",
                "pacing_note": "",
                "_error": "视频师角色 LLM 调用失败",
            },
        )

    # ──────────────────────────────────────────────────────
    #  ⑤ 质检（纯 Python，不需要 LLM）
    # ──────────────────────────────────────────────────────
    @staticmethod
    def _quality_check(
        director_notes: Dict[str, Any],
        screenplay: Dict[str, Any],
        shot_prompts: Dict[str, Any],
        video_prompts: Dict[str, Any],
        target_duration: int,
    ) -> Dict[str, Any]:
        issues: list[str] = []
        checks: Dict[str, Any] = {}

        # 1. 时长检查
        scenes = screenplay.get("scenes", [])
        actual_duration = sum(
            s.get("duration", 0) for sc in scenes for s in sc.get("shots", [])
        )
        if target_duration > 0:
            diff_pct = abs(actual_duration - target_duration) / target_duration
            checks["duration"] = {
                "target": target_duration,
                "actual": actual_duration,
                "diff_pct": round(diff_pct * 100, 1),
            }
            if diff_pct > 0.15:
                issues.append(
                    f"时长偏差 {diff_pct*100:.1f}% 超过容差 15% "
                    f"(目标 {target_duration}s, 实际 {actual_duration}s)"
                )

        # 2. 镜头数检查
        shot_count = sum(len(sc.get("shots", [])) for sc in scenes)
        checks["shot_count"] = shot_count
        if shot_count < 5:
            issues.append(f"镜头数 {shot_count} 少于最小值 5")

        # 3. 视觉锚点完整性
        anchors = shot_prompts.get("visual_anchors", [])
        char_anchors = [a for a in anchors if a.get("kind") == "character"]
        loc_anchors = [a for a in anchors if a.get("kind") == "location"]

        char_names_in_anchors = {a.get("ref_name") for a in char_anchors}
        char_names_in_director = {c.get("name") for c in director_notes.get("characters", [])}
        missing_char_anchors = char_names_in_director - char_names_in_anchors

        checks["anchors"] = {
            "character_anchors": len(char_anchors),
            "location_anchors": len(loc_anchors),
            "missing_char_anchors": list(missing_char_anchors),
        }
        if missing_char_anchors:
            issues.append(f"缺少角色锚点: {missing_char_anchors}")

        # 4. 情绪曲线完整性
        arc = director_notes.get("emotional_arc", [])
        checks["emotional_arc"] = {
            "nodes": len(arc),
            "arc": arc,
        }
        if len(arc) < 3:
            issues.append(f"情绪曲线节点数 {len(arc)} 少于最小值 3")
        if arc and len(arc) >= 2 and arc[0] == arc[-1]:
            issues.append(f"情绪曲线首尾相同 ({arc[0]})，缺乏变化")

        # 5. 视频提示词覆盖
        sp_shot_ids = {s.get("shot_id") for sc in scenes for s in sc.get("shots", [])}
        vp_shot_ids = {s.get("shot_id") for s in video_prompts.get("shots", [])}
        missing_vp = sp_shot_ids - vp_shot_ids
        checks["video_coverage"] = {
            "total_shots": len(sp_shot_ids),
            "covered": len(vp_shot_ids),
            "missing": list(missing_vp),
        }
        if missing_vp:
            issues.append(f"视频师缺少这些镜头的运动提示词: {missing_vp}")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "checks": checks,
        }

    # ──────────────────────────────────────────────────────
    #  Markdown 输出
    # ──────────────────────────────────────────────────────
    @staticmethod
    def _build_full_markdown(result: Dict[str, Any]) -> str:
        """从结构化数据拼接完整的 Markdown 输出。"""
        parts: list[str] = []

        dn = result.get("director_notes", {})
        sp = result.get("screenplay", {})
        shp = result.get("shot_prompts", {})
        vp = result.get("video_prompts", {})
        qc = result.get("quality_report", {})

        title = sp.get("title", "")
        parts.append(f"# 🎬 {title or '文旅宣传片'}\n")

        # 基本信息
        parts.append("## 基本信息\n")
        info_parts = []
        if dn.get("theme"):
            info_parts.append(f"主题：{dn['theme']}")
        if dn.get("location"):
            info_parts.append(f"取景地：{dn['location']}")
        if dn.get("target_duration"):
            info_parts.append(f"目标时长：{dn['target_duration']}s")
        if dn.get("aspect_ratio"):
            info_parts.append(f"画幅：{dn['aspect_ratio']}")
        if sp.get("total_duration_estimate"):
            info_parts.append(f"预估时长：{sp['total_duration_estimate']}s")
        shot_count = sum(len(sc.get("shots", [])) for sc in sp.get("scenes", []))
        info_parts.append(f"镜头数：{shot_count}")
        if info_parts:
            parts.append(" | ".join(info_parts) + "\n")

        # 质检结果
        parts.append("## 质检报告\n")
        if qc.get("passed"):
            parts.append("✅ 质检通过\n")
        else:
            parts.append(f"⚠️ 质检发现 {len(qc.get('issues', []))} 个问题：\n")
            for issue in qc.get("issues", []):
                parts.append(f"- {issue}")
            parts.append("")

        # ── 导演手记 ──
        parts.append("---\n\n## 🎬 导演手记\n")
        if dn.get("logline") or dn.get("theme"):
            parts.append(f"**主题**：{dn.get('theme', '')}\n")
        if dn.get("sub_themes"):
            parts.append(f"**次级主题**：{'、'.join(dn['sub_themes'])}\n")
        if dn.get("story_type"):
            parts.append(f"**叙事类型**：{dn['story_type']}\n")
        if dn.get("emotional_arc"):
            parts.append(f"**情绪曲线**：{' → '.join(dn['emotional_arc'])}\n")
        if dn.get("location"):
            parts.append(f"**取景地**：{dn['location']}\n")
        if dn.get("cultural_tags"):
            parts.append(f"**文化标签**：{'、'.join(dn['cultural_tags'])}\n")
        if dn.get("tourism_selling"):
            parts.append(f"**文旅卖点**：{'、'.join(dn['tourism_selling'])}\n")
        if dn.get("key_motifs"):
            parts.append(f"**关键意象**：{'、'.join(dn['key_motifs'])}\n")
        if dn.get("director_note"):
            parts.append(f"**导演叮嘱**：{dn['director_note']}\n")

        # 三幕结构
        three_act = dn.get("three_act", {})
        if three_act:
            parts.append("\n### 三幕结构\n")
            parts.append(f"- **起**：{three_act.get('setup', '')}\n")
            parts.append(f"- **承/转**：{three_act.get('conflict', '')}\n")
            parts.append(f"- **合**：{three_act.get('resolve', '')}\n")

        # 角色卡
        characters = dn.get("characters", [])
        if characters:
            parts.append("\n### 角色卡\n")
            for ch in characters:
                parts.append(f"- **{ch.get('name', '')}**（{ch.get('role', '')}）"
                             f"｜{ch.get('age', '')}｜{ch.get('appearance', '')}\n")
                if ch.get("personality"):
                    parts.append(f"  性格：{ch['personality']}\n")
                if ch.get("arc"):
                    parts.append(f"  弧线：{ch['arc']}\n")

        # ── 编剧脚本 ──
        parts.append("\n---\n\n## 📝 编剧脚本\n")
        if sp.get("logline"):
            parts.append(f"**故事梗概**：{sp['logline']}\n")

        scenes = sp.get("scenes", [])
        for sc in scenes:
            parts.append(f"\n### {sc.get('scene_id', '')} {sc.get('location', '')}\n")
            if sc.get("time"):
                parts.append(f"- 时间：{sc['time']}\n")
            if sc.get("mood"):
                parts.append(f"- 情绪：{sc['mood']}\n")
            if sc.get("action"):
                parts.append(f"- 事件：{sc['action']}\n")
            if sc.get("purpose"):
                parts.append(f"- 功能：{sc['purpose']}\n")
            parts.append("\n| 镜头 | 景别 | 运镜 | 时长 | 画面描述 | 转场 |\n")
            parts.append("|------|------|------|------|----------|------|\n")
            for shot in sc.get("shots", []):
                desc = shot.get("desc", "")[:40]
                parts.append(
                    f"| {shot.get('shot_id', '')} | {shot.get('shot_type', '')} | "
                    f"{shot.get('camera_move', '')} | {shot.get('duration', '')}s | "
                    f"{desc} | {shot.get('transition_out', '')} |\n"
                )

        # 旁白
        voiceover = sp.get("voiceover", [])
        if voiceover:
            parts.append("\n### 旁白\n")
            for vo in voiceover:
                parts.append(f"- **{vo.get('shot_id', '')}**（{vo.get('emotion', '')}）："
                             f"\"{vo.get('text', '')}\"\n")

        # 字幕
        subtitles = sp.get("subtitles", [])
        if subtitles:
            parts.append("\n### 字幕\n")
            for sub in subtitles:
                parts.append(f"- [{sub.get('timing', '')}] {sub.get('text', '')}\n")

        # ── 分镜师 ──
        parts.append("\n---\n\n## 🎨 分镜画面提示词\n")

        # 视觉锚点
        anchors = shp.get("visual_anchors", [])
        if anchors:
            parts.append("### 视觉锚点\n")
            parts.append("| 锚点ID | 类型 | 名称 | 参考描述 |\n")
            parts.append("|--------|------|------|----------|\n")
            for a in anchors:
                desc = a.get("ref_desc", "")[:60]
                parts.append(
                    f"| {a.get('anchor_id', '')} | {a.get('kind', '')} | "
                    f"{a.get('ref_name', '')} | {desc} |\n"
                )
            parts.append("")

        # 逐镜头画面提示词
        shots = shp.get("shots", [])
        for shot in shots:
            parts.append(f"\n### {shot.get('shot_id', '')} 画面提示词\n")
            parts.append(f"**中文描述**：{shot.get('desc_cn', '')}\n")
            parts.append(f"**image_prompt**：\n```\n{shot.get('image_prompt', '')}\n```\n")
            parts.append(f"**negative_prompt**：\n```\n{shot.get('negative_prompt', '')}\n```\n")
            cam = shot.get("camera_params", {})
            if cam:
                parts.append(f"**镜头参数**：{cam.get('shot_size', '')} | {cam.get('lens', '')} | "
                             f"{cam.get('lighting', '')} | {cam.get('color_grade', '')}\n")
            if shot.get("composition"):
                parts.append(f"**构图**：{shot['composition']}\n")
            if shot.get("anchors_used"):
                parts.append(f"**使用锚点**：{', '.join(shot['anchors_used'])}\n")
            if shot.get("storyboard_note"):
                parts.append(f"**分镜师备注**：{shot['storyboard_note']}\n")

        # ── 视频师 ──
        parts.append("\n---\n\n## 🎥 视频运动提示词\n")

        if vp.get("pacing_note"):
            parts.append(f"**全片节奏建议**：{vp['pacing_note']}\n")

        vp_shots = vp.get("shots", [])
        for shot in vp_shots:
            parts.append(f"\n### {shot.get('shot_id', '')} 运动提示词\n")
            parts.append(f"**motion_prompt**：\n```\n{shot.get('motion_prompt', '')}\n```\n")
            parts.append(f"**运动类型**：{shot.get('motion_type', '')}\n")
            mp = shot.get("motion_params", {})
            if mp:
                parts.append(f"**运动参数**：{mp.get('camera_move', '')} | "
                             f"{mp.get('camera_speed', '')} | "
                             f"主体:{mp.get('subject_motion', '')} | "
                             f"{mp.get('duration', '')}s\n")
            ms = shot.get("model_suggestion", {})
            if ms:
                parts.append(f"**推荐模型**：{ms.get('primary', '')}（{ms.get('reason', '')}）\n")
                parts.append(f"**备选模型**：{ms.get('fallback', '')}（{ms.get('fallback_reason', '')}）\n")
            if shot.get("risk_notes"):
                parts.append(f"**风险提示**：{shot['risk_notes']}\n")
            if shot.get("fallback_motion"):
                parts.append(f"**兜底方案**：{shot['fallback_motion']}\n")
            if shot.get("image_prompt_revision"):
                parts.append(f"**画面修订**：{shot['image_prompt_revision']}\n")
                if shot.get("revised_image_prompt"):
                    parts.append(f"**修订后提示词**：\n```\n{shot['revised_image_prompt']}\n```\n")

        return "\n".join(parts)
