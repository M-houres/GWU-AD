from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.aigc_detect_evaluator import AigcDetectEvaluator


def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _index_by_sample_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed = {}
    for item in items:
        sample_id = str(item.get("sample_id") or "").strip()
        if sample_id:
            indexed[sample_id] = item
    return indexed


def _build_cases(reference_data: Any, candidate_data: Any, runs_data: Any | None = None) -> list[dict[str, Any]]:
    if isinstance(reference_data, dict) and isinstance(candidate_data, dict):
        return [
            {
                "reference": reference_data,
                "candidate": candidate_data,
                "candidate_runs": runs_data if isinstance(runs_data, list) else [],
            }
        ]

    if not isinstance(reference_data, list) or not isinstance(candidate_data, list):
        raise ValueError("Reference and candidate JSON must both be dicts or both be lists.")

    candidate_by_id = _index_by_sample_id([item for item in candidate_data if isinstance(item, dict)])
    run_index = runs_data if isinstance(runs_data, dict) else {}

    if candidate_by_id:
        cases = []
        for reference_item in reference_data:
            if not isinstance(reference_item, dict):
                continue
            sample_id = str(reference_item.get("sample_id") or "").strip()
            candidate_item = candidate_by_id.get(sample_id)
            if candidate_item is None:
                raise ValueError(f"Missing candidate result for sample_id={sample_id!r}")
            cases.append(
                {
                    "reference": reference_item,
                    "candidate": candidate_item,
                    "candidate_runs": run_index.get(sample_id, []) if isinstance(run_index, dict) else [],
                }
            )
        return cases

    if len(reference_data) != len(candidate_data):
        raise ValueError("Reference and candidate lists must have the same length when sample_id is unavailable.")

    cases = []
    for index, (reference_item, candidate_item) in enumerate(zip(reference_data, candidate_data, strict=True)):
        cases.append(
            {
                "reference": reference_item,
                "candidate": candidate_item,
                "candidate_runs": runs_data[index] if isinstance(runs_data, list) and index < len(runs_data) else [],
            }
        )
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate AIGC detection result consistency against benchmark data.")
    parser.add_argument("--reference", required=True, help="Path to normalized reference JSON.")
    parser.add_argument("--candidate", required=True, help="Path to candidate result JSON.")
    parser.add_argument(
        "--runs",
        help="Optional repeated-run JSON. For batch mode use a sample_id->list mapping.",
    )
    parser.add_argument("--indent", type=int, default=2, help="JSON output indent.")
    args = parser.parse_args()

    reference_data = _load_json(args.reference)
    candidate_data = _load_json(args.candidate)
    runs_data = _load_json(args.runs) if args.runs else None

    evaluator = AigcDetectEvaluator()
    cases = _build_cases(reference_data, candidate_data, runs_data)
    result = evaluator.evaluate_batch(cases) if len(cases) > 1 else evaluator.evaluate(**cases[0])
    print(json.dumps(result, ensure_ascii=False, indent=args.indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
