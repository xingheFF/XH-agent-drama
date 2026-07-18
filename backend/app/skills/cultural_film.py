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

    # ─── 分步流水线步骤定义 ───────────────────────────────
    PIPELINE_STEPS = [
        {"step": 1, "role": "导演", "name": "director_notes", "next_hint": "输入「继续」开始编剧创作"},
        {"step": 2, "role": "编剧", "name": "screenplay", "next_hint": "输入「继续」生成分镜画面提示词"},
        {"step": 3, "role": "分镜师", "name": "shot_prompts", "next_hint": "输入「继续」生成视频运动提示词"},
        {"step": 4, "role": "视频师", "name": "video_prompts", "next_hint": "输入「继续」生成质检报告并完成"},
    ]
    CONTINUE_KEYWORDS = {"继续", "继续生成", "继续执行", "下一步", "next", "continue", "继续输出", "继续吧"}

    @staticmethod
    def _is_continue_command(text: str) -> bool:
        """判断用户输入是否为继续指令。"""
        stripped = text.strip().lower()
        return stripped in CulturalFilmSkill.CONTINUE_KEYWORDS

    @staticmethod
    def _find_last_pipeline_state(history: Optional[List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
        """从对话历史中查找最近一次流水线状态（raw_data 中的累积数据）。

        返回最近一条包含 _pipeline_step 的 assistant 消息的 raw_data。
        """
        if not history:
            return None
        for msg in reversed(history):
            if msg.get("role") != "assistant":
                continue
            raw = msg.get("raw_data")
            if raw and isinstance(raw, dict) and "_pipeline_step" in raw:
                return raw
        return None

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

        # ── 判断是否为继续指令 ──
        is_continue = self._is_continue_command(user_input)
        prev_state = self._find_last_pipeline_state(history) if is_continue else None

        if is_continue and not prev_state:
            return SkillOutput(
                skill_id=self.info.skill_id,
                status="success",
                data={
                    "_pipeline_step": 0,
                    "_pipeline_next_hint": "请先输入剧本或灵感描述，启动流水线后再输入「继续」",
                    "full_markdown": "⚠️ 暂无进行中的流水线。请先输入剧本或灵感描述来启动文旅宣传片创作流程。",
                },
            )

        if is_continue:
            # 从历史状态恢复，执行下一步
            return await self._continue_pipeline(prev_state, visual_style, target_duration, aspect_ratio)
        else:
            # 首次调用，执行第1步（导演）
            return await self._start_pipeline(
                user_input, target_duration, aspect_ratio, resolution,
                visual_style, tone,
            )

    async def _start_pipeline(
        self,
        user_input: str,
        target_duration: int,
        aspect_ratio: str,
        resolution: str,
        visual_style: str,
        tone: str,
    ) -> SkillOutput:
        """执行第1步：导演角色。"""
        try:
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

            step_info = self.PIPELINE_STEPS[0]
            result = {
                "skill_id": self.info.skill_id,
                "skill_name": self.info.skill_name,
                "project_id": f"film_{uuid.uuid4().hex[:8]}",
                "_pipeline_step": 1,
                "_pipeline_total": len(self.PIPELINE_STEPS) + 1,
                "_pipeline_next_hint": step_info["next_hint"],
                "director_notes": director_notes,
                "screenplay": None,
                "shot_prompts": None,
                "video_prompts": None,
                "quality_report": None,
                "pipeline_version": "2.0.0",
                "full_markdown": "",
            }
            result["full_markdown"] = self._build_step_markdown(result, 1)
            return SkillOutput(skill_id=self.info.skill_id, status="success", data=result)

        except Exception as e:
            logger.exception("[cultural-film] 导演步骤执行失败")
            return SkillOutput(
                skill_id=self.info.skill_id, status="failed",
                data={"_error": str(e)}, error=str(e),
            )

    async def _continue_pipeline(
        self,
        prev_state: Dict[str, Any],
        visual_style: str,
        target_duration: int,
        aspect_ratio: str,
    ) -> SkillOutput:
        """从历史状态恢复，执行下一步。"""
        current_step = prev_state.get("_pipeline_step", 0)
        next_step = current_step + 1

        # 恢复已累积的数据
        director_notes = prev_state.get("director_notes") or {}
        screenplay = prev_state.get("screenplay") or {}
        shot_prompts = prev_state.get("shot_prompts") or {}
        project_id = prev_state.get("project_id", f"film_{uuid.uuid4().hex[:8]}")

        try:
            if next_step == 2:
                # ── ② 编剧 ──
                screenplay = await self._run_screenwriter(
                    director_notes, target_duration, aspect_ratio,
                )
                if screenplay.get("_is_fallback"):
                    return SkillOutput(
                        skill_id=self.info.skill_id, status="failed",
                        data=screenplay, error="编剧角色 LLM 调用失败",
                    )

            elif next_step == 3:
                # ── ③ 分镜师 ──
                shot_prompts = await self._run_storyboard(
                    director_notes, screenplay, visual_style,
                )
                if shot_prompts.get("_is_fallback"):
                    return SkillOutput(
                        skill_id=self.info.skill_id, status="failed",
                        data=shot_prompts, error="分镜师角色 LLM 调用失败",
                    )

            elif next_step == 4:
                # ── ④ 视频师 ──
                video_prompts = await self._run_videographer(
                    director_notes, screenplay, shot_prompts,
                )
                if video_prompts.get("_is_fallback"):
                    return SkillOutput(
                        skill_id=self.info.skill_id, status="failed",
                        data=video_prompts, error="视频师角色 LLM 调用失败",
                    )

            elif next_step == 5:
                # ── ⑤ 质检 + 最终组装 ──
                video_prompts = prev_state.get("video_prompts") or {}
                quality_report = self._quality_check(
                    director_notes, screenplay, shot_prompts, video_prompts,
                    target_duration,
                )
                result = {
                    "skill_id": self.info.skill_id,
                    "skill_name": self.info.skill_name,
                    "project_id": project_id,
                    "_pipeline_step": 5,
                    "_pipeline_total": 5,
                    "_pipeline_next_hint": "✅ 流水线已全部完成",
                    "_pipeline_done": True,
                    "director_notes": director_notes,
                    "screenplay": screenplay,
                    "shot_prompts": shot_prompts,
                    "video_prompts": video_prompts,
                    "quality_report": quality_report,
                    "pipeline_version": "2.0.0",
                    "full_markdown": "",
                }
                result["full_markdown"] = self._build_full_markdown(result)
                return SkillOutput(skill_id=self.info.skill_id, status="success", data=result)

            else:
                return SkillOutput(
                    skill_id=self.info.skill_id, status="success",
                    data={
                        **prev_state,
                        "_pipeline_next_hint": "✅ 流水线已全部完成，无需继续",
                        "full_markdown": "✅ 所有步骤已完成，无需继续。",
                    },
                )

            # 组装当前步骤的结果
            step_info = self.PIPELINE_STEPS[next_step - 1]
            result = {
                "skill_id": self.info.skill_id,
                "skill_name": self.info.skill_name,
                "project_id": project_id,
                "_pipeline_step": next_step,
                "_pipeline_total": len(self.PIPELINE_STEPS) + 1,
                "_pipeline_next_hint": step_info["next_hint"],
                "director_notes": director_notes,
                "screenplay": screenplay if next_step >= 2 else None,
                "shot_prompts": shot_prompts if next_step >= 3 else None,
                "video_prompts": video_prompts if next_step >= 4 else None,
                "quality_report": None,
                "pipeline_version": "2.0.0",
                "full_markdown": "",
            }
            result["full_markdown"] = self._build_step_markdown(result, next_step)
            return SkillOutput(skill_id=self.info.skill_id, status="success", data=result)

        except Exception as e:
            logger.exception("[cultural-film] 步骤 %d 执行失败", next_step)
            return SkillOutput(
                skill_id=self.info.skill_id, status="failed",
                data={"_error": str(e), **prev_state}, error=str(e),
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

【创作约束】
- 目标时长: {target_duration}秒
- 画幅: {aspect_ratio}
- 分辨率: {resolution}
- 帧率: 30
- 视觉风格: {visual_style}
- 全片基调: {tone}
- 所有输出内容均用中文

请根据用户输入识别其类型（完整剧本/灵感描述/混合输入），并输出 DirectorNotes JSON。

字段要求：
- theme: 一句话主题（动词+名词结构）
- sub_themes: 2-4个次级主题
- story_type: 情感散文式/故事片式/散文诗式/纪实访谈式
- three_act: {{setup, conflict, resolve}}，conflict 必须有明确转折
- emotional_arc: 3-6个情绪节点，首尾不能相同
- location: 主取景地，精确到村/镇/景区
- cultural_tags: 3-6个文化标签
- tourism_selling: 2-4个文旅卖点（观众想体验的事，不是景点名称）
- target_duration: {target_duration}
- aspect_ratio: "{aspect_ratio}"
- resolution: "{resolution}"
- fps: 30
- visual_style: "{visual_style}"
- tone: "{tone}"
- characters: [{{name, role, age, appearance, personality, base_expression, emotional_range, speech_style, arc}}]
  appearance 必须含至少4个视觉要素：人种性别+发型+体型+服装+面部特征
  base_expression: 角色默认表情基线，具体到眉/眼/嘴形态
  emotional_range: 角色在全片中的3-6种表情变化列表
  speech_style: 角色说话风格，无台词则填"无台词"
- key_motifs: 3-6个关键意象（必须是能特写捕捉的具象物体，不要抽象概念）
- director_note: 给下游的特别叮嘱（可空）

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
【导演手记】
{dn_json}

【分镜约束】
- 目标时长: {target_duration}秒（所有镜头 duration 之和应接近此时长，容差±10%）
- 单镜头时长: 2-6秒（片头片尾空镜可至8秒）
- 每场景镜头数: 2-5个
- 旁白语速: slow=3.0字/秒, normal=3.5字/秒, fast=4.5字/秒
- 可用转场: cut(硬切), crossfade(交叉溶解), dissolve(溶解), match_cut(匹配剪辑), whip_pan(快速横摇), wipe(擦除)

请根据导演手记创作完整 Screenplay JSON：
- title: 片名（1-4字）
- logline: 一句话故事梗概（含主角+目标+冲突）
- genre: 类型
- total_duration_estimate: 预估总时长（秒）
- scenes: 场景列表，每个场景含 {{scene_id, location, time, mood, action, purpose, shots}}
  shots 中每个镜头含 {{shot_id, scene_id, shot_type, camera_move, duration, desc, dialogue, character_expression, character_action, character_emotion, purpose, transition_out, characters_in_shot, location_in_shot}}
  desc 必须具体：谁+在哪+做什么+看到什么+表情如何
  dialogue: 角色台词列表 [{{speaker, text, emotion}}]，无台词则留空数组 []
  character_expression: 角色面部表情，具体到眉/眼/嘴形态，无人物则留空 {{}}
  character_action: 角色肢体动作，具体到哪个部位做什么，无人物则留空 {{}}
  character_emotion: 角色内心情绪（对应导演 emotional_arc），无人物则留空 {{}}
- voiceover: 旁白列表 {{shot_id, text, emotion, speed_preset}}
  旁白与画面错位，不要复述画面；旁白覆盖率50%-70%
- subtitles: 字幕列表 {{timing, shot_id, text, style_hint}}
  timing: opening/closing/scene_intro/caption
- screenwriter_note: 编剧备注

shot_id 格式: {{场景号}}-{{镜头序号}}，如 S1-01。
景别有节奏：大→中→特 或 特→中→大，不要全大全景或全特写。
转场有设计：不要全 cut，情绪转折处用 match_cut 或 dissolve。
导演 key_motifs 中的每个意象必须在至少1个镜头的 desc 里被描述。

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
    #  ③ 分镜师（分批调用，避免超时）
    # ──────────────────────────────────────────────────────
    async def _run_storyboard(
        self,
        director_notes: Dict[str, Any],
        screenplay: Dict[str, Any],
        visual_style: str,
    ) -> Dict[str, Any]:
        """分镜师：先生成视觉锚点，再按场景分批生成镜头提示词。"""
        system_prompt = _load_prompt("storyboard.md")
        dn_json = json.dumps(director_notes, ensure_ascii=False, indent=2)

        # ── 3a: 生成视觉锚点（小输出，快速完成）──
        characters = director_notes.get("characters", [])
        scenes_meta = [
            {"scene_id": sc.get("scene_id", ""), "location": sc.get("location", ""), "time": sc.get("time", "")}
            for sc in screenplay.get("scenes", [])
        ]
        anchors_user_content = f"""\
【导演手记】
{dn_json}

【角色清单】
{json.dumps(characters, ensure_ascii=False, indent=2)}

【场景清单】
{json.dumps(scenes_meta, ensure_ascii=False, indent=2)}

【视觉锚点生成要求】
1. 为每个角色建立 character 锚点（anchor_id 格式: char_001, char_002...）
   - ref_desc 必须按顺序包含：人种性别→年龄段→发型→体型→服装→面部特征→默认表情基线
2. 为每个场景建立 location 锚点（anchor_id 格式: loc_001, loc_002...）
   - ref_desc 必须包含：建筑风格+材质+色调+标志性元素
3. 为导演 key_motifs 中的每个意象建立 prop 锚点（anchor_id 格式: prop_001, prop_002...）
   - ref_desc 必须包含：材质+年代感+颜色+磨损程度+特征细节
4. consistency_tags 用中文撰写，如"同一人物，面部特征一致，服装完全相同"
5. negative_consistency 用中文撰写，如"不同人物，面部不一致，服装变化"

同时输出全局风格后缀和负向后缀（均用中文）：
- global_style_suffix: 基于视觉风格"{visual_style}"生成的全局风格词
- global_negative_suffix: 全局负向提示词

请只输出视觉锚点 visual_anchors，不要输出 shots。

输出 JSON：
{{"visual_anchors": [...], "global_style_suffix": "...", "global_negative_suffix": "..."}}

只输出 JSON，不要输出任何其他文字。
"""
        anchors_result = await llm_json(
            system_prompt,
            anchors_user_content,
            model=self._llm_model,
            max_tokens=2048,
            temperature=0.5,
            fallback={
                "visual_anchors": [],
                "global_style_suffix": f"{visual_style}，电影质感，胶片颗粒，高细节",
                "global_negative_suffix": "低分辨率，模糊，畸形，丑陋，文字，水印",
            },
        )
        if anchors_result.get("_is_fallback"):
            return {
                **anchors_result,
                "shots": [],
                "_error": "分镜师-视觉锚点 LLM 调用失败",
            }

        visual_anchors = anchors_result.get("visual_anchors", [])
        global_style_suffix = anchors_result.get("global_style_suffix", f"{visual_style}，电影质感，胶片颗粒，高细节")
        global_negative_suffix = anchors_result.get("global_negative_suffix", "低分辨率，模糊，畸形，丑陋，文字，水印")
        anchors_json = json.dumps(visual_anchors, ensure_ascii=False, indent=2)

        # ── 3b-pre: 全局镜头流规划（让 LLM 先规划整片镜头节奏，再逐场景细化）──
        scenes = screenplay.get("scenes", [])
        key_motifs = director_notes.get("key_motifs", [])
        emotional_arc = director_notes.get("emotional_arc", [])

        all_shot_ids: list[str] = []
        scenes_shot_meta: list[Dict[str, Any]] = []
        for sc in scenes:
            for s in sc.get("shots", []):
                sid = s.get("shot_id", "")
                all_shot_ids.append(sid)
                scenes_shot_meta.append({
                    "shot_id": sid,
                    "scene_id": s.get("scene_id", ""),
                    "shot_type": s.get("shot_type", ""),
                    "camera_move": s.get("camera_move", ""),
                    "duration": s.get("duration", 0),
                    "desc": s.get("desc", "")[:50],
                    "transition_out": s.get("transition_out", ""),
                })

        flow_plan_content = f"""\
【导演手记（摘要）】
主题: {director_notes.get('theme', '')}
视觉风格: {visual_style}
基调: {director_notes.get('tone', '')}
情绪曲线: {emotional_arc}

【全片镜头清单（按时间顺序）】
{json.dumps(scenes_shot_meta, ensure_ascii=False, indent=2)}

【镜头流规划要求】
请为整片规划镜头节奏流，确保镜头之间有视觉连续性和叙事逻辑。

1. 景别节奏：遵循"开场大全景建立→中段中景/近景交替→结尾回归大全景留白"原则
   - 相邻镜头景别不要重复（大全景后面不要接大全景，除非是跨场景建立镜头）
   - 情绪高潮处用特写/近景，过渡处用中景，环境交代用全景/大全景
2. 运镜衔接：相邻镜头运镜要有"呼吸感"
   - 推进后面接固定或拉远（给观众"看完细节后喘口气"）
   - 航拍后面接地面视角（从宏观到微观）
   - 快速运动后面接慢速或固定（避免眩晕）
3. 色调过渡：色调随情绪曲线变化
   - 前段（铺垫）: 偏冷/偏暗，营造氛围
   - 中段（冲突）: 对比增强，冷暖交替
   - 后段（解决）: 偏暖/明亮，释放情绪
4. 场景间衔接：跨场景的第一个镜头应该是新场景的建立镜头（大全景或全景），让观众知道换了地方
5. 每个场景的最后一个镜头要为下一个场景做铺垫（视觉引导线指向画面外、角色视线朝向下一场景方向等）

请输出每个 shot_id 的规划：
{{"shot_flow_plan": [{{"shot_id": "...", "planned_shot_size": "...", "planned_camera_move": "...", "planned_color_grade": "...", "flow_note": "与上一镜头的衔接说明"}}]}}

只输出 JSON，不要输出任何其他文字。
"""
        flow_plan_result = await llm_json(
            system_prompt,
            flow_plan_content,
            model=self._llm_model,
            max_tokens=4096,
            temperature=0.4,
            fallback={"shot_flow_plan": []},
        )
        shot_flow_plan = flow_plan_result.get("shot_flow_plan", [])
        # 构建 shot_id → flow_plan 映射
        flow_plan_map: Dict[str, Dict[str, Any]] = {
            p.get("shot_id", ""): p for p in shot_flow_plan
        }
        flow_plan_json = json.dumps(shot_flow_plan, ensure_ascii=False, indent=2)

        # ── 3b: 按场景分批生成镜头提示词（带跨场景衔接上下文）──
        all_shots: list[Dict[str, Any]] = []
        total_scenes = len(scenes)

        for scene_idx, scene in enumerate(scenes):
            scene_shots = scene.get("shots", [])
            if not scene_shots:
                continue

            # 构建上下文：上一场景最后一个已生成的镜头
            prev_scene_last_shot = None
            if all_shots:
                prev_scene_last_shot = {
                    "shot_id": all_shots[-1].get("shot_id", ""),
                    "shot_size": all_shots[-1].get("camera_params", {}).get("shot_size", ""),
                    "image_prompt": all_shots[-1].get("image_prompt", "")[:100],
                    "color_grade": all_shots[-1].get("camera_params", {}).get("color_grade", ""),
                    "camera_move": all_shots[-1].get("camera_params", {}).get("shot_size", ""),
                }

            # 构建上下文：下一场景摘要
            next_scene_summary = None
            if scene_idx + 1 < total_scenes:
                next_sc = scenes[scene_idx + 1]
                next_scene_summary = {
                    "scene_id": next_sc.get("scene_id", ""),
                    "location": next_sc.get("location", ""),
                    "time": next_sc.get("time", ""),
                    "mood": next_sc.get("mood", ""),
                    "action": next_sc.get("action", ""),
                }

            # 本场景的镜头流规划（只传本场景的）
            scene_shot_ids = [s.get("shot_id", "") for s in scene_shots]
            scene_flow_plan = [flow_plan_map.get(sid, {}) for sid in scene_shot_ids]
            scene_flow_json = json.dumps(scene_flow_plan, ensure_ascii=False, indent=2)

            scene_summary = {
                "scene_id": scene.get("scene_id", ""),
                "location": scene.get("location", ""),
                "time": scene.get("time", ""),
                "mood": scene.get("mood", ""),
                "action": scene.get("action", ""),
                "shots": scene_shots,
            }
            scene_json = json.dumps(scene_summary, ensure_ascii=False, indent=2)

            prev_shot_json = json.dumps(prev_scene_last_shot, ensure_ascii=False, indent=2) if prev_scene_last_shot else "无（这是第一个场景）"
            next_scene_json = json.dumps(next_scene_summary, ensure_ascii=False, indent=2) if next_scene_summary else "无（这是最后一个场景）"

            shots_user_content = f"""\
【导演手记（摘要）】
主题: {director_notes.get('theme', '')}
视觉风格: {visual_style}
基调: {director_notes.get('tone', '')}
情绪曲线: {emotional_arc}
关键意象: {key_motifs}

【当前场景位置】第 {scene_idx + 1}/{total_scenes} 场

【视觉锚点（已生成，请在 anchors_used 中引用对应 anchor_id）】
{anchors_json}

【本场景镜头流规划（已由全局规划生成，请遵循）】
{scene_flow_json}
- planned_shot_size: 建议景别，必须遵循
- planned_camera_move: 建议运镜，必须遵循
- planned_color_grade: 建议色调，必须遵循
- flow_note: 与上一镜头的衔接说明，必须在画面中体现

【上一场景最后一个镜头（衔接参考）】
{prev_shot_json}
- 本场景第一个镜头必须与上一场景最后一个镜头形成视觉衔接
- 如果上一镜头是近景/特写，本场景应以大全景/全景建立新环境
- 如果上一镜头色调偏冷，本场景色调过渡应自然变化，不要突变

【下一场景摘要（预告参考）】
{next_scene_json}
- 本场景最后一个镜头应为下一场景做视觉铺垫（如角色视线朝向下一场景方向、画面留白引导等）

【关键意象约束】
- 导演要求的关键意象必须在至少一个镜头的 image_prompt 里被明确描述

【当前场景的镜头清单】
{scene_json}

【画面提示词生成要求】
1. image_prompt 用中文，按公式拼接：景别+主体描述（含面部表情）+环境描述+光线+色调+镜头语言+风格词+一致性锚点词
2. image_prompt 字数控制在80-200字
3. 当镜头有人物时，image_prompt 必须包含编剧 character_expression 中的面部表情描述
4. 当镜头有人物时，image_prompt 应包含编剧 character_action 中的关键肢体动作
5. negative_prompt 用中文，包含本镜头特有风险+通用负向+一致性负向
6. camera_params 各字段用中文（如 lens 用"50毫米"而非"50mm"）
7. camera_params.shot_size 必须等于镜头流规划中的 planned_shot_size
8. camera_params 的 lighting/color_grade 必须与镜头流规划一致，且与上一场景末尾色调自然过渡
9. composition 用中文描述主体位置和视觉引导线
10. anchors_used 必须引用视觉锚点中已有的 anchor_id
11. storyboard_note 必须说明本镜头与上一镜头的衔接关系（景别变化、运镜过渡、色调衔接等）

【镜头衔接准则（重要！）】
- 同场景内相邻镜头：景别要有变化（大全景→中景→特写，或特写→中景→全景），不要连续两个相同景别
- 跨场景：新场景第一个镜头必须是建立镜头（大全景或全景），让观众知道换地方了
- 运镜衔接：推进后接固定或拉远，快速运动后接慢速，避免连续两个快速运动
- 色调过渡：色调随情绪曲线变化，相邻镜头色调差异不要太大，跨场景可渐变
- 构图引导线：本场景最后一个镜头的构图引导线应指向画面外，暗示后续发展

【角色四维度携带要求（重要！）】
每个 shot 的输出必须原样携带编剧提供的以下字段，不得遗漏或篡改：
- dialogue: 原样复制编剧该镜头的 dialogue（台词列表，含speaker/text/emotion），无台词则为空数组 []
- character_expression: 原样复制编剧该镜头的 character_expression（角色面部表情字典），无人物则为空对象 {{}}
- character_action: 原样复制编剧该镜头的 character_action（角色肢体动作字典），无人物则为空对象 {{}}
- character_emotion: 原样复制编剧该镜头的 character_emotion（角色内心情绪字典），无人物则为空对象 {{}}
这些字段供下游视频师参考，必须完整保留。

请为以上每个 shot 生成 ShotPrompt。
每个 shot 包含: shot_id, desc_cn, image_prompt, negative_prompt,
camera_params: {{shot_size, lens, angle, lighting, lighting_direction, color_grade, depth_of_field, film_stock_hint}},
composition, composition_rules, anchors_used, reference_images, storyboard_note,
dialogue, character_expression, character_action, character_emotion

输出 JSON：
{{"shots": [...]}}

只输出 JSON，不要输出任何其他文字。
"""
            batch_result = await llm_json(
                system_prompt,
                shots_user_content,
                model=self._llm_model,
                max_tokens=4096,
                temperature=0.6,
                fallback={"shots": []},
            )
            batch_shots = batch_result.get("shots", [])
            if batch_shots:
                all_shots.extend(batch_shots)
            else:
                # 该场景失败，用简单降级填充
                for s in scene_shots:
                    sid = s.get("shot_id", "")
                    all_shots.append({
                        "shot_id": sid,
                        "desc_cn": s.get("desc", ""),
                        "image_prompt": f"{s.get('shot_type', '中景')}，{s.get('desc', '')}，{visual_style}，电影感构图，高细节",
                        "negative_prompt": "低分辨率，模糊，畸形，丑陋，文字，水印，压缩失真，过度修图",
                        "camera_params": {
                            "shot_size": s.get("shot_type", "中景"),
                            "lens": "50毫米",
                            "angle": "平视",
                            "lighting": "自然光",
                            "lighting_direction": "正面",
                            "color_grade": "电影调色",
                            "depth_of_field": "中等",
                            "film_stock_hint": "数字纯净",
                        },
                        "composition": "三分法构图，主体位于画面三分之一处",
                        "composition_rules": ["三分法"],
                        "anchors_used": [],
                        "reference_images": "",
                        "storyboard_note": "LLM 生成失败，使用降级提示词",
                        "dialogue": s.get("dialogue", []),
                        "character_expression": s.get("character_expression", {}),
                        "character_action": s.get("character_action", {}),
                        "character_emotion": s.get("character_emotion", {}),
                    })

        return {
            "visual_anchors": visual_anchors,
            "shots": all_shots,
            "global_style_suffix": global_style_suffix,
            "global_negative_suffix": global_negative_suffix,
        }

    # ──────────────────────────────────────────────────────
    #  ④ 视频师（按场景分批调用，避免超时）
    # ──────────────────────────────────────────────────────
    async def _run_videographer(
        self,
        director_notes: Dict[str, Any],
        screenplay: Dict[str, Any],
        shot_prompts: Dict[str, Any],
    ) -> Dict[str, Any]:
        """视频师：按场景分批生成视频运动提示词。"""
        system_prompt = _load_prompt("videographer.md")
        models_table = json.dumps(VIDEO_MODELS, ensure_ascii=False, indent=2)
        emotional_arc = director_notes.get("emotional_arc", [])
        visual_style = director_notes.get("visual_style", "")

        # 构建编剧镜头的 shot_id → 角色四维度映射
        screenplay_shots_map: Dict[str, Dict[str, Any]] = {}
        for sc in screenplay.get("scenes", []):
            for s in sc.get("shots", []):
                sid = s.get("shot_id", "")
                if sid:
                    screenplay_shots_map[sid] = {
                        "shot_id": sid,
                        "dialogue": s.get("dialogue", []),
                        "character_expression": s.get("character_expression", {}),
                        "character_action": s.get("character_action", {}),
                        "character_emotion": s.get("character_emotion", {}),
                        "desc": s.get("desc", ""),
                        "duration": s.get("duration", 3),
                    }

        # 按 scene_id 分组 shot_prompts，保持场景顺序
        sp_shots = shot_prompts.get("shots", [])
        shots_by_scene: Dict[str, list] = {}
        scene_order: list[str] = []
        for shot in sp_shots:
            sid = shot.get("shot_id", "")
            # shot_id 格式如 S1-01，提取场景号
            scene_key = sid.split("-")[0] if "-" in sid else sid
            if scene_key not in shots_by_scene:
                scene_order.append(scene_key)
                shots_by_scene[scene_key] = []
            shots_by_scene[scene_key].append(shot)

        all_video_shots: list[Dict[str, Any]] = []
        total_scenes = len(scene_order)

        for scene_idx, scene_key in enumerate(scene_order):
            scene_shots = shots_by_scene[scene_key]

            # 合并分镜师画面提示词 + 编剧角色四维度数据
            merged_shots: list[Dict[str, Any]] = []
            for sb_shot in scene_shots:
                sid = sb_shot.get("shot_id", "")
                sp_data = screenplay_shots_map.get(sid, {})
                merged = {**sb_shot}
                # 确保四维度字段存在（优先用分镜师携带的，其次用编剧原始数据）
                if not merged.get("dialogue"):
                    merged["dialogue"] = sp_data.get("dialogue", [])
                if not merged.get("character_expression"):
                    merged["character_expression"] = sp_data.get("character_expression", {})
                if not merged.get("character_action"):
                    merged["character_action"] = sp_data.get("character_action", {})
                if not merged.get("character_emotion"):
                    merged["character_emotion"] = sp_data.get("character_emotion", {})
                merged_shots.append(merged)

            # 构建上下文：上一场景最后一个已生成的视频镜头
            prev_scene_last_video = None
            if all_video_shots:
                last_vs = all_video_shots[-1]
                prev_scene_last_video = {
                    "shot_id": last_vs.get("shot_id", ""),
                    "motion_type": last_vs.get("motion_type", ""),
                    "motion_prompt": last_vs.get("motion_prompt", "")[:80],
                    "camera_move": last_vs.get("motion_params", {}).get("camera_move", ""),
                    "camera_speed": last_vs.get("motion_params", {}).get("camera_speed", ""),
                    "duration": last_vs.get("motion_params", {}).get("duration", 0),
                }

            # 构建上下文：下一场景的首镜头信息
            next_scene_first_shot = None
            if scene_idx + 1 < total_scenes:
                next_scene_key = scene_order[scene_idx + 1]
                next_shots = shots_by_scene.get(next_scene_key, [])
                if next_shots:
                    ns = next_shots[0]
                    next_scene_first_shot = {
                        "shot_id": ns.get("shot_id", ""),
                        "desc_cn": ns.get("desc_cn", "")[:60],
                        "shot_size": ns.get("camera_params", {}).get("shot_size", ""),
                    }

            scene_shots_json = json.dumps(merged_shots, ensure_ascii=False, indent=2)
            prev_video_json = json.dumps(prev_scene_last_video, ensure_ascii=False, indent=2) if prev_scene_last_video else "无（这是第一个场景）"
            next_shot_json = json.dumps(next_scene_first_shot, ensure_ascii=False, indent=2) if next_scene_first_shot else "无（这是最后一个场景）"

            batch_user_content = f"""\
【导演手记（摘要）】
主题: {director_notes.get('theme', '')}
视觉风格: {visual_style}
情绪曲线: {emotional_arc}

【当前场景位置】第 {scene_idx + 1}/{total_scenes} 场

【上一场景最后一个镜头的运动（衔接参考）】
{prev_video_json}
- 本场景第一个镜头的运动必须与上一场景最后一个镜头形成衔接
- 如果上一镜头是快速推进，本场景应以固定或缓慢拉远开场（给观众喘息空间）
- 如果上一镜头是航拍，本场景应从地面视角开始（从宏观到微观）
- 运动速度过渡要自然，不要从极慢突变到极快

【下一场景第一个镜头（预告参考）】
{next_shot_json}
- 本场景最后一个镜头应为下一场景做运动铺垫
- 如下一场景是动作场景，本场景末尾可加速；如下一场景是静态空镜，本场景末尾应减速

【分镜师画面提示词 + 编剧角色数据（本场景）】
每个 shot 包含分镜师的画面提示词（image_prompt/camera_params等）以及编剧的角色四维度数据（dialogue/character_expression/character_action/character_emotion）。
{scene_shots_json}

【视频模型能力表】
{models_table}

【可用运动类型】
- camera_movement: 镜头运动为主（推拉摇移升降航拍环绕）
- character_action: 人物动作为主（走/跑/转身/手部动作）
- environment_atmosphere: 环境氛围为主（雾气/水波/光影/粒子）
- still_ken_burns: 静态图缓慢推拉（兜底）

【运动提示词生成要求】
1. motion_prompt 用中文，公式：镜头动作+主体动作（含表情变化）+环境运动+时长秒+风格词
2. motion_prompt 字数控制在30-80字，必须包含明确的运动方向和时长
3. motion_params 各字段用中文（camera_move/camera_speed/subject_motion/expression_motion等）
4. expression_motion 必须基于编剧 character_expression 和 character_emotion 描述角色面部表情变化轨迹。若角色有表情数据，必须具体描述表情如何变化（如"眉头从微蹙渐变为舒展，嘴角从抿紧到微微上扬"）；若表情无变化则填"表情保持不变"
5. subject_motion_desc 必须基于编剧 character_action 描述角色肢体动作（如"右手撑伞沿巷道缓步前行，步伐沉重"），无人物动作则留空
6. 若该镜头有台词（dialogue非空），motion_prompt 必须包含角色说话的动作描述（如"嘴唇微动轻声说话"），优先选择支持原生音频的模型并在 reason 中说明
7. model_suggestion 的 reason 必须引用模型的 strengths 或 weaknesses 作为依据
8. 优先推荐 seedance_2（全能型，支持原生音频），备选根据镜头类型选择
9. 每个镜头必须有 risk_notes（风险预判）和 fallback_motion（兜底方案）
10. 若分镜师画面中有"动起来会很怪"的元素，在 image_prompt_revision 中提出修订建议
11. 输出中必须原样携带 dialogue, character_expression, character_action, character_emotion 字段
12. videographer_note 必须说明本镜头与上一镜头的运动衔接关系（速度过渡、方向变化、运动类型切换等）

【运动衔接准则（重要！）】
- 同场景内相邻镜头：运动要有"呼吸感"，推进后接固定或拉远，快速后接慢速
- 跨场景：新场景第一个镜头的运动应与上一场景末尾形成对比或过渡（如上一场景末尾是急推，新场景以固定空镜开场）
- 运动速度曲线：整片速度应是 慢→中→快→慢 的弧线，对应情绪曲线（前段慢、中段快、结尾慢）
- 运动类型分布：前段多 camera_movement + environment_atmosphere，中段多 character_action，结尾回归 environment_atmosphere
- 避免连续两个镜头都是快速运动（会让观众眩晕）
- 避免连续两个镜头都是同方向运动（如连续两个都是"从左到右"）

请为以上每个 shot 输出 VideoShotPrompt。
每个 shot 包含: shot_id, motion_prompt, motion_type,
motion_params: {{camera_move, camera_speed, subject_motion, subject_motion_desc, expression_motion, environmental_motion, environmental_direction, particle_effect, duration}},
model_suggestion: {{primary, reason, fallback, fallback_reason}},
risk_notes, fallback_motion, image_prompt_revision, revised_image_prompt, videographer_note,
dialogue, character_expression, character_action, character_emotion

输出 JSON：
{{"shots": [...]}}

只输出 JSON，不要输出任何其他文字。
"""
            batch_result = await llm_json(
                system_prompt,
                batch_user_content,
                model=self._llm_model,
                max_tokens=4096,
                temperature=0.5,
                fallback={"shots": []},
            )
            batch_shots = batch_result.get("shots", [])
            if batch_shots:
                all_video_shots.extend(batch_shots)
            else:
                # 降级：用规则生成简单的运动提示词，从编剧/分镜师补齐四维度
                for shot in merged_shots:
                    sid = shot.get("shot_id", "")
                    cam = shot.get("camera_params", {})
                    sp_data = screenplay_shots_map.get(sid, {})
                    dialogue = shot.get("dialogue") or sp_data.get("dialogue", [])
                    expr = shot.get("character_expression") or sp_data.get("character_expression", {})
                    action = shot.get("character_action") or sp_data.get("character_action", {})
                    emotion = shot.get("character_emotion") or sp_data.get("character_emotion", {})
                    # 根据编剧数据生成更准确的降级描述
                    expr_motion = "表情保持不变"
                    if expr:
                        expr_motion = "；".join(f"{k}：{v}" for k, v in expr.items())
                    action_desc = ""
                    if action:
                        action_desc = "；".join(f"{k}：{v}" for k, v in action.items())
                    has_dialogue = bool(dialogue)
                    motion_type = "character_action" if (action or has_dialogue) else "camera_movement"
                    duration = sp_data.get("duration", 3)
                    motion_prefix = ""
                    if action_desc:
                        motion_prefix = f"{action_desc}，"
                    if has_dialogue:
                        speaker_texts = "；".join(f"{d.get('speaker', '')}说'{d.get('text', '')}'" for d in dialogue)
                        motion_prefix += f"{speaker_texts}，嘴唇微动，"
                    all_video_shots.append({
                        "shot_id": sid,
                        "motion_prompt": f"{motion_prefix}{cam.get('shot_size', '中景')}缓慢推进，{duration}秒，{visual_style}，电影感运动流畅自然物理胶片质感",
                        "motion_type": motion_type,
                        "motion_params": {
                            "camera_move": "推进",
                            "camera_speed": "慢",
                            "subject_motion": "中等" if action else "细微",
                            "subject_motion_desc": action_desc,
                            "expression_motion": expr_motion,
                            "environmental_motion": [],
                            "environmental_direction": "",
                            "particle_effect": "",
                            "duration": duration,
                        },
                        "model_suggestion": {
                            "primary": "seedance_2",
                            "reason": "Seedance 2.0为全能型模型，擅长镜头运动且支持原生音频" + ("，适合有台词镜头" if has_dialogue else ""),
                            "fallback": "kling_v1_5",
                            "fallback_reason": "可灵v1.5擅长环境氛围与长镜头，作为备选",
                        },
                        "risk_notes": "低风险" if not has_dialogue else "台词口型同步可能不准，建议用近景弱化口型问题",
                        "fallback_motion": f"固定机位极慢速推进，{duration}秒，电影感运动流畅自然物理胶片质感",
                        "image_prompt_revision": "",
                        "revised_image_prompt": "",
                        "videographer_note": "LLM 生成失败，使用降级运动提示词（已从编剧补齐角色数据）",
                        "dialogue": dialogue,
                        "character_expression": expr,
                        "character_action": action,
                        "character_emotion": emotion,
                    })

        return {
            "shots": all_video_shots,
            "global_video_style_suffix": "电影感运动，流畅，自然物理，胶片质感，高细节",
            "pacing_note": (
                f"全片情绪曲线：{' → '.join(emotional_arc) if emotional_arc else '自然节奏'}。"
                f"前段建议多镜头运动与环境氛围，慢速；"
                f"中段增加人物动作，速度提升；"
                f"结尾回归环境氛围与长空镜，留白。"
            ),
        }

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
    #  分步 Markdown 输出
    # ──────────────────────────────────────────────────────
    @staticmethod
    def _build_step_markdown(result: Dict[str, Any], step: int) -> str:
        """根据当前步骤，只输出该步骤的 Markdown 片段。"""
        parts: list[str] = []
        next_hint = result.get("_pipeline_next_hint", "")
        total = result.get("_pipeline_total", 5)

        # 进度条
        progress_bar = "▶" * step + "○" * (total - step)
        parts.append(f"## 🎬 流水线进度 [{progress_bar}] （第 {step}/{total} 步）\n")

        dn = result.get("director_notes") or {}
        sp = result.get("screenplay") or {}
        shp = result.get("shot_prompts") or {}
        vp = result.get("video_prompts") or {}

        if step == 1:
            # ── 导演手记 ──
            parts.append("### 🎬 导演手记\n")
            if dn.get("theme"):
                parts.append(f"**主题**：{dn['theme']}\n")
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

            three_act = dn.get("three_act", {})
            if three_act:
                parts.append("\n**三幕结构**\n")
                parts.append(f"- 起：{three_act.get('setup', '')}\n")
                parts.append(f"- 承/转：{three_act.get('conflict', '')}\n")
                parts.append(f"- 合：{three_act.get('resolve', '')}\n")

            characters = dn.get("characters", [])
            if characters:
                parts.append("\n**角色卡**\n")
                for ch in characters:
                    parts.append(f"- **{ch.get('name', '')}**（{ch.get('role', '')}）"
                                 f"｜{ch.get('age', '')}｜{ch.get('appearance', '')}\n")
                    if ch.get("base_expression"):
                        parts.append(f"  表情基线：{ch['base_expression']}\n")
                    if ch.get("emotional_range"):
                        parts.append(f"  情绪范围：{'、'.join(ch['emotional_range'])}\n")
                    if ch.get("speech_style"):
                        parts.append(f"  说话风格：{ch['speech_style']}\n")
                    if ch.get("personality"):
                        parts.append(f"  性格：{ch['personality']}\n")
                    if ch.get("arc"):
                        parts.append(f"  弧线：{ch['arc']}\n")

        elif step == 2:
            # ── 编剧脚本 ──
            parts.append("### 📝 编剧脚本\n")
            if sp.get("title"):
                parts.append(f"**片名**：{sp['title']}\n")
            if sp.get("logline"):
                parts.append(f"**故事梗概**：{sp['logline']}\n")
            if sp.get("genre"):
                parts.append(f"**类型**：{sp['genre']}\n")
            if sp.get("total_duration_estimate"):
                parts.append(f"**预估时长**：{sp['total_duration_estimate']}s\n")

            scenes = sp.get("scenes", [])
            for sc in scenes:
                parts.append(f"\n#### {sc.get('scene_id', '')} {sc.get('location', '')}\n")
                if sc.get("time"):
                    parts.append(f"- 时间：{sc['time']}\n")
                if sc.get("mood"):
                    parts.append(f"- 情绪：{sc['mood']}\n")
                if sc.get("action"):
                    parts.append(f"- 事件：{sc['action']}\n")
                parts.append("\n| 镜头 | 景别 | 运镜 | 时长 | 画面描述 | 台词 | 表情 | 情绪 | 转场 |\n")
                parts.append("|------|------|------|------|----------|------|------|------|------|\n")
                for shot in sc.get("shots", []):
                    desc = shot.get("desc", "")[:30]
                    dialogue_list = shot.get("dialogue", [])
                    dialogue_str = "；".join(
                        f"{d.get('speaker', '')}：{d.get('text', '')}" for d in dialogue_list
                    ) if dialogue_list else ""
                    expr_dict = shot.get("character_expression", {})
                    expr_str = "；".join(f"{k}：{v}" for k, v in expr_dict.items()) if expr_dict else ""
                    emo_dict = shot.get("character_emotion", {})
                    emo_str = "、".join(emo_dict.values()) if emo_dict else ""
                    parts.append(
                        f"| {shot.get('shot_id', '')} | {shot.get('shot_type', '')} | "
                        f"{shot.get('camera_move', '')} | {shot.get('duration', '')}s | "
                        f"{desc} | {dialogue_str[:20]} | {expr_str[:20]} | {emo_str} | {shot.get('transition_out', '')} |\n"
                    )

            # 动作详情
            has_actions = any(
                shot.get("character_action")
                for sc in scenes for shot in sc.get("shots", [])
            )
            if has_actions:
                parts.append("\n**角色动作详情**\n")
                for sc in scenes:
                    for shot in sc.get("shots", []):
                        action_dict = shot.get("character_action", {})
                        if action_dict:
                            action_str = "；".join(f"{k}：{v}" for k, v in action_dict.items())
                            parts.append(f"- **{shot.get('shot_id', '')}**：{action_str}\n")

            voiceover = sp.get("voiceover", [])
            if voiceover:
                parts.append("\n**旁白**\n")
                for vo in voiceover:
                    parts.append(f"- **{vo.get('shot_id', '')}**（{vo.get('emotion', '')}）："
                                 f"\"{vo.get('text', '')}\"\n")

        elif step == 3:
            # ── 分镜画面提示词 ──
            parts.append("### 🎨 分镜画面提示词\n")
            anchors = shp.get("visual_anchors", [])
            if anchors:
                parts.append("**视觉锚点**\n")
                parts.append("| 锚点ID | 类型 | 名称 | 参考描述 |\n")
                parts.append("|--------|------|------|----------|\n")
                for a in anchors:
                    desc = a.get("ref_desc", "")[:60]
                    parts.append(
                        f"| {a.get('anchor_id', '')} | {a.get('kind', '')} | "
                        f"{a.get('ref_name', '')} | {desc} |\n"
                    )
                parts.append("")

            shots = shp.get("shots", [])
            for shot in shots:
                parts.append(f"\n#### {shot.get('shot_id', '')} 画面提示词\n")
                parts.append(f"**中文描述**：{shot.get('desc_cn', '')}\n")
                # 角色四维度
                dialogue_list = shot.get("dialogue", [])
                if dialogue_list:
                    dialogue_str = "；".join(
                        f"{d.get('speaker', '')}：\"{d.get('text', '')}\"（{d.get('emotion', '')}）" for d in dialogue_list
                    )
                    parts.append(f"**💬 台词**：{dialogue_str}\n")
                expr_dict = shot.get("character_expression", {})
                if expr_dict:
                    expr_str = "；".join(f"{k}：{v}" for k, v in expr_dict.items())
                    parts.append(f"**😊 表情**：{expr_str}\n")
                action_dict = shot.get("character_action", {})
                if action_dict:
                    action_str = "；".join(f"{k}：{v}" for k, v in action_dict.items())
                    parts.append(f"**🏃 动作**：{action_str}\n")
                emo_dict = shot.get("character_emotion", {})
                if emo_dict:
                    emo_str = "、".join(emo_dict.values())
                    parts.append(f"**💜 情绪**：{emo_str}\n")
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

        elif step == 4:
            # ── 视频运动提示词 ──
            parts.append("### 🎥 视频运动提示词\n")
            if vp.get("pacing_note"):
                parts.append(f"**全片节奏建议**：{vp['pacing_note']}\n")

            vp_shots = vp.get("shots", [])
            for shot in vp_shots:
                parts.append(f"\n#### {shot.get('shot_id', '')} 运动提示词\n")
                # 角色四维度
                dialogue_list = shot.get("dialogue", [])
                if dialogue_list:
                    dialogue_str = "；".join(
                        f"{d.get('speaker', '')}：\"{d.get('text', '')}\"（{d.get('emotion', '')}）" for d in dialogue_list
                    )
                    parts.append(f"**💬 台词**：{dialogue_str}\n")
                expr_dict = shot.get("character_expression", {})
                if expr_dict:
                    expr_str = "；".join(f"{k}：{v}" for k, v in expr_dict.items())
                    parts.append(f"**😊 表情**：{expr_str}\n")
                action_dict = shot.get("character_action", {})
                if action_dict:
                    action_str = "；".join(f"{k}：{v}" for k, v in action_dict.items())
                    parts.append(f"**🏃 动作**：{action_str}\n")
                emo_dict = shot.get("character_emotion", {})
                if emo_dict:
                    emo_str = "、".join(emo_dict.values())
                    parts.append(f"**💜 情绪**：{emo_str}\n")
                parts.append(f"**motion_prompt**：\n```\n{shot.get('motion_prompt', '')}\n```\n")
                parts.append(f"**运动类型**：{shot.get('motion_type', '')}\n")
                mp = shot.get("motion_params", {})
                if mp:
                    parts.append(f"**运动参数**：{mp.get('camera_move', '')} | "
                                 f"{mp.get('camera_speed', '')} | "
                                 f"主体:{mp.get('subject_motion', '')} | "
                                 f"表情:{mp.get('expression_motion', '无')} | "
                                 f"{mp.get('duration', '')}s\n")
                    if mp.get("subject_motion_desc"):
                        parts.append(f"**动作描述**：{mp['subject_motion_desc']}\n")
                ms = shot.get("model_suggestion", {})
                if ms:
                    parts.append(f"**推荐模型**：{ms.get('primary', '')}（{ms.get('reason', '')}）\n")
                    parts.append(f"**备选模型**：{ms.get('fallback', '')}（{ms.get('fallback_reason', '')}）\n")
                if shot.get("risk_notes"):
                    parts.append(f"**风险提示**：{shot['risk_notes']}\n")
                if shot.get("fallback_motion"):
                    parts.append(f"**兜底方案**：{shot['fallback_motion']}\n")

        # ── 提示用户继续 ──
        parts.append(f"\n---\n")
        parts.append(f"📍 {next_hint}\n")

        return "\n".join(parts)

    # ──────────────────────────────────────────────────────
    #  完整 Markdown 输出
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
                if ch.get("base_expression"):
                    parts.append(f"  表情基线：{ch['base_expression']}\n")
                if ch.get("emotional_range"):
                    parts.append(f"  情绪范围：{'、'.join(ch['emotional_range'])}\n")
                if ch.get("speech_style"):
                    parts.append(f"  说话风格：{ch['speech_style']}\n")
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
            parts.append("\n| 镜头 | 景别 | 运镜 | 时长 | 画面描述 | 台词 | 表情 | 情绪 | 转场 |\n")
            parts.append("|------|------|------|------|----------|------|------|------|------|\n")
            for shot in sc.get("shots", []):
                desc = shot.get("desc", "")[:30]
                dialogue_list = shot.get("dialogue", [])
                dialogue_str = "；".join(
                    f"{d.get('speaker', '')}：{d.get('text', '')}" for d in dialogue_list
                ) if dialogue_list else ""
                expr_dict = shot.get("character_expression", {})
                expr_str = "；".join(f"{k}：{v}" for k, v in expr_dict.items()) if expr_dict else ""
                emo_dict = shot.get("character_emotion", {})
                emo_str = "、".join(emo_dict.values()) if emo_dict else ""
                parts.append(
                    f"| {shot.get('shot_id', '')} | {shot.get('shot_type', '')} | "
                    f"{shot.get('camera_move', '')} | {shot.get('duration', '')}s | "
                    f"{desc} | {dialogue_str[:20]} | {expr_str[:20]} | {emo_str} | {shot.get('transition_out', '')} |\n"
                )

        # 角色动作详情
        has_actions = any(
            shot.get("character_action")
            for sc in scenes for shot in sc.get("shots", [])
        )
        if has_actions:
            parts.append("\n### 角色动作详情\n")
            for sc in scenes:
                for shot in sc.get("shots", []):
                    action_dict = shot.get("character_action", {})
                    if action_dict:
                        action_str = "；".join(f"{k}：{v}" for k, v in action_dict.items())
                        parts.append(f"- **{shot.get('shot_id', '')}**：{action_str}\n")

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
            # 角色四维度
            dialogue_list = shot.get("dialogue", [])
            if dialogue_list:
                dialogue_str = "；".join(
                    f"{d.get('speaker', '')}：\"{d.get('text', '')}\"（{d.get('emotion', '')}）" for d in dialogue_list
                )
                parts.append(f"**💬 台词**：{dialogue_str}\n")
            expr_dict = shot.get("character_expression", {})
            if expr_dict:
                expr_str = "；".join(f"{k}：{v}" for k, v in expr_dict.items())
                parts.append(f"**😊 表情**：{expr_str}\n")
            action_dict = shot.get("character_action", {})
            if action_dict:
                action_str = "；".join(f"{k}：{v}" for k, v in action_dict.items())
                parts.append(f"**🏃 动作**：{action_str}\n")
            emo_dict = shot.get("character_emotion", {})
            if emo_dict:
                emo_str = "、".join(emo_dict.values())
                parts.append(f"**💜 情绪**：{emo_str}\n")
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
            # 角色四维度
            dialogue_list = shot.get("dialogue", [])
            if dialogue_list:
                dialogue_str = "；".join(
                    f"{d.get('speaker', '')}：\"{d.get('text', '')}\"（{d.get('emotion', '')}）" for d in dialogue_list
                )
                parts.append(f"**💬 台词**：{dialogue_str}\n")
            expr_dict = shot.get("character_expression", {})
            if expr_dict:
                expr_str = "；".join(f"{k}：{v}" for k, v in expr_dict.items())
                parts.append(f"**😊 表情**：{expr_str}\n")
            action_dict = shot.get("character_action", {})
            if action_dict:
                action_str = "；".join(f"{k}：{v}" for k, v in action_dict.items())
                parts.append(f"**🏃 动作**：{action_str}\n")
            emo_dict = shot.get("character_emotion", {})
            if emo_dict:
                emo_str = "、".join(emo_dict.values())
                parts.append(f"**💜 情绪**：{emo_str}\n")
            parts.append(f"**motion_prompt**：\n```\n{shot.get('motion_prompt', '')}\n```\n")
            parts.append(f"**运动类型**：{shot.get('motion_type', '')}\n")
            mp = shot.get("motion_params", {})
            if mp:
                parts.append(f"**运动参数**：{mp.get('camera_move', '')} | "
                             f"{mp.get('camera_speed', '')} | "
                             f"主体:{mp.get('subject_motion', '')} | "
                             f"表情:{mp.get('expression_motion', '无')} | "
                             f"{mp.get('duration', '')}s\n")
                if mp.get("subject_motion_desc"):
                    parts.append(f"**动作描述**：{mp['subject_motion_desc']}\n")
            ms = shot.get("model_suggestion", {})
            if ms:
                parts.append(f"**推荐模型**：{ms.get('primary', '')}（{ms.get('reason', '')}）\n")
                parts.append(f"**备选模型**：{ms.get('fallback', '')}（{ms.get('fallback_reason', '')}）\n")
            if shot.get("risk_notes"):
                parts.append(f"**风险提示**：{shot['risk_notes']}\n")
            if shot.get("fallback_motion"):
                parts.append(f"**兜底方案**：{shot['fallback_motion']}\n")
            if shot.get("videographer_note"):
                parts.append(f"**视频师备注**：{shot['videographer_note']}\n")
            if shot.get("image_prompt_revision"):
                parts.append(f"**画面修订**：{shot['image_prompt_revision']}\n")
                if shot.get("revised_image_prompt"):
                    parts.append(f"**修订后提示词**：\n```\n{shot['revised_image_prompt']}\n```\n")

        return "\n".join(parts)
