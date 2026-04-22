from app.services.strategy_style_profiles import (
    build_dedup_style_guidance,
    build_rewrite_style_guidance,
    dedup_style_profile,
    rewrite_style_profile,
)


def test_rewrite_style_profile_loads_for_supported_platform() -> None:
    profile = rewrite_style_profile("vip")

    assert profile is not None
    assert profile.platform == "vip"
    assert profile.sample_count >= 1
    assert profile.avg_sentence_length > 0


def test_rewrite_style_profile_includes_supplemental_positive_pairs() -> None:
    profile = rewrite_style_profile("cnki")

    assert profile is not None
    assert profile.platform == "cnki"
    assert profile.sample_count >= 8


def test_rewrite_style_profile_returns_none_for_unknown_platform() -> None:
    assert rewrite_style_profile("paperpass") is None


def test_build_rewrite_style_guidance_uses_profile_when_available() -> None:
    guidance = build_rewrite_style_guidance("vip")

    assert "高质量样本风格基线" in guidance
    assert "平均句长约" in guidance


def test_dedup_style_profile_loads_for_supported_platform() -> None:
    profile = dedup_style_profile("vip")

    assert profile is not None
    assert profile.platform == "vip"
    assert profile.sample_count >= 1
    assert profile.avg_sentence_length > 0


def test_build_dedup_style_guidance_uses_profile_when_available() -> None:
    guidance = build_dedup_style_guidance("cnki")

    assert "高质量降重样本风格基线" in guidance
    assert "平均句长约" in guidance
