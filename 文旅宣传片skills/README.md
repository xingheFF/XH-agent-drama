# 文旅剧情宣传片提示词工坊

> 用户输入剧本/灵感 → 导演提炼重点 → 编剧写脚本分镜 → 分镜师出画面提示词 → 视频师出视频运动提示词 → 交付成套提示词包

## 快速开始

```bash
# 安装
pip install -e .

# 配置（复制并填入 LLM key）
cp config.example.yaml config.yaml

# 一键全流程
film-prompts run --input examples/inspiration_皖南古村.txt --output output/

# 只重跑某一环
film-prompts rerun --role director --from output/proj_001/00_director_notes.json

# 查看某个角色的输出
film-prompts show --package output/proj_001 --role videographer
```

## 四个角色

| 角色 | 模块 | 职责 | 输出 |
|---|---|---|---|
| ① 导演 | `roles/director.py` | 从输入提炼主题/情绪/文旅要素/创作约束 | `DirectorNotes` |
| ② 编剧 | `roles/screenwriter.py` | 把重点信息展开为脚本+分镜清单 | `Screenplay` |
| ③ 分镜师 | `roles/storyboard.py` | 建视觉锚点，逐镜头出画面提示词 | `ShotPrompts` |
| ④ 视频师 | `roles/videographer.py` | 整合上下文，出运动提示词+模型选型 | `VideoPrompts` |

## 目录结构

```
文旅宣传片skills/
├── config.example.yaml
├── pyproject.toml
├── src/cultural_film_prompts/
│   ├── cli.py                 # Typer 入口
│   ├── pipeline.py            # 四角色编排
│   ├── config.py              # 配置加载
│   ├── roles/                 # 四个角色
│   ├── models/                # Pydantic 数据结构
│   ├── llm/                   # LLM 适配层
│   ├── io/                    # 输入解析 + 输出写入
│   ├── prompts/               # 各角色 system prompt（.md）
│   └── templates/             # Jinja2 输出模板（.j2）
├── examples/                  # 示例输入
├── output/                    # 成片产物（gitignore）
└── tests/
```

## 配置说明

见 `config.example.yaml`。所有参数（LLM 选型、默认时长、比例、风格词、视频模型能力表、重试策略、各角色温度）都写在配置里，代码只读不硬编码。

## 开发状态

骨架已搭好，所有数据模型字段、角色 prompt 模板、LLM 适配层、流水线编排、CLI、输出层全部就位。下一步接入真实 LLM 即可跑通。
