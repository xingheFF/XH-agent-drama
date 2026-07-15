# Golden Example（完整格式范例）

## 输入故事文本（节选）
> 雨夜，陈明站在老宅门前，犹豫片刻后推门而入。屋内漆黑，他打开手机电筒，光柱扫过布满灰尘的家具。突然，桌上的一张老照片引起了他的注意——照片上的人，竟然是他自己。

## 分镜脚本设计确认表

| 帧号 | 时长 | 标注 | 景别 | 视角 | 运镜 | 焦段 | 景深 | 环境 | 光影 | 构图 | 表演 | 查询标注 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1.0s | 01·固定·远景 | 远景 | 平视 | 固定 | 35mm | 深 | 雨夜老宅外 | 冷蓝月光+暖黄路灯 | 负空间，人物偏下三分之一 | 陈明撑伞站立，犹豫 | F·孤独 |
| 2 | 1.0s | 02·缓推·中景 | 中景 | 平视 | 缓慢推 | 50mm | 中 | 老宅门廊 | 低调，门缝微光 | 居中，门框框中框 | 手伸向门把 | G·期待 |
| 3 | 1.0s | 03·固定·近景 | 近景 | 微仰 | 固定 | 85mm | 浅 | 屋内黑暗 | 手机电筒冷白光柱 | 对角线，光柱切割画面 | 推门进入，光扫室内 | B·紧张 |
| 4 | 1.5s | 04·缓推·特写 | 特写 | 俯视 | 缓慢推 | 85mm macro | 极浅 | 桌面近景 | 电筒侧光，灰尘颗粒 | 居中，照片为主体 | 手拿起照片 | G·期待 |
| 5 | 1.0s | 05·固定·大特写 | 大特写 | 平视 | 固定 | 85mm | 极浅 | 照片细节 | 侧光显纹理 | 满屏，照片中人脸清晰 | 凝视，瞳孔微缩 | D·压抑 |

总帧数：5 | 总时长：5.5s | 布局：1行×5列（9:16竖屏）

---

## 多宫格分镜故事板提示词

```
【全局规则】
手绘铅笔草稿风格，黑白线条，木偶小人构图。
9:16竖屏，1行5列布局，每帧宽高比3:4。
帧间无间距，白色背景，帧序号标注在左上角。

【全局风险约束】
consistent character design across all frames, distinct silhouettes, no face blending
correct perspective vanishing point, straight architectural lines
preserve shadow detail, no crushed blacks, subtle gradation

【分镜板逐帧设计】

Frame 01 (1.0s):
Wide establishing shot, a lone figure with umbrella standing before an old house at night in rain.
Camera: static, eye-level, 35mm, deep depth of field.
Light: cold blue moonlight from upper left, warm yellow street lamp from right.
Composition: negative space, figure placed on lower third, rain filling upper two-thirds.
Mood: isolation, hesitation.
same person, consistent clothing design

Frame 02 (1.0s):
Medium shot, figure's hand reaching for old wooden door handle, door slightly ajar with light leak.
Camera: slow push-in, eye-level, 50mm, medium depth of field.
Light: low-key, warm light leaking from door gap.
Composition: centered, door frame as frame-within-frame.
Mood: anticipation, suspense.
same person, consistent clothing design

Frame 03 (1.0s):
Close-up, figure entering dark room, phone flashlight beam cutting through dust particles.
Camera: static, slight low-angle, 85mm, shallow depth of field.
Light: cold white phone torch as hard directional light, dust motes visible in beam.
Composition: diagonal, light beam divides frame.
Mood: tension, unease.
same person, consistent clothing design

Frame 04 (1.5s):
Extreme close-up, hand picking up an old photograph from dusty table surface.
Camera: slow push-in, overhead angle, 85mm macro, extremely shallow depth of field.
Light: flashlight side-light revealing paper texture, dust particles.
Composition: centered, photograph as main subject.
Mood: discovery, anticipation.
detailed hands, correct finger count, natural hand pose

Frame 05 (1.0s):
Extreme close-up, photograph showing a face — it is the same person, younger.
Camera: static, eye-level, 85mm, extremely shallow depth of field.
Light: side light revealing photo paper texture and aging.
Composition: full frame, face in photograph is sharp.
Mood: shock, dread.
no garbled text, clean photograph surface

【负面提示】
modern buildings, cars, neon signs, deformed hands, extra fingers, merged faces, inconsistent clothing, text watermark, jpeg artifacts
```

---

## 视频提示词

```
【参考素材】
@陈明；@老宅外景；@老宅内景；@老照片

【视频风格】
写实风格，冷色调为主，雨夜氛围
- 时间：夜晚
- 光源：月光（冷蓝）+ 路灯（暖黄）+ 手机电筒（冷白）
- 色温：约3200K-4500K混合
- 动态元素：雨滴下落，灰尘颗粒飘浮
- 氛围：悬疑、压抑、孤寂
- 微细节：衣物湿润反光，呼吸可见白雾

【视频内容】
0-1.0s：远景固定镜头，陈明撑伞站在雨夜老宅前，雨水持续下落，人物微微犹豫后向前迈步。
1.0-2.0s：中景缓推，手伸向门把推开门，门缝漏出微光，雨声渐弱。
2.0-3.0s：近景固定，推门进入漆黑屋内，手机电筒光柱扫过布满灰尘的家具，灰尘颗粒在光柱中飘浮。
3.0-4.5s：特写缓推，手拿起桌上老照片，电筒侧光照亮照片表面纹理。
4.5-5.5s：大特写固定，照片特写——照片上的人竟是自己，瞳孔微缩，画面静止。

视频约束：
无字幕、无水印、无背景音乐。保持角色外观全程一致。雨滴方向和密度保持一致。灰尘粒子自然飘浮不循环。
```
