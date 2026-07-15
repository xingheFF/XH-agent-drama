# 各步骤输出范例

## 阶段① 输出范例：角色/场景/道具清单 + 合并表

```json
{
  "characters": [
    {"name": "陈明", "voice": "男，30岁，沉稳、略带沙哑"},
    {"name": "林雪", "voice": "女，25岁，清亮、温柔"}
  ],
  "scenes": [
    {"name": "老宅外景", "description": "雨夜的皖南老宅，青石板路"},
    {"name": "老宅内景", "description": "昏暗的老宅堂屋，布满灰尘"}
  ],
  "props": [
    {"name": "老照片", "scene": "老宅内景", "note": "泛黄的黑白照片"}
  ],
  "merge_table": [
    {"unit": "视频单元1", "shot": "镜1,镜2", "script": "陈明雨夜来到老宅，推门而入"},
    {"unit": "视频单元2", "shot": "镜3", "script": "屋内黑暗，电筒扫过灰尘家具"},
    {"unit": "视频单元3", "shot": "镜4,镜5", "script": "发现桌上老照片，竟是自己的脸"}
  ]
}
```

## 阶段② 输出范例：分镜脚本设计

```json
{
  "shot_script_details": [
    {
      "unit_number": "视频单元1",
      "shot_number": "镜1",
      "shot_type": "远景",
      "angle": "平视",
      "movement": "固定",
      "composition": "负空间，人物偏下三分之一",
      "lighting": "冷蓝月光+暖黄路灯",
      "performance": "陈明撑伞站立，犹豫后向前走",
      "dialogue": "",
      "sound_effect": "雨声",
      "continuity_check": "与镜2衔接：推门动作需连贯"
    }
  ]
}
```

## 阶段③ 输出范例：Seedance 提示词

```
【第1集-01 | 总时长5s】
【参考素材】
@陈明；
@老宅外景；
@老宅内景；

【视频风格】
写实电影感，自然皮肤质感，35mm镜头视角，浅景深，柔和色调过渡，PBR物理材质渲染
- 时间：夜晚
- 光源：月光（冷蓝）为主，路灯（暖黄）为辅
- 色温：约4500K冷调为主
- 动态元素：雨滴持续下落
- 氛围：悬疑、孤寂、压抑
- 微细节：衣物湿润反光，呼吸可见白雾

【视频内容】
陈明撑伞站在雨夜的老宅门前，犹豫片刻后向前迈步，手伸向门把推门而入。屋内漆黑，他打开手机电筒，冷白光柱扫过布满灰尘的家具。光柱掠过桌面时，一张泛黄的老照片引起他的注意——他拿起照片，照片上的人竟然是他自己。

视频约束：
无字幕、无水印、无背景音乐。保持角色外观全程一致。雨滴方向和密度保持一致。
```

## 完整 JSON 输出结构

```json
{
  "skill_id": "script-video-prompt-architect",
  "skill_name": "短剧视频提示词架构师",
  "episode": "第1集",
  "style": "真人写实",
  "aspect_ratio": "9:16",
  "characters": [...],
  "scenes": [...],
  "props": [...],
  "merge_table": [...],
  "shot_script_details": [...],
  "video_units": [
    {
      "unit_id": "第1集-01",
      "duration": "5s",
      "prompt": "【第1集-01 | 总时长5s】\n【参考素材】\n...",
      "characters_in_unit": ["陈明"],
      "scenes_in_unit": ["老宅外景", "老宅内景"]
    }
  ],
  "total_units": 3,
  "total_duration": "12s"
}
```
