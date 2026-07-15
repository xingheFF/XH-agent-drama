"""② 编剧角色输出：Screenplay

职责：拿着 DirectorNotes，展开为可拍摄的脚本 + 镜头清单。
"""

from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator


# —— 镜头景别 ——
ShotType = Literal["大全景", "全景", "中景", "近景", "特写", "大特写"]

# —— 运镜方式 ——
CameraMove = Literal[
    "固定",        # static
    "推",          # dolly in / zoom in
    "拉",          # dolly out / zoom out
    "摇",          # pan
    "移",          # tracking
    "升降",        # crane / boom
    "手持",        # handheld
    "跟拍",        # follow
    "航拍",        # drone
    "环绕",        # orbit
]

# —— 转场 ——
Transition = Literal["cut", "crossfade", "wipe", "dissolve", "whip_pan", "match_cut"]


class Shot(BaseModel):
    """单个镜头单元 —— 编剧产出，分镜师会在此基础上扩展"""
    shot_id: str = Field(..., description="镜头编号，如 'S1-01'，格式 {场景号}-{镜头序号}")
    scene_id: str = Field(..., description="所属场景编号，如 'S1'")
    shot_type: ShotType = Field(..., description="景别")
    camera_move: CameraMove = Field("固定", description="运镜方式")
    duration: float = Field(..., description="时长（秒）", ge=1, le=15)
    desc: str = Field(..., description="镜头画面描述（中文，2-3 句）")
    purpose: str = Field(..., description="该镜头的叙事功能，如 '交代环境'、'强化情绪'")
    transition_out: Transition = Field("cut", description="与下一镜头的转场方式")
    characters_in_shot: list[str] = Field(
        default_factory=list,
        description="本镜头出现的角色名（对应 DirectorNotes.characters[].name）",
    )
    location_in_shot: str = Field("", description="本镜头取景地（对应 DirectorNotes.location 或其细分）")

    @field_validator("shot_id")
    @classmethod
    def _validate_shot_id(cls, v: str) -> str:
        if "-" not in v:
            raise ValueError(f"shot_id 必须含 '-'，如 'S1-01'，got {v!r}")
        return v


class Scene(BaseModel):
    """一个场景 —— 含若干镜头"""
    scene_id: str = Field(..., description="场景编号，如 'S1'")
    location: str = Field(..., description="场景地点")
    time: str = Field("", description="时间设定，如 '清晨 06:30'")
    mood: str = Field(..., description="场景情绪基调，如 '宁静、微凉'")
    action: str = Field(..., description="场景总动作/事件（1-2 句）")
    purpose: str = Field(..., description="该场景在叙事中的功能")
    shots: list[Shot] = Field(..., description="本场景的镜头列表", min_length=1)


class VoiceoverSegment(BaseModel):
    """旁白片段 —— 按镜头切分"""
    shot_id: str = Field(..., description="对应镜头 shot_id")
    text: str = Field(..., description="旁白文本（中文）")
    emotion: str = Field("叙述", description="旁白情绪，如 '平静'、'激昂'")
    speed_preset: Literal["slow", "normal", "fast"] = Field(
        "normal", description="语速档位"
    )


class SubtitleEntry(BaseModel):
    """字幕条目 —— 片头/片尾/关键节点"""
    timing: Literal["opening", "closing", "scene_intro", "caption"] = Field(
        ..., description="字幕时机类型"
    )
    shot_id: str = Field("", description="关联镜头（如有）")
    text: str = Field(..., description="字幕文本")
    style_hint: str = Field("", description="样式提示，如 '居中大字淡入'")


class Screenplay(BaseModel):
    """完整脚本 —— 编剧角色产出"""

    title: str = Field(..., description="片名")
    logline: str = Field(..., description="一句话故事梗概")
    genre: str = Field("文旅剧情短片", description="类型")
    total_duration_estimate: float = Field(
        ..., description="预估总时长（秒）= 所有 shot duration 之和"
    )

    scenes: list[Scene] = Field(
        ..., description="场景列表（建议 3-6 个场景）", min_length=1
    )

    voiceover: list[VoiceoverSegment] = Field(
        default_factory=list,
        description="旁白片段，按镜头切分；无旁白镜头可省略",
    )

    subtitles: list[SubtitleEntry] = Field(
        default_factory=list,
        description="字幕列表（片名/片尾/关键节点）",
    )

    screenwriter_note: str = Field(
        "", description="编剧给下游的备注，如 'S2 情绪转折建议用 match_cut'"
    )

    # —— 校验 ——
    @model_validator(mode="after")
    def _validate_durations(self) -> "Screenplay":
        total = sum(s.duration for sc in self.scenes for s in sc.shots)
        # 同步 total_duration_estimate（允许 LLM 给的不准，以实际为准）
        if abs(total - self.total_duration_estimate) > 0.5:
            self.total_duration_estimate = total
        return self

    @model_validator(mode="after")
    def _validate_shot_ids_unique(self) -> "Screenplay":
        ids = [s.shot_id for sc in self.scenes for s in sc.shots]
        if len(ids) != len(set(ids)):
            raise ValueError(f"shot_id 存在重复: {ids}")
        return self

    @model_validator(mode="after")
    def _validate_scene_ids(self) -> "Screenplay":
        for sc in self.scenes:
            for s in sc.shots:
                if s.scene_id != sc.scene_id:
                    raise ValueError(
                        f"shot {s.shot_id} 的 scene_id={s.scene_id!r} "
                        f"与所属场景 {sc.scene_id!r} 不一致"
                    )
        return self
