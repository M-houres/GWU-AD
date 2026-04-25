from app.services.strategy_asset_validation import (
    DISCIPLINE_KEYS,
    SLOT_KEYS,
    SUPPLEMENTAL_DEDUP_REFERENCE_PATH,
    SUPPLEMENTAL_POSITIVE_PAIR_PATH,
    validate_dedup_positive_references,
    validate_positive_few_shot_pairs,
    validate_supplemental_dedup_positive_references,
    validate_supplemental_positive_few_shot_pairs,
    validate_strategy_asset_files,
    validate_synthetic_negative_samples,
)


def test_strategy_asset_jsonl_files_are_parseable() -> None:
    summaries = validate_strategy_asset_files()
    assert [item.name for item in summaries] == [
        "dedup_positive_references_v1.jsonl",
        "platform_signal_reports_v1.jsonl",
        "positive_few_shot_pairs_v1.jsonl",
        "strict_benchmark_samples_v1.jsonl",
        "supplemental_dedup_positive_references_v1.jsonl",
        "supplemental_positive_few_shot_pairs_v1.jsonl",
        "synthetic_negative_samples_v1.jsonl",
        "weak_supervised_pairs_v1.jsonl",
    ]
    assert all(item.count > 0 for item in summaries)


def test_synthetic_negative_samples_cover_all_slots_and_non_education_disciplines() -> None:
    summary = validate_synthetic_negative_samples()

    assert summary.total >= 18
    assert set(summary.slots) == SLOT_KEYS
    assert all(count >= 2 for count in summary.slots.values())

    assert summary.disciplines.get("medicine_public_health", 0) >= 2
    assert summary.disciplines.get("law_policy", 0) >= 2
    assert summary.disciplines.get("finance_management", 0) >= 2
    assert summary.disciplines.get("engineering_it_patent", 0) >= 2
    assert summary.disciplines.get("humanities_social_science", 0) >= 2
    assert set(summary.disciplines) <= DISCIPLINE_KEYS | {"unspecified"}


def test_positive_few_shot_pairs_cover_rewrite_slots() -> None:
    summary = validate_positive_few_shot_pairs()

    assert summary.total >= 8
    assert summary.slots["cnki.rewrite.llm"] >= 1
    assert summary.slots["vip.rewrite.llm"] >= 1
    assert summary.slots["cnki.dedup.llm"] == 0
    assert summary.slots["vip.dedup.llm"] == 0
    assert set(summary.disciplines) <= DISCIPLINE_KEYS


def test_supplemental_positive_few_shot_pairs_cover_non_education_rewrite_disciplines() -> None:
    summary = validate_supplemental_positive_few_shot_pairs(SUPPLEMENTAL_POSITIVE_PAIR_PATH)

    assert summary.total >= 8
    assert summary.slots["cnki.rewrite.llm"] >= 1
    assert summary.slots["vip.rewrite.llm"] >= 1
    assert summary.disciplines.get("finance_management", 0) >= 1
    assert summary.disciplines.get("law_policy", 0) >= 1
    assert summary.disciplines.get("medicine_public_health", 0) >= 1
    assert set(summary.disciplines) <= DISCIPLINE_KEYS


def test_dedup_positive_references_cover_dedup_slots_and_multi_discipline() -> None:
    summary = validate_dedup_positive_references()

    assert summary.total >= 12
    assert summary.slots["cnki.dedup.llm"] >= 1
    assert summary.slots["vip.dedup.llm"] >= 1
    assert summary.slots["cnki.rewrite.llm"] == 0
    assert summary.slots["vip.rewrite.llm"] == 0
    assert summary.disciplines.get("medicine_public_health", 0) >= 1
    assert summary.disciplines.get("finance_management", 0) >= 1
    assert summary.disciplines.get("engineering_it_patent", 0) >= 1
    assert summary.disciplines.get("humanities_social_science", 0) >= 1
    assert summary.disciplines.get("law_policy", 0) >= 1
    assert set(summary.disciplines) <= DISCIPLINE_KEYS


def test_supplemental_dedup_positive_references_cover_cnki_non_education_slots() -> None:
    summary = validate_supplemental_dedup_positive_references(SUPPLEMENTAL_DEDUP_REFERENCE_PATH)

    assert summary.total >= 4
    assert summary.slots["cnki.dedup.llm"] >= 1
    assert summary.disciplines.get("finance_management", 0) >= 1
    assert summary.disciplines.get("law_policy", 0) >= 1
    assert summary.disciplines.get("medicine_public_health", 0) >= 1
    assert summary.disciplines.get("engineering_it_patent", 0) >= 1
