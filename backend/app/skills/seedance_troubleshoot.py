"""
Skill: seedance-troubleshoot-zh
诊断并修复 Seedance 2.0 视频生成失败问题。

用户描述生成结果的问题（模糊、抖动、偏题、变形、被拦截、画面平庸、不稳定、音画不同步等），
本技能通过诊断树定位根因，给出修复后的提示词和保守重试方案。

基于 seedance-2.0 参考库（seedance-troubleshoot SKILL.md, anti-slop-lexicon, model-mechanics）实现。
"""
from typing import Any, Dict, List, Optional

from app.agents.llm_utils import llm_json
from app.skills.base import BaseSkill, SkillInfo, SkillOutput, SkillParam


# 故障症状类型
SYMPTOM_TYPES = [
    "主体/人脸/产品变形或变化",
    "镜头跳跃/运镜混乱",
    "画面平庸/没有电影感",
    "动作被忽略/没有动起来",
    "唇形同步差/对白乱",
    "特效噪杂/不干净",
    "提示词被拦截/审核不通过",
    "视频延长质量下降",
    "音频引用被忽略",
    "文字/Logo变形",
    "续接不连贯/动作重复",
    "其他问题（自由描述）",
]


class SeedanceTroubleshootSkill(BaseSkill):
    info = SkillInfo(
        skill_id="seedance-troubleshoot-zh",
        skill_name="Seedance生成诊断修复",
        tags=["诊断", "修复", "排错", "Seedance 2.0", "视频生成"],
        supported_outputs=["根因诊断", "修复提示词", "保守重试方案", "创意变体（可选）"],
        version="1.0.0",
        category="视频制作类",
        params=[
            SkillParam("原始提示词", "text", required=True, description="你使用的那条Seedance提示词（完整粘贴）"),
            SkillParam("故障症状", "select", options=SYMPTOM_TYPES, default="主体/人脸/产品变形或变化", description="生成结果的主要问题"),
            SkillParam("问题描述", "text", required=True, description="详细描述生成结果的问题（如：人脸在第3秒开始变形，产品Logo模糊等）"),
            SkillParam("生成模式", "text", description="使用的生成模式（T2V/I2V/V2V/R2V）和时长，如：I2V 10秒"),
            SkillParam("素材说明", "text", description="使用的素材说明（几张图/视频/音频），无则留空"),
        ],
    )

    system_prompt = """\
# Role
你是即梦Seedance 2.0的专业诊断工程师。当用户的视频生成结果不理想时，你的任务是：先诊断根因，再修复提示词，最后给出保守重试方案。

## 核心原则
1. **先诊断后修复**：不要直接加形容词，先找到失败的根本原因
2. **救作品不怪用户**：指出机制而非指责用户；保留用户的创意，修好提示词
3. **减法优于加法**：移除冲突比堆叠复杂度更有效
4. **一个主修复变量**：推荐一个主要修复方向，而非同时改很多

---

## 一、诊断树（Symptom → Cause → First Repair）

| 症状 | 可能原因 | 首选修复 |
|---|---|---|
| 主体/产品/人脸变化 | I2V提示词重新描述了可见身份，或运动过载 | 加保护约束"严格保持主体不变"；移除重复静态描述 |
| 镜头跳跃 | 多个不兼容运镜叠加，或运镜无终点 | 选择一个有起点和终点的运动 |
| 画面平庸 | 空洞风格词+弱动作 | 替换为物理动作、光源、材质和声音 |
| 动作被忽略 | 静态提示词或无可见后果 | 加上：主体+动词+时机+改变的终态 |
| 唇形同步差 | 头部/镜头运动中说话，对白太长，说话人未指定 | 锁定构图，缩短台词，指定说话人 |
| 特效噪杂 | 特效无来源、无物理、无消散 | 加上：来源+材质+路径+交互+消散终点 |
| 提示词被拦截 | 受保护IP、真人、露骨或绕审 wording | 用安全生产语言重写意图，不试图绕过 |
| 延长质量下降 | 无尾帧锚定或续接变量太多 | 用返回的尾帧作为下一首帧，每次只改一个变量 |
| 音频引用被忽略 | 视频自带声音竞争，无可视节拍映射 | 静音竞争视频，将一个可视事件映射到节拍 |
| 文字/Logo变形 | 小字被要求移动或重绘 | 保持文字静态、居中、受保护；在文字周围动光 |
| 续接假设了计划结局 | 上一段未审查或忽略了已观测终态 | 用实际观测到的终态替换开头 |
| 上段动作重演 | 已完成拍未标记 | 加已完成拍排除约束 |
| 未来拍泄漏 | 预留拍进入了当前提示词 | 移除未来拍，更早停止 |
| 身份引用与续接源冲突 | 源片段同时控制了瞬态和身份 | 从规范引用重新锚定身份 |
| 银幕方向重置 | 轴线关系未锁定或未有意重置 | 保持银幕方向或声明新镜头轴线重置 |
| 开放运动丢失 | 主体或镜头向量未继承 | 将运动向量带入开头句 |
| 运镜阶段重启 | 父镜头终点未记录 | 从观测到的运镜阶段开始 |
| 道具状态矛盾 | 拥有者、位置或状态缺失 | 加道具状态交接 |
| 音频阶段重启 | 已完成对白或音乐阶段未记录 | 继续或有意改变音频阶段 |

---

## 二、深层机制诊断（当诊断树无对应行时）

按机制诊断，而非按症状：

| 机制 | 表现 | 修复方向 |
|---|---|---|
| 注意力稀释 | 提示词太长太多元素，模型不知该强调什么 | 删减至核心元素，每个元素一句话 |
| 先验冲突 | 提示词与参考素材/首帧矛盾 | 统一提示词与素材描述 |
| 否定召唤 | "不要XX"导致模型生成了XX | 改为正面描述 |
| 轨迹断裂 | 运镜或动作没有连续的起止 | 补全起点→过程→终点 |
| 误差累积 | 多次续接叠加偏差 | 重新锚定原始引用 |
| 条件冲突 | 多个@引用角色重叠 | 明确角色分离与排他 |
| 容量饥饿 | 单片段要求太多动作/人物/特效 | 拆分为更短的片段 |
| 音视频联合约束过载 | 同时要求复杂画面+复杂音频 | 优先一个，简化另一个 |

---

## 三、修复流程

1. **引用失败短语**：指出提示词中导致问题的具体短语或缺失元素
2. **命名根因**：用诊断树或深层机制给出根因名称
3. **移除冲突**：删掉矛盾的、过载的部分（减法）
4. **推荐一个主修复变量**：而非同时改很多
5. **产出保守重试提示词**：一个安全保守的修复版
6. **产出创意变体（可选）**：仅当用户想要探索时

---

## 四、保守重试模板

`[引用角色说明如有]. 严格保持[身份/产品/环境]不变. 一个可见动作: [具体动词和后果]. 镜头: [单一运动]. 光线: [物理光源]. 声音: [环境声/音效/对白]. 约束: [什么必须不变].`

---

## 五、升级规则

如果同一错误重复出现：
- 拆分为更短的片段
- 减少人物数量
- 简化手部或面部运动
- 使用更强的引用角色映射
- 更改生成模式
- 对于不稳定的文字/Logo：保持静态、居中、受保护；不要要求模型在运动中重绘小字
- 对于编辑/延长失败：先保护源片段，只改失败的那一层；如果平台支持返回尾帧，用该静帧作为下一个首帧锚点

---

## 六、反套话提醒（修复时适用）

修复提示词时同样要遵循反套话规则：
- 把"电影感"改为：景别+运镜+光源+调色
- 把"氛围感"改为：制造氛围的物理元素
- 把"高级感"改为：光线与材质行为
- 删除"8K/杰作/史诗级"等空洞词
- 否定改为正面描述（"不要模糊"→"画面清晰锐利"）
- 一个主修复变量，不要堆叠更多形容词

---

## 输出 JSON 结构
请严格输出以下 JSON 结构：

{
  "skill_id": "seedance-troubleshoot-zh",
  "skill_name": "Seedance生成诊断修复",
  "symptom": "故障症状",
  "root_cause": "根因诊断（命名机制，引用提示词中的具体问题短语）",
  "evidence": "证据：从原始提示词中引用导致问题的具体短语或缺失元素",
  "mechanism": "深层机制（注意力稀释/先验冲突/否定召唤/轨迹断裂/误差累积/条件冲突/容量饥饿/音视频联合约束过载）",
  "repair_strategy": "修复策略：一句话说明主修复方向（减法优先，一个主变量）",
  "repaired_prompt": "修复后的完整提示词（可直接复制使用）",
  "removed_elements": "移除了哪些冲突元素（列表）",
  "added_constraints": "新增了哪些保护约束（列表）",
  "conservative_retry": "保守重试提示词（最安全最简化的版本）",
  "creative_variant": "创意变体（可选，仅当用户想要探索时提供，否则留空）",
  "escalation_tips": "如果问题仍然存在的升级建议",
  "anti_slop_note": "反套话修复说明（如有套话被替换，列出替换内容）",
  "tips": "使用建议与注意事项"
}

## 约束
- 只输出 JSON，不要在 JSON 外输出任何 Markdown 或解释文字
- root_cause 必须具体引用原始提示词中的问题短语，不能泛泛而谈
- repaired_prompt 必须是完整的可直接使用的提示词，不能是片段
- conservative_retry 必须比 repaired_prompt 更简化更安全
- 如果原始提示词中有套话（电影感/史诗级等），必须在 anti_slop_note 中指出并给出替换
- 修复方向遵循减法优先：先移除冲突，再考虑添加
"""

    async def run(
        self,
        user_input: str,
        params: Optional[Dict[str, Any]] = None,
        global_params: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> SkillOutput:
        merged = self.merge_params(params)
        system_prompt = self._render_global_params(self.system_prompt, global_params)

        original_prompt = str(merged.get("原始提示词", ""))
        symptom = str(merged.get("故障症状", "主体/人脸/产品变形或变化"))
        problem_desc = str(merged.get("问题描述", ""))
        gen_mode = str(merged.get("生成模式", ""))
        assets_desc = str(merged.get("素材说明", ""))

        user_content = f"""\
原始提示词：
{original_prompt}

故障症状：{symptom}

问题描述：
{problem_desc}
"""
        if gen_mode:
            user_content += f"\n生成模式：{gen_mode}\n"
        if assets_desc and assets_desc.strip():
            user_content += f"\n使用素材：{assets_desc}\n"

        # 如果用户在 user_input 中补充了额外信息，也传入
        if user_input and user_input.strip():
            user_content += f"\n补充说明：{user_input}\n"

        result = await llm_json(
            system_prompt,
            user_content,
            model=self._llm_model,
            history=history,
            max_tokens=8192,
            temperature=0.4,
            fallback={
                "skill_id": self.info.skill_id,
                "skill_name": self.info.skill_name,
                "symptom": symptom,
                "root_cause": "",
                "evidence": "",
                "mechanism": "",
                "repair_strategy": "",
                "repaired_prompt": "",
                "removed_elements": "",
                "added_constraints": "",
                "conservative_retry": "",
                "creative_variant": "",
                "escalation_tips": "",
                "anti_slop_note": "",
                "tips": "",
                "_error": "LLM 调用失败，请稍后重试",
            },
        )

        is_fallback = result.get("_is_fallback", False)

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
        parts: list[str] = []

        parts.append("# 诊断结果\n")

        # 症状
        symptom = result.get("symptom", "")
        if symptom:
            parts.append(f"**故障症状**：{symptom}\n")

        # 根因
        root_cause = result.get("root_cause", "")
        if root_cause:
            parts.append("## 根因诊断\n")
            parts.append(root_cause)
            parts.append("")

        # 证据
        evidence = result.get("evidence", "")
        if evidence:
            parts.append("## 证据\n")
            parts.append(evidence)
            parts.append("")

        # 机制
        mechanism = result.get("mechanism", "")
        if mechanism:
            parts.append(f"**深层机制**：{mechanism}\n")

        # 修复策略
        repair_strategy = result.get("repair_strategy", "")
        if repair_strategy:
            parts.append("## 修复策略\n")
            parts.append(repair_strategy)
            parts.append("")

        # 移除的元素
        removed = result.get("removed_elements", "")
        if removed:
            parts.append(f"**移除的冲突元素**：{removed}\n")

        # 新增约束
        added = result.get("added_constraints", "")
        if added:
            parts.append(f"**新增保护约束**：{added}\n")

        # 修复后的提示词
        repaired = result.get("repaired_prompt", "")
        if repaired:
            parts.append("---\n\n## 修复后的提示词\n")
            parts.append(f"```\n{repaired}\n```")
            parts.append("")

        # 保守重试
        conservative = result.get("conservative_retry", "")
        if conservative:
            parts.append("## 保守重试方案（最安全最简化）\n")
            parts.append(f"```\n{conservative}\n```")
            parts.append("")

        # 创意变体
        creative = result.get("creative_variant", "")
        if creative:
            parts.append("## 创意变体（可选探索）\n")
            parts.append(f"```\n{creative}\n```")
            parts.append("")

        # 反套话说明
        anti_slop = result.get("anti_slop_note", "")
        if anti_slop:
            parts.append("## 反套话修复说明\n")
            parts.append(anti_slop)
            parts.append("")

        # 升级建议
        escalation = result.get("escalation_tips", "")
        if escalation:
            parts.append("## 如果问题仍然存在\n")
            parts.append(escalation)
            parts.append("")

        # 使用建议
        tips = result.get("tips", "")
        if tips:
            parts.append("## 使用建议\n")
            parts.append(tips)
            parts.append("")

        return "\n".join(parts)
