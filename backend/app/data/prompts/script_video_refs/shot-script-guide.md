# 分镜脚本设计标准

## 镜头设计要素

每个镜头必须明确以下维度：

### 1. 景别（Shot Type）
- 大全景（Extreme Wide）：交代环境全貌，人物渺小
- 全景（Wide）：人物全身+环境，空间关系清晰
- 中景（Medium）：人物腰部以上，日常互动距离
- 中近景（Medium Close-up）：胸部以上，对话常用
- 近景（Close-up）：肩部以上，情绪表达
- 特写（Close-up）：面部或物体细节
- 大特写（Extreme Close-up）：极局部，眼睛/手指/嘴唇

### 2. 视角（Angle）
- 平视（Eye Level）：平等、客观
- 仰视（Low Angle）：权威、压迫、力量
- 俯视（High Angle）：弱小、无助、审视
- 鸟瞰（Bird's Eye）：全知视角、几何构图
- 倾斜（Dutch Tilt）：不安、失衡、疯狂

### 3. 运镜（Camera Move）
- 固定（Static）：稳定观察
- 推（Dolly/Push-in）：靠近、聚焦、压迫
- 拉（Dolly-out/Pull-back）：远离、揭示、释放
- 摇（Pan/Tilt）：水平/垂直转动
- 移（Tracking）：平行移动
- 升降（Crane/Boom）：垂直方向大范围移动
- 手持（Handheld）：不稳定、纪实感
- 跟拍（Follow）：跟随主体
- 航拍（Drone）：空中视角
- 环绕（Orbit）：围绕主体旋转

### 4. 焦段（Lens）
- 广角 24mm：空间感、透视夸张
- 标准 35-50mm：自然视角、人眼近似
- 长焦 85mm：压缩空间、浅景深、人像
- 微距（Macro）：极近细节

### 5. 光影（Lighting）
| 光线类型 | 情绪 | 适用场景 |
|---|---|---|
| golden_hour | 温暖、怀旧 | 黄昏/清晨外景 |
| blue_hour | 忧郁、冷峻 | 黎明/黄昏过渡 |
| overcast | 柔和、平静 | 阴天外景 |
| hard_daylight | 强烈、真实 | 正午烈日 |
| interior_warm | 温馨、亲密 | 室内暖灯 |
| interior_cool | 冷漠、压抑 | 室内冷灯/办公室 |
| backlight | 轮廓、神圣 | 逆光剪影 |
| candlelight | 亲密、温暖 | 烛光场景 |
| neon | 赛博、都市 | 霓虹灯场景 |
| moonlight | 神秘、清冷 | 夜晚月光 |

### 6. 构图（Composition）
- 三分法（Rule of Thirds）：主体在三分之一线交点
- 黄金比例（Golden Ratio）：螺旋构图
- 对称（Symmetry）：居中对称
- 引导线（Leading Lines）：线条引向主体
- 框中框（Frame within Frame）：门框/窗框/镜框
- 负空间（Negative Space）：大面积留白
- 居中构图（Center Composition）：主体居中
- 对角线（Diagonal）：动态张力

### 7. 景深（Depth of Field）
- 浅（Shallow）：主体清晰，背景模糊——特写/情绪
- 中（Medium）：主体清晰，背景可辨认——对话/中景
- 深（Deep）：全景清晰——风景/大全景

## 镜头描述规范
每个镜头的 `desc` 字段必须包含：
1. 画面主体在做什么（可见动作）
2. 环境氛围如何（光线/天气/质感）
3. 构图关系如何（主体位置/背景关系）
