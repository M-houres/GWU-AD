from app.services.aigc_detect_strategies.cnki import detect
from app.services.aigc_detect_strategies.common import split_paragraphs


SAMPLE_TEXT = "\n".join(
    [
        "人工智能背景下高校课程评价改革研究",
        "摘要",
        "本研究围绕高校课程评价改革展开分析，研究表明该路径具备较强复制性，因此可以看出其表达具有模板化倾向，同时在多个场景中重复使用统一结论。",
        "关键词",
        "人工智能；课程评价；改革",
        "引言",
        "在此背景下，本文基于已有研究展开系统讨论，并从多个层面提出实施路径。",
        "一、课程评价改革的现实基础",
        "研究表明，当前评价方式在不同教学场景中具有较强一致性，因此可以快速迁移到其他课程。",
        "二、课程评价改革的实施路径",
        "首先，需要构建统一指标。其次，需要形成闭环反馈。最后，需要持续优化保障机制。",
        "结论",
        "综上所述，本文提出的路径具有可复制性与推广价值。",
    ]
)


def test_split_paragraphs_keeps_front_matter_and_outline_lines_separate() -> None:
    paragraphs = split_paragraphs(SAMPLE_TEXT)

    assert paragraphs == [
        "人工智能背景下高校课程评价改革研究",
        "摘要",
        "本研究围绕高校课程评价改革展开分析，研究表明该路径具备较强复制性，因此可以看出其表达具有模板化倾向，同时在多个场景中重复使用统一结论。",
        "关键词",
        "人工智能；课程评价；改革",
        "引言",
        "在此背景下，本文基于已有研究展开系统讨论，并从多个层面提出实施路径。",
        "一、课程评价改革的现实基础",
        "研究表明，当前评价方式在不同教学场景中具有较强一致性，因此可以快速迁移到其他课程。",
        "二、课程评价改革的实施路径",
        "首先，需要构建统一指标。其次，需要形成闭环反馈。最后，需要持续优化保障机制。",
        "结论",
        "综上所述，本文提出的路径具有可复制性与推广价值。",
    ]


def test_cnki_detect_does_not_merge_title_and_abstract_into_risk_segment() -> None:
    result = detect(SAMPLE_TEXT)

    assert len(result["paragraphs"]) == 13
    assert set(result["distribution_20pct"]) == {"front", "middle", "back"}
    assert result["section_details"][0]["section_name"] == "中英文摘要等"
    joined_segments = " ".join(
        str(segment.get("text") or "")
        for row in result["paragraphs"]
        for segment in (row.get("suspicious_segments") or [])
    )
    assert "研究摘要本研究" not in joined_segments
    assert "关键词人工智能" not in joined_segments


def test_cnki_detect_prioritizes_abstract_block_and_skips_metadata_references() -> None:
    text = "\n".join(
        [
            "餐饮企业客户体验优化研究",
            "摘要",
            "在数字化转型背景下，本文围绕客户体验优化展开系统分析，研究表明当前服务流程、场景设计与会员运营之间存在明显断裂，需要从产品、服务与数字触点协同重构体验路径。",
            "2 理论基础",
            "体验经济理论为研究提供了分析框架。Pine 和 Gilmore（1999）在《体验经济》中提出，体验是继商品、服务之后的第四种经济提供物[1]。",
            "作者：张三 单位：某大学",
            "参考文献",
            "[1] Pine B J, Gilmore J H. The Experience Economy[M]. Boston: Harvard Business School Press, 1999.",
        ]
    )

    result = detect(text)
    abstract_row = result["paragraphs"][2]
    theory_row = result["paragraphs"][4]
    meta_row = result["paragraphs"][5]
    reference_row = result["paragraphs"][7]

    assert abstract_row["role"] == "front_abstract"
    assert abstract_row["label"] == "high"
    assert theory_row["label"] in {"clean", "low"}
    assert meta_row["label"] == "clean"
    assert reference_row["label"] == "clean"
    assert result["sentence_spans"]
    assert result["section_details"][0]["score_pct"] >= 50.0
