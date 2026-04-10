from app.services.aigc_detect_evaluator import AigcDetectEvaluator


def _reference_payload() -> dict:
    return {
        "sample_id": "cnki_doc_001",
        "platform": "cnki",
        "source_text": "\n".join(
            [
                "Paragraph one keeps a mild amount of template phrasing for detection alignment.",
                "Paragraph two repeats structured statements and carries the main suspicious content.",
                "Paragraph three is a normal discussion paragraph with low risk.",
            ]
        ),
        "reference": {
            "total_score_pct": 28.0,
            "band_text_ratio": {
                "high": 10.0,
                "medium": 12.0,
                "low": 6.0,
                "clean": 72.0,
            },
            "paragraphs": [
                {
                    "index": 1,
                    "score_pct": 8.0,
                    "label": "low",
                    "text": "Paragraph one keeps a mild amount of template phrasing for detection alignment.",
                    "spans": [{"text": "template phrasing", "label": "low", "score_pct": 8.0}],
                },
                {
                    "index": 2,
                    "score_pct": 66.0,
                    "label": "high",
                    "text": "Paragraph two repeats structured statements and carries the main suspicious content.",
                    "spans": [{"text": "repeats structured statements", "label": "high", "score_pct": 66.0}],
                },
                {
                    "index": 3,
                    "score_pct": 0.0,
                    "label": "clean",
                    "text": "Paragraph three is a normal discussion paragraph with low risk.",
                    "spans": [],
                },
            ],
        },
    }


def _candidate_payload() -> dict:
    return {
        "sample_id": "cnki_doc_001",
        "platform": "cnki",
        "score_pct": 28.0,
        "fragment_distribution": {
            "high_suspected_text_ratio": 10.0,
            "middle_suspected_text_ratio": 12.0,
            "low_suspected_text_ratio": 6.0,
            "no_ai_suspected_text_ratio": 72.0,
        },
        "paragraph_details": [
            {
                "index": 1,
                "score": 8.0,
                "label": "low",
                "text": "Paragraph one keeps a mild amount of template phrasing for detection alignment.",
                "suspicious_segments": [{"text": "template phrasing", "label": "low", "score": 8.0}],
            },
            {
                "index": 2,
                "score": 66.0,
                "label": "high",
                "text": "Paragraph two repeats structured statements and carries the main suspicious content.",
                "suspicious_segments": [{"text": "repeats structured statements", "label": "high", "score": 66.0}],
            },
            {
                "index": 3,
                "score": 0.0,
                "label": "low",
                "text": "Paragraph three is a normal discussion paragraph with low risk.",
                "suspicious_segments": [],
            },
        ],
        "suspicious_segments": [
            {"paragraph_index": 1, "text": "template phrasing", "label": "low", "score": 8.0},
            {"paragraph_index": 2, "text": "repeats structured statements", "label": "high", "score": 66.0},
        ],
    }


def test_evaluator_scores_perfect_match() -> None:
    evaluator = AigcDetectEvaluator()

    report = evaluator.evaluate(_reference_payload(), _candidate_payload())

    assert report["final_score"] == 100.0
    assert report["grade"] == "S"
    assert report["promotion_ready"] is True
    assert report["passed_all_gates"] is True
    assert report["dimension_scores"]["highlight_span_alignment"]["span_overlap_f1"] == 1.0


def test_evaluator_flags_full_text_gate_failure() -> None:
    evaluator = AigcDetectEvaluator()
    candidate = _candidate_payload()
    candidate["score_pct"] = 42.0

    report = evaluator.evaluate(_reference_payload(), candidate)

    assert report["hard_gates"]["full_text"]["passed"] is False
    assert report["dimension_scores"]["full_text_score_consistency"]["diff_pct"] == 14.0
    assert report["final_score"] < 100.0


def test_evaluator_flags_paragraph_gate_failure() -> None:
    evaluator = AigcDetectEvaluator()
    candidate = _candidate_payload()
    candidate["paragraph_details"] = [
        {
            "index": 1,
            "score": 0.0,
            "label": "low",
            "text": "Paragraph one keeps a mild amount of template phrasing for detection alignment.",
            "suspicious_segments": [],
        },
        {
            "index": 2,
            "score": 0.0,
            "label": "low",
            "text": "Paragraph two repeats structured statements and carries the main suspicious content.",
            "suspicious_segments": [],
        },
        {
            "index": 3,
            "score": 48.0,
            "label": "medium",
            "text": "Paragraph three is a normal discussion paragraph with low risk.",
            "suspicious_segments": [{"text": "normal discussion", "label": "medium", "score": 48.0}],
        },
    ]

    report = evaluator.evaluate(_reference_payload(), candidate)

    assert report["hard_gates"]["paragraph"]["passed"] is False
    assert report["dimension_scores"]["paragraph_alignment"]["risk_paragraph_recall"] < 0.75
    assert report["dimension_scores"]["paragraph_alignment"]["paragraph_risk_f1"] < 0.75


def test_evaluator_flags_span_gate_failure() -> None:
    evaluator = AigcDetectEvaluator()
    candidate = _candidate_payload()
    candidate["suspicious_segments"] = [
        {"paragraph_index": 1, "text": "completely different snippet", "label": "low", "score": 8.0},
        {"paragraph_index": 2, "text": "unmatched segment body", "label": "medium", "score": 66.0},
    ]
    candidate["paragraph_details"][0]["suspicious_segments"] = [
        {"text": "completely different snippet", "label": "low", "score": 8.0}
    ]
    candidate["paragraph_details"][1]["suspicious_segments"] = [
        {"text": "unmatched segment body", "label": "medium", "score": 66.0}
    ]

    report = evaluator.evaluate(_reference_payload(), candidate)

    assert report["hard_gates"]["highlight_span"]["passed"] is False
    assert report["dimension_scores"]["highlight_span_alignment"]["span_overlap_f1"] < 0.65


def test_evaluator_batch_reports_stability_failures() -> None:
    evaluator = AigcDetectEvaluator()
    reference = _reference_payload()
    candidate = _candidate_payload()
    run_two = _candidate_payload()
    run_two["score_pct"] = 34.0
    run_two["paragraph_details"][1]["score"] = 72.0
    run_two["suspicious_segments"][1]["text"] = "changed suspicious segment"
    run_two["paragraph_details"][1]["suspicious_segments"][0]["text"] = "changed suspicious segment"

    report = evaluator.evaluate_batch(
        [
            {
                "reference": reference,
                "candidate": candidate,
                "candidate_runs": [candidate, run_two],
            }
        ]
    )

    assert report["sample_count"] == 1
    assert report["hard_gates"]["stability"]["passed"] is False
    assert report["samples"][0]["dimension_scores"]["stability_and_determinism"]["score_variance"] > 1.0
