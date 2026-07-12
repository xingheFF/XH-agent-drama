import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ─── 全局参数默认值（与 short_drama.py 的 DEFAULT_GLOBAL_PARAMS 对齐）──
DEFAULT_GLOBAL_PARAMS: Dict[str, str] = {
    "目标画幅": "9:16竖屏",
    "单集时长": "60-90秒",
    "目标平台": "抖音",
    "渲染基准": "UE5离线渲染、PBR物理材质、写实电影感",
    "镜头基准": "35mm定焦镜头，f/1.8光圈，柯达5207胶片质感",
}


@dataclass
class SkillParam:
    name: str
    param_type: str
    options: Optional[List[str]] = None
    default: Any = None
    required: bool = False
    description: str = ""


@dataclass
class SkillInfo:
    skill_id: str
    skill_name: str
    tags: List[str]
    supported_outputs: List[str]
    version: str
    category: str
    params: List[SkillParam]


@dataclass
class SkillOutput:
    skill_id: str
    status: str  # success | failed
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    model_used: Optional[str] = None


class BaseSkill(ABC):
    info: SkillInfo
    system_prompt: str = ""

    @abstractmethod
    async def run(
        self,
        user_input: str,
        params: Optional[Dict[str, Any]] = None,
        global_params: Optional[Dict[str, Any]] = None,
    ) -> SkillOutput:
        """
        执行 Skill。

        :param user_input: 用户的自然语言输入
        :param params: 前端传入的参数（已合并默认值）
        :param global_params: 大脑注入的全局参数（画幅、渲染基准、镜头基准等），
                              用于渲染 system_prompt 中的 {{占位符}}
        """
        raise NotImplementedError

    def merge_params(self, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        for p in self.info.params:
            merged[p.name] = p.default
        if params:
            for k, v in params.items():
                if v is not None:
                    merged[k] = v
        return merged

    @staticmethod
    def _render_global_params(prompt: str, params: Optional[Dict[str, Any]]) -> str:
        """将 system_prompt 中的 {{占位符}} 替换为全局参数。

        与 short_drama.py 的 _render_global_params 逻辑一致：
        合并默认参数 + 用户传入参数，替换占位符后清除未匹配的 {{...}}。
        """
        rendered = prompt or ""
        gp = {**DEFAULT_GLOBAL_PARAMS, **(params or {})}
        for key, value in gp.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
        # 清除所有剩余未解析的 {{...}} 占位符
        rendered = re.sub(r"\{\{[^}]+\}\}", "", rendered)
        return rendered

    def describe(self) -> Dict[str, Any]:
        return {
            "skill_id": self.info.skill_id,
            "skill_name": self.info.skill_name,
            "tags": self.info.tags,
            "supported_outputs": self.info.supported_outputs,
            "version": self.info.version,
            "category": self.info.category,
            "params": [
                {
                    "name": p.name,
                    "type": p.param_type,
                    "options": p.options,
                    "default": p.default,
                    "required": p.required,
                    "description": p.description,
                }
                for p in self.info.params
            ],
        }
