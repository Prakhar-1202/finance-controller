"""
evaluate.py
-----------
Validates the matching engine against ground truth instead of relying on
unit tests alone. Two separate evaluations, because they test different
layers of the pipeline:

1. Order-level: does `ReconciliationResult.reconciled_order_ids()` agree
   with ground_truth.csv's `expected_match` label? Reported as an overall
   confusion matrix (TP/FP/TN/FN, precision/recall/F1) AND broken down per
   `case_type`, because an aggregate number hides exactly the kind of
   systematic disagreement this dataset is designed to surface (see the
   methodology note below about delayed_settlement).

2. Bank-row-level: does Tier 2's duplicate detector and fee-drift
   classifier agree with the `batch_notes` column that generate_data.py
   wrote at creation time (independent of ground_truth.csv, which only
   covers order-level cases)?

IMPORTANT METHODOLOGY NOTE -- read this before trusting the numbers:
`ground_truth.csv` labels `delayed_settlement` orders as `expected_match =
False`. That label was written under the assumption that a matcher relies
on a *narrow date window* to link records, so a large date gap should
break the match. This pipeline's Tier 1 does NOT use a date window for
order_id / utr joins -- it uses exact keys, which are date-independent by
design. The practical result: this pipeline correctly reconciles delayed
settlements (the order really was paid, just later), while ground truth
scores that as wrong. This shows up below as a cluster of "false
positives" concentrated entirely in the delayed_settlement case type. That
is a labeling-assumption mismatch, not a matching defect -- but it's
reported rather than hidden, and the per-case-type breakdown exists
specifically so you can see it and make your own call on which behavior
you actually want.

Usage:
    python -m backend.evaluate --data-dir data
"""

import argparse

import pandas as pd

from backend.pipeline import run_pipeline


def evaluate_order_level(result, ground_truth: pd.DataFrame):
    reconciled_ids = result.reconciled_order_ids()

    gt = ground_truth.copy()
    gt["predicted_match"] = gt["order_id"].isin(reconciled_ids)
    gt["expected_match"] = gt["expected_match"].astype(bool)

    tp = ((gt["predicted_match"]) & (gt["expected_match"])).sum()
    fp = ((gt["predicted_match"]) & (~gt["expected_match"])).sum()
    tn = ((~gt["predicted_match"]) & (~gt["expected_match"])).sum()
    fn = ((~gt["predicted_match"]) & (gt["expected_match"])).sum()

    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) and precision == precision and recall == recall else float("nan"))

    print("=" * 60)
    print("ORDER-LEVEL EVALUATION (vs ground_truth.csv)")
    print("=" * 60)
    print(f"\nConfusion matrix:")
    print(f"  True Positive  (correctly reconciled):     {tp}")
    print(f"  False Positive (reconciled but shouldn't):  {fp}")
    print(f"  True Negative  (correctly NOT reconciled):  {tn}")
    print(f"  False Negative (should reconcile, missed):  {fn}")
    print(f"\nPrecision: {precision:.1%}   Recall: {recall:.1%}   F1: {f1:.1%}")

    print(f"\n--- Breakdown by case_type ---")
    breakdown = gt.groupby("case_type").apply(
        lambda g: pd.Series({
            "n": len(g),
            "correct": (g["predicted_match"] == g["expected_match"]).sum(),
            "incorrect": (g["predicted_match"] != g["expected_match"]).sum(),
        }),
        include_groups=False,
    )
    print(breakdown.to_string())

    delayed_incorrect = breakdown.loc["delayed_settlement", "incorrect"] if "delayed_settlement" in breakdown.index else 0
    if delayed_incorrect > 0:
        print(f"\n  Note: {delayed_incorrect} delayed_settlement disagreement(s) above are the")
        print(f"  expected result of the key-based-vs-date-window methodology gap explained")
        print(f"  in this file's module docstring -- not a matching defect.")

    return gt


def evaluate_bank_level(result):
    """Fee-drift is evaluated at the row level (each unmatched batch maps
    to exactly one bank row, so row identity is meaningful there).

    Duplicate detection is evaluated at the (bank_ref, amount) GROUP level,
    not raw bank_row_id -- because within a duplicate pair, nothing
    distinguishes "the real one" from "the copy," so both the generator
    and the detector make an arbitrary, independent choice of which row to
    label. Comparing literal row ids would penalize that arbitrary
    disagreement even when the group was correctly caught, which measures
    the wrong thing. What actually matters operationally is: did we catch
    that this (bank_ref, amount) pair was posted twice.
    """
    bank = result.bank

    gt_dup_rows = bank[bank["batch_notes"].str.startswith("duplicate_bank_row")]
    gt_duplicate_groups = set(zip(gt_dup_rows["bank_ref"], gt_dup_rows["amount"]))

    pred_dup = result.duplicates.merge(
        bank[["bank_row_id", "bank_ref", "amount"]], on=["bank_row_id", "bank_ref", "amount"], how="left"
    ) if not result.duplicates.empty else result.duplicates
    predicted_duplicate_groups = set(zip(result.duplicates["bank_ref"], result.duplicates["amount"]))

    gt_drift_ids = set(bank[bank["batch_notes"].str.startswith("fee_drift")]["bank_row_id"])
    predicted_drift_ids = set(
        result.drift_classified[result.drift_classified["category"] == "fee_drift"]["bank_row_id"]
    )

    def prf(predicted: set, actual: set, label: str, unit: str):
        tp = len(predicted & actual)
        fp = len(predicted - actual)
        fn = len(actual - predicted)
        precision = tp / (tp + fp) if (tp + fp) else float("nan")
        recall = tp / (tp + fn) if (tp + fn) else float("nan")
        print(f"\n{label} (measured per {unit}):")
        print(f"  ground truth count: {len(actual)}   predicted count: {len(predicted)}")
        print(f"  TP={tp}  FP={fp}  FN={fn}   Precision={precision:.1%}  Recall={recall:.1%}")

    print("\n" + "=" * 60)
    print("BANK-ROW-LEVEL EVALUATION (vs bank_statement.csv batch_notes)")
    print("=" * 60)
    prf(predicted_duplicate_groups, gt_duplicate_groups, "Duplicate bank row detection", "duplicate group")
    prf(predicted_drift_ids, gt_drift_ids, "Fee-drift classification", "bank row")


def run(data_dir: str = "data"):
    result = run_pipeline(data_dir)
    ground_truth = pd.read_csv(f"{data_dir}/ground_truth.csv")

    evaluate_order_level(result, ground_truth)
    evaluate_bank_level(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=str, default="data")
    args = parser.parse_args()
    run(args.data_dir)
