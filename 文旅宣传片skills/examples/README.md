# 示例输入

## inspiration_皖南古村.txt
灵感描述示例（约 200 字）。演示"灵感→成套提示词"的链路。

## full_script_归.md
完整剧本示例（约 600 字）。演示"剧本→成套提示词"的链路，含场景列表、旁白、字幕、技术要求。

## 用法

```bash
# 灵感示例
film-prompts run -i examples/inspiration_皖南古村.txt -o output/

# 完整剧本示例
film-prompts run -i examples/full_script_归.md -o output/
```

## 期望产出

跑完后 `output/{project_id}/` 下应有：
- `00_director_notes.json` — 导演手记
- `01_screenplay.json` — 编剧脚本+分镜清单
- `02_shot_prompts.json` — 分镜师画面提示词（含视觉锚点）
- `03_video_prompts.json` — 视频师运动提示词+选型
- `final_package.json` — 全量合并
- `human_readable.md` — 人类可读版本
- `prompts_only.txt` — 只抽提示词
- `shot_table.csv` — 镜头表
