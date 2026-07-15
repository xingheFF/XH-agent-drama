"""① 导演角色输出：DirectorNotes

职责：从用户输入（剧本/灵感）中提炼核心信息。
这是整条流水线的"信息源"，下游所有角色都消费它。
"""

from typing import Literal
from pydantic import BaseModel, Field


class Character(BaseModel):
    """人物卡"""
    name: str = Field(..., description="角色名")
    role: Literal["主角", "配角", "群像"] = Field(..., description="角色定位")
    age: str = Field("", description="年龄段，如 '30岁'、'老年'")
    appearance: str = Field("", description="外貌描述，如 '短发、瘦削、穿橄榄绿外套'")
    personality: str = Field("", description="性格特征，如 '沉默、内敛'")
    arc: str = Field("", description="该角色在本片中的变化弧线（一句话）")


class ThreeAct(BaseModel):
    """起承转合三幕骨架"""
    setup: str = Field(..., description="开篇：交代环境、人物、初始状态")
    conflict: str = Field(..., description="中段：冲突或转折点")
    resolve: str = Field(..., description="结尾：解决或升华")


class DirectorNotes(BaseModel):
    """导演手记 —— 从输入中提炼的核心信息卡"""

    # —— 核心主题 ——
    theme: str = Field(..., description="一句话主题，如 '乡愁与归途'")
    sub_themes: list[str] = Field(default_factory=list, description="次级主题列表")

    # —— 叙事骨架 ——
    story_type: str = Field(..., description="叙事类型，如 '情感散文式'、'故事片式'")
    three_act: ThreeAct = Field(..., description="起承转合三幕")
    emotional_arc: list[str] = Field(
        default_factory=list,
        description="情绪曲线节点，如 ['平静','怅惘','温暖','坚定']",
    )

    # —— 文旅要素 ——
    location: str = Field(..., description="主场景/取景地，如 '皖南古村落'")
    cultural_tags: list[str] = Field(default_factory=list, description="文化标签，如 ['徽派建筑','宗族文化']")
    tourism_selling: list[str] = Field(
        default_factory=list,
        description="文旅卖点，如 ['古建保护','非遗体验','慢生活']",
    )

    # —— 创作约束 ——
    target_duration: int = Field(90, description="目标总时长（秒）", ge=10, le=300)
    aspect_ratio: Literal["9:16", "16:9", "1:1"] = Field("9:16", description="画幅比例")
    resolution: str = Field("1080x1920", description="输出分辨率")
    fps: int = Field(30, description="帧率", ge=24, le=60)
    visual_style: str = Field("胶片质感,暖黄调,逆光,电影感", description="视觉风格词")
    tone: str = Field("克制、留白、诗意", description="全片基调")

    # —— 人物 ——
    characters: list[Character] = Field(
        default_factory=list,
        description="核心人物列表（建议 1-3 人）",
    )

    # —— 关键意象 ——
    key_motifs: list[str] = Field(
        default_factory=list,
        description="关键意象/符号，导演要求反复出现的画面元素，如 ['老钥匙','褪色春联']",
    )

    # —— 导演备注 ——
    director_note: str = Field(
        "",
        description="导演给下游的特别叮嘱，如 '全片不要出现现代物品'、'结尾留 3 秒空镜'",
    )
