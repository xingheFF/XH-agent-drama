"""CLI 入口 —— Typer。"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from .config import Config
from .io import parse_input, write_outputs
from .llm import LLMClient
from .models import (
    DirectorNotes,
    Screenplay,
    ShotPrompts,
    VideoPrompts,
)
from .pipeline import (
    PIPELINE_VERSION,
    rerun_role,
    run_pipeline,
)

app = typer.Typer(
    name="film-prompts",
    help="文旅剧情宣传片提示词工坊",
    no_args_is_help=True,
)
console = Console()


# —— 日志初始化 ——


def setup_logging(config: Config) -> None:
    level = getattr(logging, config.logging.level.upper(), logging.INFO)
    if config.logging.rich_console:
        handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            rich_tracebacks=True,
        )
    else:
        handler = logging.StreamHandler()

    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[handler],
        force=True,
    )


# —— 加载配置 ——


def load_config(config_path: str | None = None) -> Config:
    candidates = [
        Path(config_path) if config_path else None,
        Path("config.yaml"),
        Path("config.example.yaml"),
    ]
    for c in candidates:
        if c and c.exists():
            return Config.load(c)
    console.print("[red]找不到配置文件 config.yaml 或 config.example.yaml[/]")
    raise typer.Exit(1)


# —— 命令：一键全流程 ——


@app.command()
def run(
    input: str = typer.Option(..., "--input", "-i", help="输入文件路径或纯文本"),
    output: str = typer.Option("output", "--output", "-o", help="输出目录"),
    config: str = typer.Option(
        "config.yaml", "--config", "-c", help="配置文件路径"
    ),
) -> None:
    """一键全流程：输入 → 导演 → 编剧 → 分镜 → 视频 → 提示词包"""

    cfg = load_config(config)
    setup_logging(cfg)
    logger = logging.getLogger(__name__)

    # —— 解析输入 ——
    parsed = parse_input(
        source=input,
        full_script_min_chars=cfg.input.full_script_min_chars,
        full_script_markers=cfg.input.full_script_markers,
        inspiration_max_chars=cfg.input.inspiration_max_chars,
        asset_extensions=cfg.input.asset_extensions,
    )

    console.print("\n[bold cyan]文旅剧情宣传片提示词工坊[/]")
    console.print(f"  版本: v{PIPELINE_VERSION}")
    console.print(f"  输入类型: [yellow]{parsed.input_type.value}[/]")
    console.print(f"  字符数: {parsed.char_count}")
    console.print(f"  模型: {cfg.llm.model}")
    console.print(f"  目标时长: {cfg.defaults.target_duration}s\n")

    if not parsed.raw_text:
        console.print("[red]输入为空，无法处理[/]")
        raise typer.Exit(1)

    # —— 跑流水线 ——
    try:
        package = run_pipeline(
            user_input=parsed.raw_text,
            config=cfg,
        )
    except Exception as e:
        console.print(f"[red]流水线失败: {e}[/]")
        logger.exception("Pipeline failed")
        raise typer.Exit(1)

    # —— 写输出 ——
    cfg.output.dir = output
    written = write_outputs(package, cfg, base_dir=output)

    # —— 汇总 ——
    console.print("\n[bold green]✓ 流水线完成[/]")
    console.print(f"  项目 ID: {package.project_id}")

    table = Table(title="输出文件", show_header=True)
    table.add_column("类型", style="cyan")
    table.add_column("路径", style="white")
    for k, v in written.items():
        table.add_row(k, v)
    console.print(table)

    # 质检结果
    qr = package.quality_report
    if qr.get("passed"):
        console.print("\n[green]✓ 质检通过[/]")
    else:
        console.print("\n[yellow]⚠ 质检发现问题:[/]")
        for issue in qr.get("issues", []):
            console.print(f"  - {issue}")


# —— 命令：单角色重跑 ——


@app.command()
def rerun(
    role: str = typer.Option(
        ..., "--role", "-r",
        help="角色: director / screenwriter / storyboard / videographer",
    ),
    from_json: str = typer.Option(
        ..., "--from", "-f",
        help="包含上游数据的 JSON 文件路径",
    ),
    output: str = typer.Option("output", "--output", "-o", help="输出目录"),
    config: str = typer.Option("config.yaml", "--config", "-c"),
) -> None:
    """单角色重跑（迭代回路）"""

    cfg = load_config(config)
    setup_logging(cfg)

    import json

    upstream_data = json.loads(Path(from_json).read_text(encoding="utf-8"))

    result = rerun_role(role=role, upstream_data=upstream_data, config=cfg)

    # 写出
    out_dir = Path(output) / f"rerun_{role}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{role}_output.json"
    out_file.write_text(
        json.dumps(result.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    console.print(f"\n[bold green]✓ {role} 重跑完成[/]")
    console.print(f"  输出: {out_file}")


# —— 命令：查看产物 ——


@app.command(name="show")
def show_cmd(
    package: str = typer.Option(..., "--package", "-p", help="package 目录路径"),
    role: str = typer.Option(
        "all", "--role", "-r",
        help="查看的角色: director / screenwriter / storyboard / videographer / all",
    ),
) -> None:
    """查看某个角色的输出"""

    pkg_dir = Path(package)
    if not pkg_dir.exists():
        console.print(f"[red]目录不存在: {pkg_dir}[/]")
        raise typer.Exit(1)

    role_files = {
        "director": "00_director_notes.json",
        "screenwriter": "01_screenplay.json",
        "storyboard": "02_shot_prompts.json",
        "videographer": "03_video_prompts.json",
    }

    if role == "all":
        for r, fn in role_files.items():
            p = pkg_dir / fn
            if p.exists():
                console.print(f"\n[bold cyan]── {r} ──[/]")
                console.print(p.read_text(encoding="utf-8")[:2000])
    else:
        fn = role_files.get(role)
        if not fn:
            console.print(f"[red]未知角色: {role}[/]")
            raise typer.Exit(1)
        p = pkg_dir / fn
        if not p.exists():
            console.print(f"[red]文件不存在: {p}[/]")
            raise typer.Exit(1)
        console.print(p.read_text(encoding="utf-8"))


# —— 命令：版本 ——


@app.command()
def version() -> None:
    """显示版本"""

    console.print(f"文旅剧情宣传片提示词工坊 v{PIPELINE_VERSION}")


if __name__ == "__main__":
    app()
