"""文旅剧情宣传片提示词工坊

用户输入剧本/灵感 → 导演提炼 → 编剧写脚本分镜 → 分镜师出画面提示词 → 视频师出运动提示词 → 交付成套提示词包
"""

from .config import Config
from .models import (
    DirectorNotes,
    FinalPackage,
    Screenplay,
    ShotPrompts,
    VideoPrompts,
)
from .pipeline import (
    PIPELINE_VERSION,
    rerun_role,
    run_pipeline,
    run_quality_check,
)

__version__ = PIPELINE_VERSION

__all__ = [
    "Config",
    "DirectorNotes",
    "Screenplay",
    "ShotPrompts",
    "VideoPrompts",
    "FinalPackage",
    "run_pipeline",
    "rerun_role",
    "run_quality_check",
    "PIPELINE_VERSION",
    "__version__",
]
