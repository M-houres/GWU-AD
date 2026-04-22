from app.services.processing_text_tools import (
    reorder_comma_clauses,
    rewrite_academic_frames,
    rewrite_causal_chains,
    rewrite_parallel_targets,
    split_long_sentences,
)


def test_split_long_sentences_breaks_comma_heavy_sentence() -> None:
    text = "研究表明，这一教学方案在多个场景中保持了稳定执行路径，并且能够持续生成结构接近的段落表达，因此需要进一步拆分处理。"

    result = split_long_sentences(text, 24)

    assert "。" in result
    assert result != text


def test_split_long_sentences_keeps_short_sentence_unchanged() -> None:
    text = "这是一个较短的句子，不需要拆分。"

    assert split_long_sentences(text, 40) == text


def test_split_long_sentences_supports_softer_clause_joiner() -> None:
    text = "研究表明，这一方案覆盖多个教学场景，能够保持实施连续性，也能兼顾评价反馈，因此需要在复杂语境下进行验证。"

    result = split_long_sentences(text, 24, clause_joiner="；", min_clauses=3)

    assert "；" in result
    assert "。同时，" not in result


def test_rewrite_parallel_targets_changes_goal_structure() -> None:
    text = "将图书管理与阅读活动结合，能够提升校园阅读生态的整体质量，并形成更加稳定的实施机制。"

    result = rewrite_parallel_targets(text)

    assert result != text
    assert "不仅可以" in result or "既能" in result


def test_rewrite_causal_chains_changes_reasoning_frame() -> None:
    text = "研究表明，课程治理路径具有较强复制性，因此需要进一步优化实施环节。"

    result = rewrite_causal_chains(text)

    assert result != text
    assert "研究结果显示" in result or "从研究结果看" in result


def test_rewrite_academic_frames_changes_summary_frame() -> None:
    text = "本文立足数字化治理背景，系统探讨课程协同机制，梳理实施路径，以期提升课堂治理质量。"

    result = rewrite_academic_frames(text)

    assert result != text
    assert "立足数字化治理背景" in result or "以数字化治理背景为立足点" in result


def test_reorder_comma_clauses_swaps_front_clauses() -> None:
    text = "研究立足课堂观察，围绕课程治理路径展开分析，并提出优化建议。"

    result = reorder_comma_clauses(text, max_changes=1)

    assert result != text
    assert result.startswith("围绕课程治理路径展开分析，研究立足课堂观察")
