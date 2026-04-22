from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.strategy_asset_validation import (
    SUPPLEMENTAL_DEDUP_REFERENCE_PATH,
    SUPPLEMENTAL_POSITIVE_PAIR_PATH,
    validate_dedup_positive_references,
    validate_positive_few_shot_pairs,
    validate_supplemental_dedup_positive_references,
    validate_supplemental_positive_few_shot_pairs,
    validate_strategy_asset_files,
    validate_synthetic_negative_samples,
)
from app.services.strategy_slot_evaluation import evaluate_strategy_slots, write_strategy_slot_evaluation_report


def main() -> None:
    asset_summaries = validate_strategy_asset_files()
    synthetic = validate_synthetic_negative_samples()
    positive = validate_positive_few_shot_pairs()
    supplemental_positive = validate_supplemental_positive_few_shot_pairs(SUPPLEMENTAL_POSITIVE_PAIR_PATH)
    dedup_positive = validate_dedup_positive_references()
    supplemental_dedup_positive = validate_supplemental_dedup_positive_references(SUPPLEMENTAL_DEDUP_REFERENCE_PATH)
    slot_evaluation = evaluate_strategy_slots()
    report_path = write_strategy_slot_evaluation_report(slot_evaluation)

    print("FILES")
    for item in asset_summaries:
        print(f"{item.name}\t{item.count}")

    print("SYNTHETIC_SLOTS")
    for slot, count in synthetic.slots.items():
        print(f"{slot}\t{count}")

    print("SYNTHETIC_DISCIPLINES")
    for discipline, count in synthetic.disciplines.items():
        print(f"{discipline}\t{count}")

    print("POSITIVE_PAIR_SLOTS")
    for slot, count in positive.slots.items():
        print(f"{slot}\t{count}")

    print("POSITIVE_PAIR_DISCIPLINES")
    for discipline, count in positive.disciplines.items():
        print(f"{discipline}\t{count}")

    print("SUPPLEMENTAL_POSITIVE_PAIR_SLOTS")
    for slot, count in supplemental_positive.slots.items():
        print(f"{slot}\t{count}")

    print("SUPPLEMENTAL_POSITIVE_PAIR_DISCIPLINES")
    for discipline, count in supplemental_positive.disciplines.items():
        print(f"{discipline}\t{count}")

    print("DEDUP_REFERENCE_SLOTS")
    for slot, count in dedup_positive.slots.items():
        print(f"{slot}\t{count}")

    print("DEDUP_REFERENCE_DISCIPLINES")
    for discipline, count in dedup_positive.disciplines.items():
        print(f"{discipline}\t{count}")

    print("SUPPLEMENTAL_DEDUP_REFERENCE_SLOTS")
    for slot, count in supplemental_dedup_positive.slots.items():
        print(f"{slot}\t{count}")

    print("SUPPLEMENTAL_DEDUP_REFERENCE_DISCIPLINES")
    for discipline, count in supplemental_dedup_positive.disciplines.items():
        print(f"{discipline}\t{count}")

    print("SLOT_EVALUATION")
    for row in slot_evaluation["slots"]:
        print(
            f"{row['slot']}\t{row['status']}\t{row['qualified_count']}/{row['sample_count']}\t{row['qualified_rate']:.2f}"
        )

    print("SLOT_EVALUATION_REPORT")
    print(report_path)


if __name__ == "__main__":
    main()
