"""最终合并包：FinalPackage

把四个角色的输出合并成单一对象，便于序列化和下游消费。
"""

from pydantic import BaseModel, Field

from .director_notes import DirectorNotes
from .screenplay import Screenplay
from .shot_prompts import ShotPrompts
from .video_prompts import VideoPrompts


class FinalPackage(BaseModel):
    """全流程产物合并包"""

    project_id: str = Field(..., description="项目编号，如 'proj_001'")
    created_at: str = Field(..., description="创建时间 ISO8601")

    # —— 四个角色的输出 ——
    director_notes: DirectorNotes = Field(..., description="① 导演手记")
    screenplay: Screenplay = Field(..., description="② 编剧脚本+分镜清单")
    shot_prompts: ShotPrompts = Field(..., description="③ 分镜师画面提示词")
    video_prompts: VideoPrompts = Field(..., description="④ 视频师运动提示词")

    # —— 质检结果 ——
    quality_report: dict = Field(
        default_factory=dict,
        description="质检报告（时长/锚点/旁白/镜头数/情绪曲线）",
    )

    # —— 元信息 ——
    pipeline_version: str = Field("0.1.0", description="流水线版本")
    notes: str = Field("", description="整体备注")
