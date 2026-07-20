"""
Skill: industrial-storyboard
短剧分镜工业化提示词生成器（独立技能，不与现有分镜技能合并）。

将用户输入的剧本片段 / 结构化镜头清单 / 单镜描述，自动按"场号-镜头号"拆分，
逐镜套用标准 12 字段公式，同时输出两套内容：
  1. 分镜卡（Markdown 表格，12 字段完整）
  2. AI 模型中文提示词块（9 段压缩格式，可直接喂给即梦/可灵等模型）

内置 14 套题材风格包、C编号角色档案体系、S编号场景档案体系、运镜禁词校验。

基于 data/prompts/industrial_storyboard/ 下的技能包文件实现：
  - formula/12-fields-formula.md     12 字段公式定义
  - formula/forbidden-words.md       运镜禁词校验规则
  - style-packs/index.md             14 套风格包索引
  - style-packs/<pack>.md            各题材风格包详情
  - templates/character-template.md  角色档案模板（C001 体系）
  - templates/scene-template.md      场景档案模板（S001 体系）
  - output-formats/storyboard-card.md        分镜卡输出模板
  - output-formats/model-prompt-cn.md        AI 模型中文提示词压缩规则
"""
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.agents.llm_utils import llm_json
from app.skills.base import BaseSkill, SkillInfo, SkillOutput, SkillParam


# ─── 参考文件加载 ────────────────────────────────────────
_REF_DIR = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "prompts"
    / "industrial_storyboard"
)

_STYLE_PACK_DIR = _REF_DIR / "style-packs"


def _load_ref(rel_path: str) -> str:
    """加载参考文件内容，若文件不存在则返回空字符串。"""
    filepath = _REF_DIR / rel_path
    try:
        return filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _load_style_pack(pack_filename: str) -> str:
    """加载某个风格包详情文件。"""
    try:
        return (_STYLE_PACK_DIR / pack_filename).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


# 预加载常驻文件（公式 / 禁词 / 索引 / 输出格式）
_FORMULA_12_FIELDS = _load_ref("formula/12-fields-formula.md")
_FORBIDDEN_WORDS = _load_ref("formula/forbidden-words.md")
_STYLE_PACK_INDEX = _load_ref("style-packs/index.md")
_STORYBOARD_CARD_FMT = _load_ref("output-formats/storyboard-card.md")
_MODEL_PROMPT_CN_FMT = _load_ref("output-formats/model-prompt-cn.md")

# 题材 → 风格包文件名映射
_GENRE_TO_PACK: Dict[str, str] = {
    "古装权谋 (G01)": "ancient-political.md",
    "现代复仇 (G02)": "modern-revenge.md",
    "甜宠 (G03)": "sweet-romance.md",
    "悬疑罪案 (G04)": "suspense-crime.md",
    "都市职场 (G05)": "urban-workplace.md",
    "民国谍战 (G06)": "republic-spy.md",
    "仙侠玄幻 (G07)": "xianxia-fantasy.md",
    "校园青春 (G08)": "campus-youth.md",
    "家庭伦理 (G09)": "family-ethics.md",
    "战争军旅 (G10)": "war-military.md",
    "惊悚灵异 (G11)": "horror-supernatural.md",
    "电竞热血 (G12)": "e-sports-hot-blooded.md",
    "大漠武侠 (G13)": "desert-wuxia.md",
    "宫廷古装 (G14)": "costume-palace.md",
}


# ─── 参数选项 ────────────────────────────────────────────
GENRE_OPTIONS = list(_GENRE_TO_PACK.keys()) + ["自定义"]

INPUT_MODE_OPTIONS = ["自动识别", "模式A：剧本自动拆分", "模式B：结构化镜头清单", "模式C：单镜直填"]


class IndustrialStoryboardSkill(BaseSkill):
    """短剧分镜工业化提示词生成器（独立技能）。"""

    info = SkillInfo(
        skill_id="industrial-storyboard",
        skill_name="短剧分镜工业化提示词",
        tags=[
            "分镜",
            "工业化",
            "12字段公式",
            "C编号角色档案",
            "S编号场景档案",
            "14套风格包",
            "运镜禁词校验",
            "双版本输出",
            "AI模型提示词",
        ],
        supported_outputs=[
            "分镜卡（Markdown 表格 12 字段）",
            "AI 模型中文提示词块（9 段压缩）",
            "角色档案（C001 体系）",
            "场景档案（S001 体系）",
        ],
        version="1.0.0",
        category="分镜制作类",
        params=[
            SkillParam(
                "创作内容",
                "text",
                required=True,
                description="剧本片段 / 结构化镜头清单 / 单镜描述",
            ),
            SkillParam("题材风格包", "select", options=GENRE_OPTIONS, default="古装权谋 (G01)"),
            SkillParam("输入模式", "select", options=INPUT_MODE_OPTIONS, default="自动识别"),
        ],
    )

    # system_prompt 在运行时动态构建（需嵌入参考文件内容）
    system_prompt = ""

    def _build_system_prompt(self, merged: Dict[str, Any]) -> str:
        """构建包含参考文件知识的 system prompt（精简版，只加载选中的风格包）。"""
        genre = str(merged.get("题材风格包", "古装权谋 (G01)"))
        mode = str(merged.get("输入模式", "自动识别"))

        # 只加载用户选中的那 1 套风格包详情，不加载全部 14 套
        pack_filename = _GENRE_TO_PACK.get(genre, "")
        selected_pack = _load_style_pack(pack_filename) if pack_filename else ""

        return f"""\
# Role
你是短剧分镜工业化生产引擎。将用户提交的剧本片段 / 结构化镜头清单 / 单镜描述，
按"场号-镜头号"拆分为多个镜头单元，逐镜套用标准 12 字段公式，同时输出两套内容：
  1. 分镜卡（Markdown 表格，12 字段完整）
  2. AI 模型中文提示词块（9 段压缩格式，可直接喂给即梦/可灵等模型）

## 全局参数
- 题材风格包：{genre}
- 输入模式：{mode}

---

# 硬不变量（绝对不可违反）

1. **12 字段完整**：每张分镜卡必须包含全部 12 个字段（镜头ID/时间码/景别/运镜/场景地点/环境光影/出场人物/人物动作/面部表情/情绪基调/台词音效/转场方式），缺一不可。
2. **运镜禁词**："运镜"字段中严禁出现"运镜"二字，必须改写为精确起止状态+运动轨迹+速度描述。
3. **角色ID体系**：出场人物字段必须使用 `C编号` 体系（C001、C002……按出场顺序）。
4. **场景ID体系**：场景地点字段必须使用 `S编号` 体系（S001、S002……按出场顺序）。
5. **情绪基调**：必须为 2-4 字短语，对应风格包的情绪节奏阶段。
6. **时间码累计**：时间码按全剧时间轴累计计算，非每场独立。
7. **双版本输出**：每条镜头必须同时输出分镜卡 + AI 模型提示词块。
8. **禁止写入文件**：只输出到对话中。

---

# STEP 1: 解析输入 → 判断模式 A / B / C

- 模式 A（剧本自动拆分）：用户提供剧本文字段落 → 按动作变化+台词变化自动切分镜头单元
- 模式 B（结构化镜头清单）：用户提供 CSV/JSON/Markdown 表格（含场号、镜号、景别、台词等） → 直接补全 12 字段
- 模式 C（单镜直填）：用户描述单个镜头核心信息 → 生成单张分镜卡
- 若用户指定了模式，按指定模式执行；否则自动识别输入格式

# STEP 2: 读取/创建角色档案（C001 体系）

- 从剧本/清单中识别出场人物，按出场顺序分配 C编号（C001、C002……）
- 提取角色外貌/服装/性格标签/口头动作/面部表情库
- 若用户已提供角色档案，优先调用档案内容

# STEP 3: 读取/创建场景档案（S001 体系）

- 从剧本/清单中识别场景，按出场顺序分配 S编号（S001、S002……）
- 提取场景空间属性/环境属性/光影基调/音效偏好
- 若用户已提供场景档案，优先调用档案内容

# STEP 4: 匹配题材风格包（G01-G14）

- 根据用户指定的题材，加载对应风格包的完整参数（光影基调/运镜偏好/情绪节奏/转场偏好/色彩特征/构图特征）
- 支持临时覆盖某项参数（例：题材古装权谋，但光影改为冷蓝调）
- 风格包索引见下方【参考·风格包索引】，当前选中风格包详情见下方【参考·当前风格包详情】

# STEP 5: 按 12 字段公式逐项填充

- 逐镜填充 12 个字段，遵循字段填充优先级（景别→情绪→动作→表情→光影→运镜→转场→时间码）
- 12 字段公式定义见下方【参考·12字段公式】
- 字段格式严格遵循公式中的示例

# STEP 6: 运镜禁词校验（强制）

- 扫描所有镜头的"运镜"字段，确认无"运镜"二字
- 若出现禁词，按改写模板重写为精确轨迹描述
- 禁词清单与改写规则见下方【参考·运镜禁词校验规则】

# STEP 7: 双版本输出

每条镜头同时输出：
  1. 分镜卡（Markdown 表格）—— 格式见下方【参考·分镜卡输出模板】
  2. AI 模型中文提示词块（9 段压缩）—— 压缩规则见下方【参考·AI模型提示词压缩规则】

输出结构：先输出整场戏的分组标题（含场景/题材/情绪曲线），再逐镜输出"分镜卡 + 提示词块"。

---

# 【参考·12字段公式】

{_FORMULA_12_FIELDS}

---

# 【参考·运镜禁词校验规则】

{_FORBIDDEN_WORDS}

---

# 【参考·风格包索引】

{_STYLE_PACK_INDEX}

---

# 【参考·当前风格包详情】（{genre}）

{selected_pack}

---

# 【参考·分镜卡输出模板】

{_STORYBOARD_CARD_FMT}

---

# 【参考·AI模型提示词压缩规则】

{_MODEL_PROMPT_CN_FMT}

---

## 输出 JSON 结构

请严格输出以下 JSON 结构，分镜卡和提示词块内容放在对应字符串字段中：

{{
  "skill_id": "industrial-storyboard",
  "skill_name": "短剧分镜工业化提示词",
  "title": "分镜标题（从创作内容概括）",
  "genre": "{genre}",
  "input_mode": "{mode}",
  "scene_group": "场景分组标题（例：场景 S001 — 沈砚夜审李掌柜）",
  "emotion_curve": "情绪曲线（例：压抑沉寂 - 暗流涌动 - 压迫对峙 - 惊恐求饶 - 威权碾压）",
  "storyboard_cards": "全部分镜卡的 Markdown 内容（含分组标题 + 逐镜 12 字段表格）",
  "model_prompts": "全部 AI 模型中文提示词块的 Markdown 内容（逐镜 9 段压缩，用 --- 分隔每镜）",
  "characters": [
    {{"id": "C001", "name": "角色名", "appearance": "外貌/服装简述", "personality": "性格标签", "actions": "口头动作"}},
    {{"id": "C002", "name": "角色名", "appearance": "外貌/服装简述", "personality": "性格标签", "actions": "口头动作"}}
  ],
  "scenes": [
    {{"id": "S001", "name": "场景名", "space": "空间属性简述", "lighting": "照明方式简述", "ambient_sound": "环境音效"}}
  ],
  "shot_count": 5,
  "total_duration": "22秒"
}}

## 约束
- 不要输出 XML 包裹标签
- 不要输出内部分析、自查清单
- 分镜卡必须使用 S编号/C编号 体系
- 运镜字段严禁出现"运镜"二字
- 每条镜头必须同时输出分镜卡 + 提示词块
- **严禁在 JSON 字符串值中使用 ``` 代码块标记**，所有内容用纯文本表达，每镜提示词之间用 --- 分隔
- 只输出 JSON，不要在 JSON 外输出任何 Markdown 或解释文字
"""

    async def run(
        self,
        user_input: str,
        params: Optional[Dict[str, Any]] = None,
        global_params: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> SkillOutput:
        merged = self.merge_params(params)
        system_prompt = self._build_system_prompt(merged)
        system_prompt = self._render_global_params(system_prompt, global_params)

        user_content = f"""\
创作内容：
{user_input}

请按照 STEP 1–7 流程执行，输出完整的分镜卡（Markdown 表格）和 AI 模型中文提示词块。
"""

        result = await llm_json(
            system_prompt,
            user_content,
            model=self._llm_model,
            history=history,
            max_tokens=16384,
            temperature=0.4,
            fallback={
                "skill_id": self.info.skill_id,
                "skill_name": self.info.skill_name,
                "title": "",
                "genre": merged.get("题材风格包", ""),
                "input_mode": merged.get("输入模式", ""),
                "scene_group": "",
                "emotion_curve": "",
                "storyboard_cards": "",
                "model_prompts": "",
                "characters": [],
                "scenes": [],
                "shot_count": 0,
                "total_duration": "",
                "_error": "LLM 调用失败，请稍后重试",
            },
        )

        is_fallback = result.get("_is_fallback", False)

        # 后端拼接 full_markdown
        if not is_fallback:
            result["full_markdown"] = self._build_full_markdown(result)

        return SkillOutput(
            skill_id=self.info.skill_id,
            status="success" if not is_fallback else "failed",
            data=result,
            error=result.get("_fallback_error"),
        )

    @staticmethod
    def _build_full_markdown(result: Dict[str, Any]) -> str:
        """从结构化数据拼接完整的 Markdown 输出。"""
        parts: List[str] = []

        title = result.get("title", "")
        if title:
            parts.append(f"# 《{title}》- 短剧分镜工业化提示词\n")

        # 基本信息
        genre = result.get("genre", "")
        mode = result.get("input_mode", "")
        shot_count = result.get("shot_count", "")
        total_duration = result.get("total_duration", "")
        if any([genre, mode, shot_count, total_duration]):
            parts.append("## 基本信息\n")
            info_parts = []
            if genre:
                info_parts.append(f"题材风格包：{genre}")
            if mode:
                info_parts.append(f"输入模式：{mode}")
            if shot_count:
                info_parts.append(f"镜头数：{shot_count}")
            if total_duration:
                info_parts.append(f"总时长：{total_duration}")
            parts.append(" | ".join(info_parts) + "\n")

        # 情绪曲线
        emotion_curve = result.get("emotion_curve", "")
        if emotion_curve:
            parts.append(f"**情绪曲线**：{emotion_curve}\n")

        # 角色档案
        characters = result.get("characters", [])
        if characters:
            parts.append("---\n\n## 角色档案（C编号体系）\n")
            for c in characters:
                cid = c.get("id", "")
                name = c.get("name", "")
                appearance = c.get("appearance", "")
                personality = c.get("personality", "")
                actions = c.get("actions", "")
                parts.append(f"### {cid} {name}\n")
                if appearance:
                    parts.append(f"- 外貌/服装：{appearance}")
                if personality:
                    parts.append(f"- 性格标签：{personality}")
                if actions:
                    parts.append(f"- 口头动作：{actions}")
                parts.append("")

        # 场景档案
        scenes = result.get("scenes", [])
        if scenes:
            parts.append("## 场景档案（S编号体系）\n")
            for s in scenes:
                sid = s.get("id", "")
                name = s.get("name", "")
                space = s.get("space", "")
                lighting = s.get("lighting", "")
                ambient = s.get("ambient_sound", "")
                parts.append(f"### {sid} {name}\n")
                if space:
                    parts.append(f"- 空间属性：{space}")
                if lighting:
                    parts.append(f"- 照明方式：{lighting}")
                if ambient:
                    parts.append(f"- 环境音效：{ambient}")
                parts.append("")

        # 分镜卡
        storyboard_cards = result.get("storyboard_cards", "")
        if storyboard_cards:
            parts.append("---\n\n## 📋 分镜卡（12 字段表格）\n")
            parts.append(storyboard_cards)
            parts.append("")

        # AI 模型中文提示词块
        model_prompts = result.get("model_prompts", "")
        if model_prompts:
            parts.append("---\n\n## 🎬 AI 模型中文提示词块（9 段压缩）\n")
            parts.append(model_prompts)
            parts.append("")

        return "\n".join(parts)
