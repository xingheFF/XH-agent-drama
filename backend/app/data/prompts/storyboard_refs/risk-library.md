# 风险库（逐帧风险注入）

## A库：生图风险（注入分镜故事板提示词）

| 风险关键词 | 触发条件 | 注入约束 |
|---|---|---|
| 多人同框 | 帧内≥3人 | `consistent character design, distinct silhouettes, no face blending` |
| 手部特写 | 景别=特写/大特写 + 手部动作 | `detailed hands, correct finger count, natural hand pose` |
| 文字/招牌 | 画面含文字、Logo、路牌 | `no garbled text, clean signage, legible letters` |
| 动物/非人物 | 画面含动物或奇幻生物 | `anatomically correct, natural posture, consistent species design` |
| 建筑透视 | 全景/大全景 + 建筑 | `correct perspective vanishing point, straight architectural lines` |
| 雨雪天气 | 环境含雨/雪/雾 | `natural particle distribution, no clumping, depth-aware fog` |
| 镜面反射 | 画面含镜子/水面反射 | `accurate mirror reflection, consistent reflected content` |
| 暗部细节 | 低调光影 + 暗部占比>50% | `preserve shadow detail, no crushed blacks, subtle gradation` |

## B库：视频风险（注入视频提示词）

| 风险关键词 | 触发条件 | 注入约束 |
|---|---|---|
| 快速运动 | 运镜=快速移/甩镜 | `motion blur on fast pan, no frame tearing, smooth motion interpolation` |
| 人物运动 | 主体运动=active/intense | `stable body proportions, no limb distortion, weight shift visible` |
| 长镜头 | 单帧时长≥4s | `maintain quality throughout, no degradation, consistent lighting` |
| 航拍/升降 | 运镜=航拍/升降 | `smooth aerial movement, no jitter, stable horizon line` |
| 水面/液体 | 画面含水/液体 | `realistic fluid dynamics, no frozen water, natural ripple spread` |
| 火焰/烟雾 | 画面含火/烟 | `natural flame flicker, smoke rises and dissipates, no static fire` |
| 多体交互 | 帧内≥2人且有肢体接触 | `clear contact points, no body merging, natural interaction physics` |
| 面部表情 | 景别=近景/特写 + 情绪=D/E | `subtle facial micro-expression, no exaggeration, natural eye movement` |

## C库：组合场景风险（整段套用）

| 场景类型 | 整段约束 |
|---|---|
| 动作戏连续镜头 | `maintain screen direction consistency, 180-degree rule, consistent spatial geography` |
| 情感对话场景 | `eye-line match, consistent character heights, natural shot-reverse-shot rhythm` |
| 环境建立段落 | `progressive disclosure, consistent time-of-day lighting, establishing geography` |
| 蒙太奇段落 | `consistent style across cuts, rhythmic pacing, visual continuity through color/motion` |
| 回忆/闪回 | `distinct visual treatment (grade/aspect), clear transition cues, return to present` |
