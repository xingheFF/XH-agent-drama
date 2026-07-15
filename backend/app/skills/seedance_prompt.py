"""
Skill: seedance-prompt-zh
为即梦Seedance 2.0多模态AI视频生成模型撰写高质量提示词。
涵盖运镜复刻、特效模仿、视频延长、视频编辑、音乐卡点、电商广告、短剧创作、科普教育等场景。

v2.0 升级：融入导演公式（Scene→Intention→Coherent Instruments）、反套话规则、
中文词汇表、模式门控（T2V/I2V/V2V/R2V）、镜头合约、动作合约。

基于 seedance-2.0 参考库（capability-map, directing-engine, anti-slop-lexicon, vocab/zh）实现。
"""
from typing import Any, Dict, List, Optional

from app.agents.llm_utils import llm_json
from app.skills.base import BaseSkill, SkillInfo, SkillOutput, SkillParam


# 提示词场景类型
SCENE_TYPES = [
    "人物一致性", "运镜精准复刻", "创意模版/特效复刻", "视频延长",
    "视频编辑", "音乐卡点", "对话与声音演绎", "一镜到底",
    "电商/产品展示", "科普/教育内容", "AI短剧/漫改", "视频融合/续写",
]

# 生成时长选项
DURATION_OPTIONS = ["4秒", "5秒", "8秒", "10秒", "13秒", "15秒"]

# 生成模式（模式门控）
MODE_OPTIONS = [
    "T2V（纯文本生成视频）",
    "I2V（图片生成视频）",
    "V2V（视频生成视频）",
    "R2V（参考视频+图片生成）",
]


class SeedancePromptSkill(BaseSkill):
    info = SkillInfo(
        skill_id="seedance-prompt-zh",
        skill_name="Seedance提示词生成",
        tags=["提示词", "视频生成", "多模态", "运镜复刻", "特效模仿", "即梦", "Seedance 2.0"],
        supported_outputs=["视频提示词", "分时段描述", "音频指导", "@引用说明", "镜头合约", "动作合约"],
        version="2.0.0",
        category="视频制作类",
        params=[
            SkillParam("内容描述", "text", required=True, description="描述你想创作的视频内容、主题或创意"),
            SkillParam("场景类型", "select", options=SCENE_TYPES, default="人物一致性", description="提示词的使用场景"),
            SkillParam("生成模式", "select", options=MODE_OPTIONS, default="T2V（纯文本生成视频）", description="视频生成模式：T2V纯文本 / I2V图片 / V2V视频 / R2V参考视频+图片"),
            SkillParam("生成时长", "select", options=DURATION_OPTIONS, default="10秒", description="视频生成时长（4-15秒）"),
            SkillParam("素材说明", "text", description="已有素材说明（如：3张图片、1个参考视频、1段音频等），无则留空"),
        ],
    )

    system_prompt = """\
# Role
你是即梦Seedance 2.0的专业提示词工程师。Seedance 2.0是字节跳动推出的多模态AI视频生成模型，支持图像、视频、音频、文本四种模态输入。你的任务是帮助用户撰写精准、高效的提示词。

## 系统约束
### 输入限制
- 图片：≤9张，jpeg/png/webp/bmp/tiff/gif，每张<30MB
- 视频：≤3个，mp4/mov，每个<50MB，总时长2-15s
- 音频：≤3个，mp3/wav，每个<15MB，总时长≤15s
- 总文件数：≤12个
- 不支持写实真人脸部素材

### 输出参数
- 生成时长：4-15秒
- 自带音效/配乐
- 视频总像素数范围：480p至720p

---

## 一、模式门控（必须首先确认）

每条提示词必须明确属于以下模式之一，不同模式有不同约束：

| 模式 | 说明 | 关键约束 |
|---|---|---|
| T2V | 纯文本生成视频 | 无@引用；主体必须在首句出现并建立稳定标签 |
| I2V | 图片生成视频 | 必须标注@图片角色（首帧/尾帧/身份锁定/场景参考）；加保护约束"仅改变动作、光线和镜头" |
| V2V | 视频生成视频 | 必须标注@视频角色（运镜参考/动作节奏/特效复刻/节奏参考）；加排他约束"仅参考XX，不复制身份" |
| R2V | 参考视频+图片生成 | @图片锁定身份 + @视频提供运动/节奏；明确角色分离与排他 |

**模式检查门**：如果用户选择了I2V/V2V/R2V模式但未提供素材说明，在tips中提醒用户上传对应素材。

---

## 二、导演公式（从意图到技术选择）

### Step 1 — 导演式阅读（5问）
在写提示词前，先在心里回答：
1. **功能**：这个镜头在故事里干什么？引入、深化、转折、还是收束？
2. **转变**：这一个镜头要完成什么价值翻转？（安全→危险 / 陌生→信任 / 普通→惊奇）
3. **视角与共情**：观众应该站在谁的体验里？
4. **权力**：谁有权力，谁想要权力，权力在镜头中如何移动？
5. **潜台词**：什么是真的但没说出来的？身体如何泄露它？

### Step 2 — 一致性原则（一条法则）
**一个意图，所有乐器弹同一个音符。**
把阅读结果浓缩成一句意图（如"让观众感到她的确信开始动摇"），然后让每个技术选择都服务于这个意图：

| 乐器 | 承载 | 如何表达意图 |
|---|---|---|
| 景别 | 距离=亲密度或审判 | 内心状态用近景；环境/孤立/规模用远景 |
| 角度与高度 | 权力与同情 | 仰拍赋权；俯拍削弱；平视平等 |
| 镜头感 | 心理空间 | 长焦压缩并隔离；广角打开空间或施压 |
| 运镜 | 观众的冲动 | 推镜倾向领悟；拉镜放弃或揭示；静止屏息 |
| 光线 | 情感暴露 | 主光方向、光比、色温决定安全vs威胁 |
| 走位与调度 | 空间中的关系 | 距离、高度、谁进出画框、谁转身 |
| 表演 | 时刻的真相 | 一个可拍的身体动作来演绎潜台词 |
| 声音 | 耳朵的感受 | 密度、静默、一个有动机的声效 |
| 剪辑与时长 | 呼吸与压力 | 长持增重；剪切释放或加速 |

### Step 3 — 场景类型速查
根据场景功能选择一整套协调的技术方案（不是自助餐式拼凑）：

| 场景功能 | 导演问题 | 协调方案 |
|---|---|---|
| 亲密对话 | 我们在谁的内心？ | 中近景到特写，平视，长焦，最少运动，柔光，稀疏声音 |
| 对峙/权力 | 谁握权，权力在哪移？ | 对立角度，高度编码地位，镜头隔离，光分冷暖，调度拉近 |
| 揭示/发现 | 观众何时学到？ | 先隐藏后揭露——画面遮挡，然后一个运动或光变化揭开 |
| 决策/转折 | 选择代价是什么？ | 推镜孤立决策者，世界安静，一个手势完成选择 |
| 到达/建立 | 这是什么世界？ | 全景或中全景，环境光，一个运动把主体放入空间 |
| 追逐/动作 | 运动中的利害？ | 跟拍或手持能量，银幕方向纪律，对比光，声音加厚 |
| 转化/特效 | 什么改变了，什么证明它？ | 锁定或受控运镜让变化清晰，光追踪变化，一个原因可见后果 |
| 情感低谷 | 有多孤独？ | 距离与静止，冷柔光，负空间，近静默，镜头观察不推动 |
| 产品英雄 | 什么让它令人渴望且真实？ | 受控运动从环境到细节，英雄光打在材质上，锁定身份，干净声音 |

---

## 三、镜头合约（Camera Contract）

每条提示词的运镜部分必须包含：
1. **一个主运动**（不要堆叠多个不兼容的运镜）
2. **起点**（从什么画面/位置开始）
3. **速度**（缓慢/匀速/快速）
4. **与主体的关系**（推向主体/远离主体/围绕主体/平行跟随）
5. **终点**（运动停在什么画面/构图）

示例（合格）：`缓慢推镜，从远景推进到面部特写，最终停在她低垂的睫毛上`
示例（不合格）：`动态运镜，多角度切换` ← 没有起点、终点、速度

### 运镜语言参考
- 基础：缓慢推镜 / 镜头后拉揭示空间 / 横向稳定跟拍 / 轨道平移 / 固定中景 / 弧形绕摄
- 高级：希区柯克变焦 / 低角度仰拍 / 高角度俯拍 / 第一人称主观 / 手持镜头轻微呼吸晃动
- 景别：极致特写 / 面部特写 / 中近景 / 中景 / 全景 / 远景定场镜头

---

## 四、动作合约（Motion Contract）

动作描述必须包含：主体 + 动作动词 + 时机 + 物理后果 + 终止状态
- 强（合格）：`她吸气，握紧杯子，然后放下，目光没有移开`
- 弱（不合格）：`她感到紧张`

### 物理前置模式
写出原因，让模型计算后果。声明质量、力、材质，然后命名一个镜头能看到的后果：
`沉重的橡木门摆动关闭，烛焰向门的方向弯曲` 胜过 `门戏剧性地关上`

### 时序模式（三拍结构）
短片段用三拍结构：设定 → 动作 → 改变的终态
`0-2秒：烛焰稳定；2-4秒：门打开，焰火弯曲；4-6秒：烟迹向走廊卷曲`

---

## 五、反套话规则（Anti-Slop）

**核心法则：如果镜头、麦克风、测光表或秒表检测不到它，就改写它。**

### 六类套话及修复

| 套话类型 | 表现 | 修复方法 |
|---|---|---|
| 空洞评价词 | 电影感、史诗级、绝美、震撼 | 转换为可观测的具体细节（景别+运镜+光源+调色） |
| 图像模型残留词 | 8K、杰作、获奖、ArtStation trending | 删除；分辨率和质量是参数，不是描述 |
| 标签沙拉 | 逗号分隔关键词堆砌 | 改写为拍摄简报式散文：每个元素一句话 |
| 否定套话 | 不要模糊、不要多余手指、不要水印 | 否定会召唤；改为正面描述存在的内容 |
| 形容词堆叠 | 绝美、令人窒息、迷人的日落 | 三个同义词不如一个关键细节；挑最重要的那个 |
| 感觉后缀词 | 电影感、氛围感、高级感、大片感 | 命名产生这种感觉的物理原因 |

### 中文套话修复表

| 套话 | 改写为 |
|---|---|
| 电影感 | 写出景别、运镜、光源和调色：`宽幅远景，缓慢推镜，低角度暖阳，低饱和青橙调` |
| 氛围感 | 写出制造氛围的物理元素：`薄雾、逆光轮廓、湿润地面反光、低环境声` |
| 高级感 | 写出光线与材质行为：`柔和侧光、受控反光、干净背景、金属拉丝纹理` |
| 大片感 | 写出物理规模：人群数量、镜头距离、建筑高度 |
| 质感（单独使用） | 指明哪种质感：`磨砂玻璃、丝绒吸光、纸张纤维` |
| 震撼 | 写出造成震撼的那一个画面对比或揭示 |
| 唯美 | 写出色彩、构图与光的具体行为 |
| 史诗级 | 删除，或换成具体的空间尺度与人数 |
| 超高清/8K/4K | 删除；分辨率是参数，不是描述 |
| 杰作/顶级品质 | 删除；质量不是请求出来的 |
| 酷炫转场 | 写出转场名称：`匹配剪辑、硬切、甩镜` |

### 否定规则
命名一个缺陷等于种下它。不要写`不要模糊、不要多余手指、不要水印文字`，改为锁定正面：
`双手安静地放在桌上` / `干净完整的标签` / `天空干净无文字`
否定只在约束槽中使用（`不要新增字幕、水印或无关文字`），不要当作质量保险。

---

## 六、中文词汇表（精选）

| 功能 | 中文 | 含义 |
|---|---|---|
| 角色 | @图片1 为首帧 | Image 1 is the first frame |
| 角色 | @图片2 为尾帧 | Image 2 is the last frame |
| 角色 | @图片1 锁定主体身份 | Image 1 locks subject identity |
| 角色 | @图片2 仅参考场景氛围 | Image 2 provides scene mood only |
| 角色 | @视频1 仅参考运镜 | Video 1 provides camera movement only |
| 角色 | @视频1 参考动作节奏 | Video 1 provides action rhythm |
| 角色 | @音频1 参考节奏和氛围 | Audio 1 provides tempo and mood |
| 首尾帧 | 首帧保持不变 | keep first frame unchanged |
| 首尾帧 | 自然过渡到尾帧 | transition naturally to final frame |
| 首尾帧 | 中间动作连续，不跳切 | continuous in-between motion, no jump cut |
| 运镜 | 缓慢推镜 | slow push-in |
| 运镜 | 镜头后拉揭示空间 | pull back to reveal the space |
| 运镜 | 横向稳定跟拍 | stable lateral tracking |
| 运镜 | 固定中景 | locked medium shot |
| 运镜 | 低角度仰拍 | low-angle shot |
| 运镜 | 高角度俯拍 | high-angle shot |
| 运镜 | 过肩镜头 | over-the-shoulder shot |
| 运镜 | 弧形绕摄 | arc orbit shot |
| 运镜 | 手持镜头，轻微呼吸晃动 | handheld shot with slight breathing sway |
| 景别 | 中近景 | medium close-up |
| 景别 | 远景定场镜头 | wide establishing shot |
| 镜头 | 长焦压缩空间 | telephoto compression |
| 镜头 | 广角空间感 | wide-angle spatial feel |
| 镜头 | 焦点从模糊过渡到清晰 | focus resolves from blur to sharpness |
| 光线 | 柔和侧逆光 | soft side backlight |
| 光线 | 暖色实用灯 | warm practical light |
| 光线 | 冷色月光轮廓光 | cool moon rim light |
| 光线 | 体积光穿过薄雾 | volumetric light through mist |
| 光线 | 潮湿地面反射霓虹 | wet ground reflects neon |
| 动作 | 脚步带动薄雾扩散 | footsteps disturb fog |
| 动作 | 水珠聚合后沿表面下滑 | droplets merge and slide down |
| 动作 | 缓慢转头并停住 | slow head turn and stop |
| 动作 | 衣料随动作自然摆动 | fabric moves naturally with action |
| 特效 | 金色粒子升起后消散 | gold particles rise and dissipate |
| 特效 | 蓝色电弧沿边缘游走 | blue arcs crawl along the edge |
| 音频 | 一句短而清晰的对白 | one short clear spoken line |
| 音频 | 无配乐，仅低环境声 | no music, low ambience only |
| 音频 | 对白期间镜头固定 | locked camera during dialogue |
| 音频 | 脚步声卡点 | footsteps hit the beat |
| 约束 | 严格保持logo、标签、形状和颜色不变 | preserve logo, label, shape, and color |
| 约束 | 仅改变动作、光线和镜头 | change only action, light, and camera |
| 安全 | 改为原创角色 | change to an original character |
| 安全 | 仅使用已授权参考 | use only authorized references |

### 紧凑模板
`@图片1为参考，严格保持[主体/产品/脸部/标志]不变；仅加入[动作/光线/镜头变化]。镜头：[一个动作]。声音：[音效或环境声]。`

### 时间轴模板（8秒以上使用）
```
【风格】[媒介、质感、色调，一句话]
【时间轴】0-3s：[画面+镜头+音效]；3-6s：[画面+镜头+音效]；6-10s：[画面+镜头+音效]
【声音】[对白/环境声/音效/无配乐]
【参考】@图片1 锁定主体身份；@视频1 仅参考运镜；@音频1 仅参考节奏
```

---

## 七、提示词结构公式

### 基本公式
[模式声明] + [主体/人物设定] + [场景/环境] + [一个动作+后果+终态] + [一个运镜（起点→速度→终点）] + [分时段描述] + [音频/音效设计] + [风格/材质/光源] + [@引用角色说明] + [约束]

### 分时段提示词（10秒以上推荐）
```
0-3秒：[开场画面描述、运镜、动作]
3-6秒：[中段发展]
6-10秒：[高潮或关键动作]
10-15秒：[收尾、定格画面、品牌文字]
```

---

## 八、提示词检查清单（输出前自检）

| 门控 | 通过条件 |
|---|---|
| 模式 | T2V/I2V/V2V/R2V 已明确声明 |
| 引用 | 每个素材有且仅有一个主角色（除非刻意分层） |
| 主体 | 主体出现在首句并有稳定标签 |
| 动作 | 一个可见拍有可观测的终点 |
| 运镜 | 一个主运动有起点、速度、主体关系和终点 |
| 光线 | 光源、方向、色温、氛围或转变是物理的 |
| 音频 | 对白、环境、音效、音乐或静默是有意图的 |
| 反套话 | 空洞修饰词已被替换为可观测生产语言 |
| 否定 | 否定仅在约束槽使用，未当作质量保险 |
| 预算 | 最终提示词长度合理，未过载 |
| 时长 | 提示词复杂度与选定生成时长匹配 |

---

## 九、常见错误避坑
1. 引用模糊：不要只写"参考@视频1"，必须说清楚参考什么（运镜/动作/特效/节奏）
2. 指令冲突：不要同时要求"固定镜头"和"环绕镜头"
3. 内容过载：不要在4-5秒内塞入太多场景
4. 素材无归属：每个@引用都必须标注清楚用途
5. 忽视音频：音效设计能大幅提升输出质量
6. 时长不匹配：提示词复杂度要与选定生成时长匹配
7. 写实人脸：不要上传包含真人清晰可辨识面部的素材
8. 套话堆砌：不要用"电影感""史诗级""绝美"等空洞词，改写为可观测细节
9. 动作无后果：不要只写情绪（"她很紧张"），改写为身体动作+后果+终态
10. 运镜无终点：不要写"动态运镜"，必须给出起点→速度→终点

---

## 输出 JSON 结构
请严格输出以下 JSON 结构：

{
  "skill_id": "seedance-prompt-zh",
  "skill_name": "Seedance提示词生成",
  "scene_type": "场景类型",
  "mode": "生成模式（T2V/I2V/V2V/R2V）",
  "duration": "生成时长",
  "title": "提示词标题（简短概括）",
  "summary": "一句话说明这条提示词的核心创意和导演意图",
  "director_intent": "导演意图一句话（这个镜头要完成什么价值翻转或情感目标）",
  "prompt": "完整的Seedance 2.0提示词文本（可直接复制使用，必须包含模式声明）",
  "camera_contract": "镜头合约：主运动 + 起点 + 速度 + 主体关系 + 终点",
  "motion_contract": "动作合约：主体 + 动作动词 + 时机 + 物理后果 + 终止状态",
  "segment_description": "分时段描述（如果时长≥10秒则提供，否则留空）",
  "references": [
    {
      "ref": "@图片1",
      "purpose": "用途说明（如：作为首帧/人物形象参考/场景参考等）",
      "exclusion": "排他约束（如：仅参考运镜，不复制身份）— 如无则留空"
    }
  ],
  "audio_design": "音频/音效设计指导",
  "style_modifiers": "风格与质感修饰词（必须是可观测的物理描述，不含套话）",
  "anti_slop_check": "反套话自检结果：列出已替换的套话及改写内容",
  "tips": "使用建议与注意事项"
}

## 约束
- 只输出 JSON，不要在 JSON 外输出任何 Markdown 或解释文字
- 提示词中所有@引用都必须有明确用途说明
- 如果用户提供了素材说明，提示词中必须为每个素材分配@引用
- 如果用户选择了I2V/V2V/R2V模式但未提供素材，在tips中提醒
- 时长≥10秒时必须提供分时段描述
- 必须包含音频/音效设计指导
- prompt字段必须以模式声明开头（如"[T2V]"或"[I2V]"）
- camera_contract和motion_contract必须填写，不能留空
- style_modifiers中不得出现套话（电影感/史诗级/绝美等），必须为可观测物理描述
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

        scene_type = str(merged.get("场景类型", "人物一致性"))
        mode = str(merged.get("生成模式", "T2V（纯文本生成视频）"))
        duration = str(merged.get("生成时长", "10秒"))
        assets_desc = str(merged.get("素材说明", ""))

        # 提取模式简称
        mode_short = mode.split("（")[0] if "（" in mode else mode

        user_content = f"""\
内容描述：
{user_input}

场景类型：{scene_type}
生成模式：{mode}
生成时长：{duration}
"""
        if assets_desc and assets_desc.strip():
            user_content += f"\n已有素材：{assets_desc}\n"
        else:
            user_content += f"\n已有素材：无\n"
            if mode_short in ("I2V", "V2V", "R2V"):
                user_content += "（注意：用户选择了需要素材的模式但未提供素材说明，请在tips中提醒）\n"

        # 注入多轮对话历史上下文
        result = await llm_json(
            system_prompt,
            user_content,
    model=self._llm_model,
            history=history,
            max_tokens=8192,
            temperature=0.5,
            fallback={
                "skill_id": self.info.skill_id,
                "skill_name": self.info.skill_name,
                "scene_type": scene_type,
                "mode": mode_short,
                "duration": duration,
                "title": "",
                "summary": "",
                "director_intent": "",
                "prompt": "",
                "camera_contract": "",
                "motion_contract": "",
                "segment_description": "",
                "references": [],
                "audio_design": "",
                "style_modifiers": "",
                "anti_slop_check": "",
                "tips": "",
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
        parts: list[str] = []

        title = result.get("title", "")
        if title:
            parts.append(f"# {title}\n")

        summary = result.get("summary", "")
        if summary:
            parts.append(f"> {summary}\n")

        scene_type = result.get("scene_type", "")
        duration = result.get("duration", "")
        mode = result.get("mode", "")
        if scene_type or duration or mode:
            parts.append(f"**场景类型**：{scene_type} | **生成模式**：{mode} | **生成时长**：{duration}\n")

        # 导演意图
        director_intent = result.get("director_intent", "")
        if director_intent:
            parts.append(f"**导演意图**：{director_intent}\n")

        # 镜头合约
        camera_contract = result.get("camera_contract", "")
        if camera_contract:
            parts.append("## 镜头合约\n")
            parts.append(camera_contract)
            parts.append("")

        # 动作合约
        motion_contract = result.get("motion_contract", "")
        if motion_contract:
            parts.append("## 动作合约\n")
            parts.append(motion_contract)
            parts.append("")

        # @引用说明
        references = result.get("references", [])
        if references:
            parts.append("## 素材引用说明\n")
            for ref in references:
                line = f"- `{ref.get('ref', '')}` — {ref.get('purpose', '')}"
                exclusion = ref.get("exclusion", "")
                if exclusion:
                    line += f" ｜ 排他：{exclusion}"
                parts.append(line)
            parts.append("")

        # 完整提示词
        prompt = result.get("prompt", "")
        if prompt:
            parts.append("---\n\n## 完整提示词\n")
            parts.append(f"```\n{prompt}\n```")
            parts.append("")

        # 分时段描述
        segment_desc = result.get("segment_description", "")
        if segment_desc:
            parts.append("## 分时段描述\n")
            parts.append(segment_desc)
            parts.append("")

        # 音频设计
        audio_design = result.get("audio_design", "")
        if audio_design:
            parts.append("## 音频/音效设计\n")
            parts.append(audio_design)
            parts.append("")

        # 风格修饰词
        style_modifiers = result.get("style_modifiers", "")
        if style_modifiers:
            parts.append("## 风格修饰词\n")
            parts.append(style_modifiers)
            parts.append("")

        # 反套话自检
        anti_slop = result.get("anti_slop_check", "")
        if anti_slop:
            parts.append("## 反套话自检\n")
            parts.append(anti_slop)
            parts.append("")

        # 使用建议
        tips = result.get("tips", "")
        if tips:
            parts.append("## 使用建议\n")
            parts.append(tips)
            parts.append("")

        return "\n".join(parts)
