"""④ 视频师角色输出：VideoPrompts

职责：
1. 整合上下文（导演重点 + 编剧脚本 + 分镜师画面提示词）。
2. 为每个镜头输出运动提示词（图生视频/文生视频用）。
3. 按镜头 motion_type 给出视频模型选型建议。
4. 拥有对画面提示词的"修订权"——若某元素动起来会很怪，建议改。
"""

from typing import Literal
from pydantic import BaseModel, Field, field_validator


# —— 运动类型 ——
MotionType = Literal[
    "camera_movement",         # 镜头运动为主
    "character_action",        # 人物动作为主
    "environment_atmosphere",  # 环境氛围为主
    "still_ken_burns",         # 静态图缓慢推拉（兜底）
]

# —— 镜头运动细分 ——
CameraMove = Literal[
    "static",
    "dolly_in",
    "dolly_out",
    "zoom_in",
    "zoom_out",
    "pan_left",
    "pan_right",
    "tilt_up",
    "tilt_down",
    "tracking",
    "crane_up",
    "crane_down",
    "handheld",
    "follow",
    "drone_aerial",
    "orbit",
    "parallax",
]

# —— 主体运动强度 ——
SubjectMotionLevel = Literal["none", "subtle", "moderate", "active", "intense"]

# —— 环境氛围运动 ——
EnvironmentalMotion = Literal[
    "none",
    "mist_drift",
    "wind_in_leaves",
    "water_ripple",
    "rain",
    "snow",
    "dust_particles",
    "smoke_rise",
    "cloud_move",
    "light_flicker",
    "candle_flicker",
    "fire_flicker",
]


class MotionParams(BaseModel):
    """运动参数细分"""

    camera_move: CameraMove = Field(..., description="镜头运动方式")
    camera_speed: Literal["very_slow", "slow", "medium", "fast"] = Field(
        "slow", description="镜头运动速度"
    )
    subject_motion: SubjectMotionLevel = Field(
        "none", description="主体（人物/物体）运动强度"
    )
    subject_motion_desc: str = Field(
        "", description="主体运动具体描述（英文），如 'young man walks slowly along alley'"
    )
    environmental_motion: list[EnvironmentalMotion] = Field(
        default_factory=list,
        description="环境氛围运动列表，如 ['mist_drift','wind_in_leaves']",
    )
    environmental_direction: str = Field(
        "",
        description="环境运动方向描述，如 'mist drifts left to right at mid-frame'",
    )
    particle_effect: str = Field(
        "", description="粒子特效描述（英文），如 'subtle dust motes in light shafts'"
    )
    duration: float = Field(
        ..., description="视频时长（秒），建议等于编剧该镜头 duration", ge=1, le=15
    )


class ModelSuggestion(BaseModel):
    """视频模型选型建议"""

    primary: str = Field(..., description="主推模型名，对应 config video_models 的 key")
    reason: str = Field(..., description="主推理由（中文，1-2 句）")
    fallback: str = Field(..., description="备选模型名")
    fallback_reason: str = Field(..., description="备选理由（中文，1-2 句）")


class VideoShotPrompt(BaseModel):
    """单个镜头的视频提示词 —— 视频师产出"""

    model_config = {"protected_namespaces": ()}

    shot_id: str = Field(..., description="对应编剧 Shot.shot_id")

    # —— 运动提示词（英文，给图生视频模型）——
    motion_prompt: str = Field(
        ...,
        description="图生视频运动提示词（英文）。"
        "需明确：镜头运动 + 主体运动 + 环境氛围运动 + 时长。"
        "公式：camera action + subject action + environmental motion + duration + style words.",
    )

    # —— 运动分类 ——
    motion_type: MotionType = Field(
        ..., description="运动类型分类，决定视频模型选型"
    )

    # —— 运动参数 ——
    motion_params: MotionParams = Field(..., description="运动参数细分")

    # —— 模型选型 ——
    model_suggestion: ModelSuggestion = Field(
        ..., description="视频模型选型建议"
    )

    # —— 风险提示 ——
    risk_notes: str = Field(
        "",
        description="生成风险提示（中文），如 '鸟群运动轨迹难控制，失败可降级为 Ken Burns'",
    )

    # —— 兜底方案 ——
    fallback_motion: str = Field(
        "static, very slow ken burns zoom-in",
        description="若视频生成失败的兜底运动描述（英文）",
    )

    # —— 对画面提示词的修订权 ——
    image_prompt_revision: str = Field(
        "",
        description="若需修订分镜师的 image_prompt，写出修订说明（中文）。空字符串表示不修订。",
    )
    revised_image_prompt: str = Field(
        "",
        description="修订后的 image_prompt（英文）。仅当 image_prompt_revision 非空时填写。",
    )

    # —— 视频师备注 ——
    videographer_note: str = Field("", description="视频师给用户/合成的备注")

    @field_validator("motion_prompt")
    @classmethod
    def _validate_motion_prompt_len(cls, v: str) -> str:
        if len(v) < 20:
            raise ValueError(
                f"motion_prompt 过短（{len(v)} 字），需含完整运动描述"
            )
        return v

    @field_validator("revised_image_prompt")
    @classmethod
    def _validate_revision_consistency(cls, v: str) -> str:
        # 如果有修订后的 prompt，但 revision 说明为空，是矛盾的
        # 这里只做软提示，不强制
        return v


class VideoPrompts(BaseModel):
    """视频师总输出 —— 逐镜头运动提示词 + 选型"""

    shots: list[VideoShotPrompt] = Field(
        ..., description="逐镜头视频提示词列表", min_length=1
    )

    # —— 全局视频风格词 ——
    global_video_style_suffix: str = Field(
        "cinematic motion, smooth, natural physics, film look",
        description="全局视频风格后缀词，拼到每个 motion_prompt",
    )

    # —— 全片节奏建议 ——
    pacing_note: str = Field(
        "",
        description="全片节奏建议（中文），如 '前段缓慢铺垫，中段加快，结尾留白'",
    )

    @field_validator("shots")
    @classmethod
    def _validate_shot_ids_unique(
        cls, v: list[VideoShotPrompt]
    ) -> list[VideoShotPrompt]:
        ids = [s.shot_id for s in v]
        if len(ids) != len(set(ids)):
            raise ValueError(f"VideoShotPrompt.shot_id 存在重复: {ids}")
        return v
