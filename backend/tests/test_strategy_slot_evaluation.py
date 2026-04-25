from app.services.strategy_slot_evaluation import evaluate_strategy_slots, render_strategy_slot_evaluation_report


def test_evaluate_strategy_slots_covers_all_four_slots() -> None:
    payload = evaluate_strategy_slots()
    slots = {row["slot"] for row in payload["slots"]}

    assert payload["summary"]["slot_count"] == 4
    assert slots == {
        "cnki.rewrite.llm",
        "cnki.dedup.llm",
        "vip.rewrite.llm",
        "vip.dedup.llm",
    }


def test_rewrite_llm_slot_evaluation_sees_non_education_examples() -> None:
    payload = evaluate_strategy_slots()
    row = next(item for item in payload["slots"] if item["slot"] == "cnki.rewrite.llm")

    assert row["slot_type"] == "llm_prompt_readiness"
    assert "finance_management" in str(row["details"]["disciplines"]) or "law_policy" in str(row["details"]["disciplines"])
    assert row["qualified_count"] >= 3


def test_render_strategy_slot_evaluation_report_includes_slot_names() -> None:
    payload = evaluate_strategy_slots()
    content = render_strategy_slot_evaluation_report(payload)

    assert "四槽位策略评估" in content
    assert "cnki.rewrite.llm" in content
    assert "vip.dedup.llm" in content
