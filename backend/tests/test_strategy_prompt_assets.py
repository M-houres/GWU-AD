from app.services.strategy_prompt_assets import (
    build_slot_positive_examples,
    build_slot_prompt_examples,
    slot_negative_examples,
    slot_positive_examples,
)


def test_slot_negative_examples_are_filtered_by_slot() -> None:
    rows = slot_negative_examples("cnki.rewrite.llm")

    assert rows
    assert all(row["target_slot"] == "cnki.rewrite.llm" for row in rows)
    assert all(row["target_layer"] in {"few_shot_negative", "negative_assets"} for row in rows)


def test_build_slot_prompt_examples_renders_discipline_and_bad_case() -> None:
    content = build_slot_prompt_examples("vip.dedup.llm")

    assert "禁止模仿以下坏写法示例" in content
    assert "财经/管理" in content or "未标注" in content
    assert "路径方式" in content or "协同收益释放" in content


def test_slot_positive_examples_are_filtered_by_slot() -> None:
    rows = slot_positive_examples("cnki.rewrite.llm")

    assert rows
    assert all("cnki.rewrite.llm" in row["target_slots"] for row in rows)
    assert all(row.get("source_excerpt") for row in rows)
    assert all(row.get("rewritten_excerpt") for row in rows)
    assert any(str(row.get("discipline") or "") != "education" for row in rows)


def test_dedup_slot_positive_examples_prefer_excerpt_references() -> None:
    rows = slot_positive_examples("vip.dedup.llm")

    assert rows
    assert all("vip.dedup.llm" in row["target_slots"] for row in rows)
    assert all(row.get("excerpt") for row in rows)


def test_cnki_dedup_slot_positive_examples_include_non_education_disciplines() -> None:
    rows = slot_positive_examples("cnki.dedup.llm")

    assert rows
    assert all("cnki.dedup.llm" in row["target_slots"] for row in rows)
    assert any(str(row.get("discipline") or "") != "education" for row in rows)


def test_build_slot_positive_examples_renders_positive_style_examples() -> None:
    rewrite_content = build_slot_positive_examples("cnki.rewrite.llm")
    dedup_content = build_slot_positive_examples("vip.dedup.llm")

    assert "优先参考以下正向改写风格示例" in rewrite_content
    assert "->" in rewrite_content or "知网/降AIGC" in rewrite_content
    assert "财经/管理" in rewrite_content or "法学/政策" in rewrite_content
    assert "优先参考以下正向改写风格示例" in dedup_content
    assert "->" not in dedup_content
    assert "vip_dedup_report" in dedup_content
