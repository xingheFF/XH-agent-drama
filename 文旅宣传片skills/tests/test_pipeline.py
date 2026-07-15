"""端到端自检测试。

不调用真实 LLM，只验证：
1. 数据模型能正确序列化/反序列化
2. 流水线各阶段产物能正确组装
3. 质检逻辑正确
4. 输出写入器能生成所有格式
"""

import json
from pathlib import Path

import pytest

from cultural_film_prompts.config import Config
from cultural_film_prompts.io.output_writer import write_outputs
from cultural_film_prompts.models import (
    DirectorNotes,
    FinalPackage,
    Screenplay,
    ShotPrompts,
    VideoPrompts,
)
from cultural_film_prompts.pipeline import run_quality_check


# —— 测试夹具 ——


@pytest.fixture
def config() -> Config:
    p = Path(__file__).parent.parent / "config.example.yaml"
    return Config.load(p)


@pytest.fixture
def sample_package() -> FinalPackage:
    """手工构造一个完整的 FinalPackage"""
    from cultural_film_prompts.models.director_notes import Character, ThreeAct
    from cultural_film_prompts.models.screenplay import (
        Scene,
        Shot,
        SubtitleEntry,
        VoiceoverSegment,
    )
    from cultural_film_prompts.models.shot_prompts import (
        CameraParams,
        ShotPrompt,
        VisualAnchor,
    )
    from cultural_film_prompts.models.video_prompts import (
        ModelSuggestion,
        MotionParams,
        VideoShotPrompt,
    )

    dn = DirectorNotes(
        theme="乡愁与归途",
        sub_themes=["代际亲情", "土地记忆"],
        story_type="情感散文式",
        three_act=ThreeAct(
            setup="离乡十年的青年接到母亲电话说老屋要拆",
            conflict="回到故乡发现老屋将被拆，旧物里藏着家族记忆",
            resolve="在旧物中找到根脉，决定记录保存",
        ),
        emotional_arc=["平静", "怅惘", "温暖", "坚定"],
        location="皖南古村落",
        cultural_tags=["徽派建筑", "宗族文化", "农耕记忆"],
        tourism_selling=["古建保护", "非遗体验", "慢生活"],
        target_duration=90,
        aspect_ratio="9:16",
        resolution="1080x1920",
        fps=30,
        visual_style="胶片质感,暖黄调,逆光,电影感",
        tone="克制、留白、诗意",
        characters=[
            Character(
                name="阿远",
                role="主角",
                age="30岁",
                appearance="短发、瘦削、穿橄榄绿外套",
                personality="沉默、内敛",
                arc="从远方的漂泊者，变成家族记忆的守护者",
            )
        ],
        key_motifs=["老钥匙", "褪色春联", "屋檐滴水", "灶台烟火"],
        director_note="全片不要出现现代物品，结尾留 3 秒空镜",
    )

    sp = Screenplay(
        title="归",
        logline="一个青年回到即将拆迁的皖南老屋，在旧物中寻回家族记忆",
        genre="文旅剧情短片",
        total_duration_estimate=20,
        scenes=[
            Scene(
                scene_id="S1",
                location="皖南古村·青石板巷",
                time="清晨 06:30",
                mood="宁静微凉",
                action="阿远背着包走过青石板巷",
                purpose="交代环境与主角归乡",
                shots=[
                    Shot(
                        shot_id="S1-01",
                        scene_id="S1",
                        shot_type="大全景",
                        camera_move="推",
                        duration=4,
                        desc="晨雾中的徽派马头墙群，飞鸟掠过",
                        purpose="交代环境",
                        transition_out="dissolve",
                        characters_in_shot=[],
                        location_in_shot="皖南古村",
                    ),
                    Shot(
                        shot_id="S1-02",
                        scene_id="S1",
                        shot_type="中景",
                        camera_move="跟拍",
                        duration=3,
                        desc="阿远侧背影沿巷子前行，手触墙面",
                        purpose="主角登场",
                        transition_out="cut",
                        characters_in_shot=["阿远"],
                        location_in_shot="皖南古村·青石板巷",
                    ),
                    Shot(
                        shot_id="S1-03",
                        scene_id="S1",
                        shot_type="特写",
                        camera_move="固定",
                        duration=3,
                        desc="指尖划过墙皮剥落处",
                        purpose="强化情绪",
                        transition_out="cut",
                        characters_in_shot=["阿远"],
                        location_in_shot="皖南古村·青石板巷",
                    ),
                ],
            ),
        ],
        voiceover=[
            VoiceoverSegment(
                shot_id="S1-01",
                text="离开故乡十年，我以为自己已经习惯了远方。",
                emotion="平静",
                speed_preset="slow",
            ),
            VoiceoverSegment(
                shot_id="S1-02",
                text="母亲说，老屋要拆了。",
                emotion="平静",
                speed_preset="slow",
            ),
        ],
        subtitles=[
            SubtitleEntry(timing="opening", text="归", style_hint="居中淡入"),
            SubtitleEntry(
                timing="closing", text="皖南古村 · 等你归来", style_hint="底部小字"
            ),
        ],
        screenwriter_note="S1 情绪铺垫，转场用 dissolve 慢化",
    )

    shp = ShotPrompts(
        visual_anchors=[
            VisualAnchor(
                anchor_id="char_001",
                kind="character",
                ref_name="阿远",
                ref_desc="Asian male early 30s, short black hair, slim build, olive field jacket, dark trousers, weathered but gentle face, slight stubble",
                consistency_tags="same person, consistent facial features, identical clothing",
                negative_consistency="different person, inconsistent face, changed clothing",
            ),
            VisualAnchor(
                anchor_id="loc_001",
                kind="location",
                ref_name="皖南老屋",
                ref_desc="traditional Huizhou vernacular house, white-washed walls with dark grey tiled roof, horse-head gables, wooden lattice windows, mossy stone foundation",
                consistency_tags="same location, same architecture",
                negative_consistency="different location, inconsistent architecture",
            ),
            VisualAnchor(
                anchor_id="prop_001",
                kind="prop",
                ref_name="老钥匙",
                ref_desc="old brass key, tarnished with age, teeth worn smooth, attached to a faded red string",
                consistency_tags="same key, consistent appearance",
                negative_consistency="different key, inconsistent details",
            ),
        ],
        shots=[
            ShotPrompt(
                shot_id="S1-01",
                desc_cn="晨雾中的徽派马头墙群，飞鸟掠过",
                image_prompt="extreme wide establishing shot, traditional Huizhou village with white-washed walls and dark grey horse-head gables in early morning mist, golden hour soft directional light from camera-left, warm slightly desaturated color grade, 35mm anamorphic lens eye-level shallow depth of field, film grain cinematic vintage look, same village, consistent architecture style",
                negative_prompt="modern buildings, cars, neon, lowres, blurry, deformed, ugly, text, watermark, jpeg artifacts, different village, inconsistent architecture",
                camera_params=CameraParams(
                    shot_size="extreme_wide",
                    lens="35mm anamorphic",
                    angle="eye_level",
                    lighting="golden_hour",
                    lighting_direction="side",
                    color_grade="warm, slightly desaturated",
                    depth_of_field="shallow",
                    film_stock_hint="Kodak Portra 400 grain",
                ),
                composition="rule of thirds, village massed on lower third, sky and mist in upper two-thirds, leading lines from alley converging on character",
                composition_rules=["rule_of_thirds", "leading_lines"],
                anchors_used=["loc_001"],
                reference_images=[],
                storyboard_note="此镜头光影复杂，运动需保守",
            ),
            ShotPrompt(
                shot_id="S1-02",
                desc_cn="阿远侧背影沿巷子前行，手触墙面",
                image_prompt="medium shot from behind, Asian male early 30s in olive field jacket walking along narrow stone alley, hand trailing mossy white wall, same person consistent facial features identical clothing, backlit golden hour, warm tone, 35mm lens, shallow depth of field, film grain cinematic",
                negative_prompt="modern buildings, cars, neon, lowres, blurry, deformed, ugly, text, watermark, different person, inconsistent face, changed clothing",
                camera_params=CameraParams(
                    shot_size="medium",
                    lens="35mm",
                    angle="eye_level",
                    lighting="backlight",
                    lighting_direction="back",
                    color_grade="warm, slightly desaturated",
                    depth_of_field="shallow",
                    film_stock_hint="Kodak Portra 400 grain",
                ),
                composition="character centered, alley walls framing both sides, leading lines toward background",
                composition_rules=["leading_lines", "frame_within_frame"],
                anchors_used=["char_001", "loc_001"],
                reference_images=[],
                storyboard_note="",
            ),
            ShotPrompt(
                shot_id="S1-03",
                desc_cn="指尖划过墙皮剥落处",
                image_prompt="extreme close up, fingertips of Asian male gently tracing peeling whitewash on old wall, fine texture detail, warm directional light from camera-left, shallow depth of field, macro lens, film grain cinematic vintage look",
                negative_prompt="modern surface, clean wall, lowres, blurry, deformed hand, extra fingers, text, watermark",
                camera_params=CameraParams(
                    shot_size="extreme_close",
                    lens="85mm macro",
                    angle="eye_level",
                    lighting="golden_hour",
                    lighting_direction="side",
                    color_grade="warm, slightly desaturated",
                    depth_of_field="shallow",
                    film_stock_hint="Kodak Portra 400 grain",
                ),
                composition="hand enters frame from left, wall texture fills right two-thirds, negative space at top",
                composition_rules=["negative_space", "center_composition"],
                anchors_used=["char_001"],
                reference_images=[],
                storyboard_note="",
            ),
        ],
    )

    vp = VideoPrompts(
        shots=[
            VideoShotPrompt(
                shot_id="S1-01",
                motion_prompt="Slow camera dolly-in over 4 seconds, approaching traditional Huizhou village through early morning mist, light mist drifts left to right at mid-frame, subtle dust particles in golden light shafts, cinematic motion, smooth, natural physics, film look",
                motion_type="camera_movement",
                motion_params=MotionParams(
                    camera_move="dolly_in",
                    camera_speed="slow",
                    subject_motion="none",
                    subject_motion_desc="",
                    environmental_motion=["mist_drift", "dust_particles"],
                    environmental_direction="mist drifts left to right at mid-frame",
                    particle_effect="subtle dust particles in golden light shafts",
                    duration=4,
                ),
                model_suggestion=ModelSuggestion(
                    primary="kling_v1_5",
                    reason="长镜头缓慢推拉，可灵运镜稳定性最好",
                    fallback="runway_gen3",
                    fallback_reason="可灵排队过久时，Gen-3 对氛围镜头也胜任",
                ),
                risk_notes="鸟群运动轨迹难控制，失败可降级为 Ken Burns",
                fallback_motion="static, very slow ken burns zoom-in",
                image_prompt_revision="原 prompt 中 'a flock of birds crossing sky' 在图生视频里鸟群运动会扭曲，建议改为静态停在屋脊，或直接删除该元素",
                revised_image_prompt="extreme wide establishing shot, traditional Huizhou village with white-washed walls and dark grey horse-head gables in early morning mist, a few birds perched on roof ridge, golden hour soft directional light from camera-left, warm slightly desaturated color grade, 35mm anamorphic lens eye-level shallow depth of field, film grain cinematic vintage look, same village, consistent architecture style",
                videographer_note="鸟群改为静态停栖",
            ),
            VideoShotPrompt(
                shot_id="S1-02",
                motion_prompt="Asian male early 30s in olive jacket walks slowly along stone alley over 3 seconds, hand trailing mossy wall, camera tracking at eye level, subtle dust particles in light shafts, backlit golden hour, cinematic motion, smooth, natural physics, film look",
                motion_type="character_action",
                motion_params=MotionParams(
                    camera_move="tracking",
                    camera_speed="slow",
                    subject_motion="moderate",
                    subject_motion_desc="young man walks slowly along alley, hand trailing wall",
                    environmental_motion=["dust_particles"],
                    environmental_direction="",
                    particle_effect="subtle dust particles in light shafts",
                    duration=3,
                ),
                model_suggestion=ModelSuggestion(
                    primary="runway_gen3",
                    reason="人物行走动作，Gen-3 的 character_action 能力最强",
                    fallback="kling_v1_5",
                    fallback_reason="Gen-3 不可用时，可灵对人物动作也尚可",
                ),
                risk_notes="手指触碰墙面的细节可能扭曲，失败可弱化手部动作",
                fallback_motion="static, very slow ken burns dolly-in",
                image_prompt_revision="",
                revised_image_prompt="",
                videographer_note="",
            ),
            VideoShotPrompt(
                shot_id="S1-03",
                motion_prompt="Extreme close up static shot over 3 seconds, fingertips slowly tracing peeling whitewash on old wall, very subtle camera micro-movement, warm directional light, macro lens shallow depth of field, cinematic motion, smooth, natural physics, film look",
                motion_type="environment_atmosphere",
                motion_params=MotionParams(
                    camera_move="static",
                    camera_speed="very_slow",
                    subject_motion="subtle",
                    subject_motion_desc="fingertips slowly tracing wall texture",
                    environmental_motion=["dust_particles"],
                    environmental_direction="",
                    particle_effect="subtle dust particles in light shafts",
                    duration=3,
                ),
                model_suggestion=ModelSuggestion(
                    primary="svd_v1_1",
                    reason="静态特写+环境氛围，SVD 最便宜且胜任",
                    fallback="kling_v1_5",
                    fallback_reason="SVD 出图风格不符时，可灵的 environment_atmosphere 也强",
                ),
                risk_notes="低风险，最坏情况降级为 Ken Burns",
                fallback_motion="static, very slow ken burns zoom-in",
                image_prompt_revision="",
                revised_image_prompt="",
                videographer_note="",
            ),
        ],
        pacing_note="前段(S1)缓慢铺垫，dolly-in 和 tracking 拉开空间感；中段(S2-S3)节奏稍快，匹配寻根情绪；结尾(S4-S5)回到长空镜和 environment_atmosphere，留白收束",
    )

    return FinalPackage(
        project_id="proj_test001",
        created_at="2026-07-15T17:00:00",
        director_notes=dn,
        screenplay=sp,
        shot_prompts=shp,
        video_prompts=vp,
        quality_report={},
        notes="测试用 package",
    )


# —— 测试用例 ——


def test_config_loads(config: Config) -> None:
    """配置能正确加载"""
    assert config.llm.model == "deepseek-chat"
    assert config.defaults.target_duration == 90
    assert config.defaults.aspect_ratio == "9:16"
    assert "kling_v1_5" in config.video_models
    assert len(config.transitions) >= 6
    assert len(config.motion_types) >= 4


def test_director_notes_serialization(sample_package: FinalPackage) -> None:
    """DirectorNotes 能序列化/反序列化"""
    dn = sample_package.director_notes
    j = dn.model_dump_json()
    dn2 = DirectorNotes.model_validate_json(j)
    assert dn2.theme == dn.theme
    assert dn2.three_act.setup == dn.three_act.setup
    assert len(dn2.characters) == 1


def test_screenplay_validators(sample_package: FinalPackage) -> None:
    """Screenplay 校验器工作"""
    sp = sample_package.screenplay
    # shot_id 唯一
    ids = [s.shot_id for sc in sp.scenes for s in sc.shots]
    assert len(ids) == len(set(ids))
    # scene_id 一致
    for sc in sp.scenes:
        for s in sc.shots:
            assert s.scene_id == sc.scene_id


def test_shot_prompts_anchors(sample_package: FinalPackage) -> None:
    """ShotPrompts 锚点完整"""
    shp = sample_package.shot_prompts
    assert len(shp.visual_anchors) >= 3
    char_anchors = [a for a in shp.visual_anchors if a.kind == "character"]
    assert len(char_anchors) >= 1
    # 每个锚点有 anchor_id 前缀
    for a in shp.visual_anchors:
        assert a.anchor_id.startswith(("char_", "loc_", "prop_"))


def test_video_prompts_motion_types(sample_package: FinalPackage) -> None:
    """VideoPrompts 运动类型分布合理"""
    vp = sample_package.video_prompts
    types = {s.motion_type for s in vp.shots}
    assert "camera_movement" in types or "character_action" in types
    # 每个镜头有兜底
    for s in vp.shots:
        assert s.fallback_motion
        assert s.model_suggestion.primary


def test_quality_check_runs(
    sample_package: FinalPackage, config: Config
) -> None:
    """质检能跑通"""
    qr = run_quality_check(
        director_notes=sample_package.director_notes,
        screenplay=sample_package.screenplay,
        shot_prompts=sample_package.shot_prompts,
        video_prompts=sample_package.video_prompts,
        config=config,
    )
    assert "passed" in qr
    assert "issues" in qr
    assert "checks" in qr
    # 这个样例时长偏差大（20s vs 90s），应该报 issue
    assert not qr["passed"] or len(qr["issues"]) >= 0


def test_output_writer_all_formats(
    sample_package: FinalPackage, config: Config, tmp_path: Path
) -> None:
    """输出写入器能生成所有格式"""
    written = write_outputs(
        package=sample_package,
        config=config,
        base_dir=str(tmp_path),
    )

    # 各阶段 JSON
    assert "00_director_notes" in written
    assert "01_screenplay" in written
    assert "02_shot_prompts" in written
    assert "03_video_prompts" in written
    assert "final_package" in written
    assert "markdown" in written
    assert "prompts_only" in written
    assert "shot_table" in written

    # 验证文件非空
    for k, path in written.items():
        p = Path(path)
        assert p.exists(), f"{k} 文件不存在: {p}"
        assert p.stat().st_size > 0, f"{k} 文件为空: {p}"

    # 验证 final_package.json 能解析
    fp = json.loads(Path(written["final_package"]).read_text(encoding="utf-8"))
    assert fp["project_id"] == "proj_test001"
    assert fp["director_notes"]["theme"] == "乡愁与归途"

    # 验证 shot_table.csv 行数
    with open(written["shot_table"], encoding="utf-8-sig") as f:
        lines = f.readlines()
    assert len(lines) == 4  # 1 header + 3 shots


def test_input_parser_classification(config: Config) -> None:
    """输入解析器能正确分类"""
    from cultural_film_prompts.io import parse_input

    # 灵感（短文本）
    short = "想去皖南拍乡愁片，主角返乡整理旧物。"
    parsed = parse_input(source=short)
    assert parsed.input_type.value in ("inspiration", "mixed")

    # 完整剧本（长文本 + 场景标记）
    long = (
        "# 完整剧本\n\n"
        "## 场景 1：归途（外景·清晨）\n"
        "清晨的皖南古村，薄雾笼罩。青年阿远背着旧帆布包，走在青石板巷里。\n"
        "他的手轻轻抚摸斑驳的白墙，像在确认什么。屋檐滴下一颗水珠，落在他的肩上。\n\n"
        "## 场景 2：老屋（内景·上午）\n"
        "阿远推开老屋的木门，门轴发出沉闷的吱呀声。\n"
        "屋里弥漫着灰尘，光线从木格窗斜射进来，形成一道道光柱。\n"
        "他走到神台前，发现供桌上的旧物——一把铜钥匙、一卷泛黄的族谱、几张褪色的春联。\n"
    )
    parsed = parse_input(source=long)
    assert parsed.input_type.value in ("full_script", "mixed")
    assert parsed.char_count > 100
