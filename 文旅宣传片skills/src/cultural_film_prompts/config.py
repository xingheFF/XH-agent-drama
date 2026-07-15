"""配置加载与类型定义。

从 config.yaml 加载全部参数，代码只读不硬编码。
环境变量 ${VAR} 会自动展开。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# —— 环境变量展开 ——
_ENV_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        return _ENV_RE.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


# —— 各模块配置 dataclass ——


@dataclass
class LLMRoleConfig:
    temperature: float = 0.7
    max_tokens: int = 2000


@dataclass
class LLMConfig:
    base_url: str = "https://api.deepseek.com/v1"
    api_key: str = ""
    model: str = "deepseek-chat"
    structured_output: str = "function_calling"  # function_calling | json_mode
    timeout: int = 120
    max_retries: int = 3
    retry_backoff_base: float = 2.0
    role_temperature: dict[str, float] = field(
        default_factory=lambda: {
            "director": 0.7,
            "screenwriter": 0.85,
            "storyboard": 0.6,
            "videographer": 0.5,
        }
    )
    role_max_tokens: dict[str, int] = field(
        default_factory=lambda: {
            "director": 2000,
            "screenwriter": 4000,
            "storyboard": 6000,
            "videographer": 4000,
        }
    )

    def role_config(self, role: str) -> LLMRoleConfig:
        return LLMRoleConfig(
            temperature=self.role_temperature.get(role, 0.7),
            max_tokens=self.role_max_tokens.get(role, 2000),
        )


@dataclass
class DefaultsConfig:
    target_duration: int = 90
    duration_tolerance: float = 0.10
    aspect_ratio: str = "9:16"
    resolution: str = "1080x1920"
    fps: int = 30
    visual_style: str = "胶片质感,暖黄调,逆光,电影感"
    tone: str = "克制、留白、诗意"
    voiceover_speed: float = 3.5
    subtitle_lang: str = "zh-CN"
    prompt_lang: str = "en"
    desc_lang: str = "zh-CN"


@dataclass
class ShotConfig:
    min_duration: int = 2
    max_duration: int = 6
    shot_type_weights: dict[str, float] = field(default_factory=dict)
    shots_per_scene_min: int = 2
    shots_per_scene_max: int = 5


@dataclass
class VideoModelConfig:
    name: str
    api_hint: str
    strengths: list[str]
    weaknesses: list[str]
    max_duration: int
    cost_tier: int
    priority: int


@dataclass
class OutputConfig:
    dir: str = "output"
    write_markdown: bool = True
    write_prompts_only: bool = True
    write_shot_table: bool = True
    write_final_package: bool = True
    write_stage_json: bool = True


@dataclass
class InputConfig:
    full_script_min_chars: int = 500
    full_script_markers: list[str] = field(default_factory=list)
    inspiration_max_chars: int = 800
    asset_extensions: list[str] = field(default_factory=list)


@dataclass
class VisualAnchorsConfig:
    enforce_character_anchors: bool = True
    enforce_location_anchors: bool = True
    consistency_tag_template: str = "same {kind}, consistent {feature}, {anchor_ref}"
    negative_consistency_template: str = "inconsistent {feature}, different {kind}, style drift"


@dataclass
class SubtitleConfig:
    font_family: str = "Source Han Sans CN"
    font_size_ratio: float = 0.045
    position: str = "bottom"
    margin_ratio: float = 0.08
    stroke_width: int = 2
    stroke_color: str = "black"
    fill_color: str = "white"
    max_chars_per_line: int = 16
    max_lines: int = 2


@dataclass
class VoiceoverConfig:
    default_voice: str = "中年男声,沉稳,略带沙哑,慢语速"
    speed_presets: dict[str, float] = field(
        default_factory=lambda: {"slow": 3.0, "normal": 3.5, "fast": 4.5}
    )
    emotion_speed_map: dict[str, str] = field(default_factory=dict)


@dataclass
class QualityCheckConfig:
    check_duration: bool = True
    check_voiceover_length: bool = True
    voiceover_tolerance: float = 0.20
    check_anchors: bool = True
    check_shot_count: bool = True
    min_shots: int = 5
    check_emotional_arc: bool = True


@dataclass
class LoggingConfig:
    level: str = "INFO"
    dump_llm_io: bool = True
    rich_console: bool = True


# —— 顶层 Config ——


@dataclass
class Config:
    llm: LLMConfig = field(default_factory=LLMConfig)
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
    shot: ShotConfig = field(default_factory=ShotConfig)
    video_models: dict[str, VideoModelConfig] = field(default_factory=dict)
    motion_types: list[str] = field(default_factory=list)
    transitions: list[str] = field(default_factory=list)
    output: OutputConfig = field(default_factory=OutputConfig)
    input: InputConfig = field(default_factory=InputConfig)
    visual_anchors: VisualAnchorsConfig = field(default_factory=VisualAnchorsConfig)
    subtitle: SubtitleConfig = field(default_factory=SubtitleConfig)
    voiceover: VoiceoverConfig = field(default_factory=VoiceoverConfig)
    quality_check: QualityCheckConfig = field(default_factory=QualityCheckConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    # —— 加载 ——
    @classmethod
    def load(cls, path: str | Path) -> "Config":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"配置文件不存在: {p}")
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        raw = _expand_env(raw)
        return cls._from_dict(raw)

    @classmethod
    def _from_dict(cls, d: dict) -> "Config":
        llm_d = d.get("llm", {})
        llm = LLMConfig(
            base_url=llm_d.get("base_url", ""),
            api_key=llm_d.get("api_key", ""),
            model=llm_d.get("model", ""),
            structured_output=llm_d.get("structured_output", "function_calling"),
            timeout=llm_d.get("timeout", 120),
            max_retries=llm_d.get("max_retries", 3),
            retry_backoff_base=llm_d.get("retry_backoff_base", 2.0),
            role_temperature=llm_d.get("role_temperature", {}),
            role_max_tokens=llm_d.get("role_max_tokens", {}),
        )

        def_d = d.get("defaults", {})
        defaults = DefaultsConfig(
            target_duration=def_d.get("target_duration", 90),
            duration_tolerance=def_d.get("duration_tolerance", 0.10),
            aspect_ratio=def_d.get("aspect_ratio", "9:16"),
            resolution=def_d.get("resolution", "1080x1920"),
            fps=def_d.get("fps", 30),
            visual_style=def_d.get("visual_style", ""),
            tone=def_d.get("tone", ""),
            voiceover_speed=def_d.get("voiceover_speed", 3.5),
            subtitle_lang=def_d.get("subtitle_lang", "zh-CN"),
            prompt_lang=def_d.get("prompt_lang", "en"),
            desc_lang=def_d.get("desc_lang", "zh-CN"),
        )

        shot_d = d.get("shot", {})
        shot = ShotConfig(
            min_duration=shot_d.get("min_duration", 2),
            max_duration=shot_d.get("max_duration", 6),
            shot_type_weights=shot_d.get("shot_type_weights", {}),
            shots_per_scene_min=shot_d.get("shots_per_scene_min", 2),
            shots_per_scene_max=shot_d.get("shots_per_scene_max", 5),
        )

        vm_d = d.get("video_models", {})
        video_models = {
            k: VideoModelConfig(
                name=v.get("name", k),
                api_hint=v.get("api_hint", ""),
                strengths=v.get("strengths", []),
                weaknesses=v.get("weaknesses", []),
                max_duration=v.get("max_duration", 10),
                cost_tier=v.get("cost_tier", 1),
                priority=v.get("priority", 99),
            )
            for k, v in vm_d.items()
        }

        out_d = d.get("output", {})
        output = OutputConfig(
            dir=out_d.get("dir", "output"),
            write_markdown=out_d.get("write_markdown", True),
            write_prompts_only=out_d.get("write_prompts_only", True),
            write_shot_table=out_d.get("write_shot_table", True),
            write_final_package=out_d.get("write_final_package", True),
            write_stage_json=out_d.get("write_stage_json", True),
        )

        in_d = d.get("input", {})
        input_cfg = InputConfig(
            full_script_min_chars=in_d.get("full_script_min_chars", 500),
            full_script_markers=in_d.get("full_script_markers", []),
            inspiration_max_chars=in_d.get("inspiration_max_chars", 800),
            asset_extensions=in_d.get("asset_extensions", []),
        )

        va_d = d.get("visual_anchors", {})
        visual_anchors = VisualAnchorsConfig(
            enforce_character_anchors=va_d.get("enforce_character_anchors", True),
            enforce_location_anchors=va_d.get("enforce_location_anchors", True),
            consistency_tag_template=va_d.get(
                "consistency_tag_template", "same {kind}, consistent {feature}"
            ),
            negative_consistency_template=va_d.get(
                "negative_consistency_template", "inconsistent {feature}"
            ),
        )

        sub_d = d.get("subtitle", {})
        subtitle = SubtitleConfig(
            font_family=sub_d.get("font_family", ""),
            font_size_ratio=sub_d.get("font_size_ratio", 0.045),
            position=sub_d.get("position", "bottom"),
            margin_ratio=sub_d.get("margin_ratio", 0.08),
            stroke_width=sub_d.get("stroke_width", 2),
            stroke_color=sub_d.get("stroke_color", "black"),
            fill_color=sub_d.get("fill_color", "white"),
            max_chars_per_line=sub_d.get("max_chars_per_line", 16),
            max_lines=sub_d.get("max_lines", 2),
        )

        vo_d = d.get("voiceover", {})
        voiceover = VoiceoverConfig(
            default_voice=vo_d.get("default_voice", ""),
            speed_presets=vo_d.get("speed_presets", {}),
            emotion_speed_map=vo_d.get("emotion_speed_map", {}),
        )

        qc_d = d.get("quality_check", {})
        quality_check = QualityCheckConfig(
            check_duration=qc_d.get("check_duration", True),
            check_voiceover_length=qc_d.get("check_voiceover_length", True),
            voiceover_tolerance=qc_d.get("voiceover_tolerance", 0.20),
            check_anchors=qc_d.get("check_anchors", True),
            check_shot_count=qc_d.get("check_shot_count", True),
            min_shots=qc_d.get("min_shots", 5),
            check_emotional_arc=qc_d.get("check_emotional_arc", True),
        )

        log_d = d.get("logging", {})
        logging_cfg = LoggingConfig(
            level=log_d.get("level", "INFO"),
            dump_llm_io=log_d.get("dump_llm_io", True),
            rich_console=log_d.get("rich_console", True),
        )

        return cls(
            llm=llm,
            defaults=defaults,
            shot=shot,
            video_models=video_models,
            motion_types=d.get("motion_types", []),
            transitions=d.get("transitions", []),
            output=output,
            input=input_cfg,
            visual_anchors=visual_anchors,
            subtitle=subtitle,
            voiceover=voiceover,
            quality_check=quality_check,
            logging=logging_cfg,
        )
