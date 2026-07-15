"""③ 分镜师角色输出：ShotPrompts

职责：
1. 先建立"视觉一致性锚点"（角色锚点 + 场景锚点）。
2. 把编剧的 Shot 逐个翻译成画面提示词（文生图用），含负向提示词、镜头参数、构图指引。
3. 标注每个镜头用了哪些锚点，确保跨镜头一致。
"""

from typing import Literal
from pydantic import BaseModel, Field, field_validator


# —— 光线类型 ——
LightingType = Literal[
    "golden_hour",     # 黄金时刻
    "blue_hour",       # 蓝调时刻
    "overcast",        # 阴天柔光
    "hard_daylight",   # 烈日硬光
    "interior_warm",   # 室内暖光
    "interior_cool",   # 室内冷光
    "backlight",       # 逆光
    "candlelight",     # 烛光
    "neon",            # 霓虹
    "moonlight",       # 月光
]

# —— 构图法 ——
CompositionRule = Literal[
    "rule_of_thirds",
    "golden_ratio",
    "symmetry",
    "leading_lines",
    "frame_within_frame",
    "negative_space",
    "center_composition",
    "diagonal",
]

# —— 锚点类型 ——
AnchorKind = Literal["character", "location", "prop"]


class VisualAnchor(BaseModel):
    """视觉一致性锚点定义 —— 分镜师首先要建这些"""

    anchor_id: str = Field(
        ..., description="锚点编号，如 'char_001'、'loc_001'、'prop_001'"
    )
    kind: AnchorKind = Field(..., description="锚点类型")
    ref_name: str = Field(..., description="对应名称，如 '阿远'、'皖南老屋'、'老钥匙'")
    ref_desc: str = Field(
        ...,
        description="英文参考描述，用于在 image_prompt 中保持一致。"
        "人物锚点需含：人种、性别、年龄段、发型、体型、服装、面部特征。",
    )
    consistency_tags: str = Field(
        ...,
        description="一致性提醒词，会拼到 image_prompt 里，如 'same person, consistent facial features'",
    )
    negative_consistency: str = Field(
        ...,
        description="负向一致性提醒，如 'inconsistent face, different person'",
    )

    @field_validator("anchor_id")
    @classmethod
    def _validate_anchor_id(cls, v: str) -> str:
        prefix = v.split("_")[0]
        if prefix not in ("char", "loc", "prop"):
            raise ValueError(
                f"anchor_id 必须以 char_/loc_/prop_ 开头，got {v!r}"
            )
        return v


class CameraParams(BaseModel):
    """镜头参数 —— 给即梦/可灵这类带参数控制的工具用"""

    shot_size: Literal[
        "extreme_wide",  # 大全景
        "wide",          # 全景
        "medium",        # 中景
        "medium_close",  # 近景
        "close_up",      # 特写
        "extreme_close", # 大特写
    ] = Field(..., description="景别")
    lens: str = Field("35mm", description="镜头焦段，如 '35mm'、'85mm macro'、'anamorphic 40mm'")
    angle: str = Field(
        "eye_level",
        description="机位角度，如 'eye_level'、'high_angle'、'low_angle'、'dutch_tilt'",
    )
    lighting: LightingType = Field(..., description="光线类型")
    lighting_direction: Literal[
        "front", "side", "back", "top", "bottom", "mixed"
    ] = Field("mixed", description="光源方向")
    color_grade: str = Field(
        "warm, slightly desaturated",
        description="调色描述，如 'warm, slightly desaturated'、'cool teal shadows'",
    )
    depth_of_field: Literal["shallow", "medium", "deep"] = Field(
        "medium", description="景深"
    )
    film_stock_hint: str = Field(
        "",
        description="胶片/质感暗示，如 'Kodak Portra 400 grain'、'digital clean'",
    )


class ShotPrompt(BaseModel):
    """单个镜头的画面提示词 —— 分镜师产出"""

    shot_id: str = Field(..., description="对应编剧 Shot.shot_id")

    # —— 中文画面描述（给用户看）——
    desc_cn: str = Field(..., description="中文画面描述（2-3 句）")

    # —— 英文提示词 ——
    image_prompt: str = Field(
        ...,
        description="完整文生图提示词（英文）。"
        "公式：画面主体 + 环境/场景 + 光线 + 色调 + 镜头语言 + 风格词 + 质感词 + 一致性锚点词。",
    )
    negative_prompt: str = Field(
        ...,
        description="负向提示词（英文），如 'modern buildings, cars, neon, deformed, text, watermark'",
    )

    # —— 镜头参数 ——
    camera_params: CameraParams = Field(..., description="镜头参数")

    # —— 构图 ——
    composition: str = Field(
        ...,
        description="构图描述（英文），如 'rule of thirds, village massed on lower third, sky and mist in upper two-thirds'",
    )
    composition_rules: list[CompositionRule] = Field(
        default_factory=list,
        description="应用的构图法则列表",
    )

    # —— 锚点引用 ——
    anchors_used: list[str] = Field(
        default_factory=list,
        description="本镜头用到的锚点 anchor_id 列表",
    )

    # —— 参考图（若需 img2img 起手）——
    reference_images: list[str] = Field(
        default_factory=list,
        description="参考图路径列表（用户提供的素材或锚点基准图）",
    )

    # —— 分镜师备注 ——
    storyboard_note: str = Field(
        "",
        description="分镜师给视频师的备注，如 '此镜头光影复杂，运动需保守'",
    )

    @field_validator("image_prompt")
    @classmethod
    def _validate_prompt_len(cls, v: str) -> str:
        if len(v) < 30:
            raise ValueError(
                f"image_prompt 过短（{len(v)} 字），需含完整画面描述"
            )
        return v


class ShotPrompts(BaseModel):
    """分镜师总输出 —— 锚点表 + 逐镜头画面提示词"""

    visual_anchors: list[VisualAnchor] = Field(
        ...,
        description="视觉一致性锚点表（角色 + 场景 + 关键道具），分镜师必须先建这些",
        min_length=1,
    )

    shots: list[ShotPrompt] = Field(
        ..., description="逐镜头画面提示词列表", min_length=1
    )

    # —— 全局风格词（拼到每个 image_prompt 末尾）——
    global_style_suffix: str = Field(
        "cinematic, film grain, highly detailed, 8k",
        description="全局风格后缀词，会自动拼到每个 image_prompt",
    )
    global_negative_suffix: str = Field(
        "lowres, blurry, deformed, ugly, text, watermark, jpeg artifacts",
        description="全局负向后缀词",
    )

    @field_validator("shots")
    @classmethod
    def _validate_shot_ids_unique(cls, v: list[ShotPrompt]) -> list[ShotPrompt]:
        ids = [s.shot_id for s in v]
        if len(ids) != len(set(ids)):
            raise ValueError(f"ShotPrompt.shot_id 存在重复: {ids}")
        return v

    @field_validator("visual_anchors")
    @classmethod
    def _validate_anchor_ids_unique(
        cls, v: list[VisualAnchor]
    ) -> list[VisualAnchor]:
        ids = [a.anchor_id for a in v]
        if len(ids) != len(set(ids)):
            raise ValueError(f"VisualAnchor.anchor_id 存在重复: {ids}")
        return v
