"""
run_reconciliation.py
----------------------
CLI entry point for local development / demoing. All orchestration logic
lives in pipeline.py so it's shared with evaluate.py rather than
duplicated -- this file only prints.

Usage:
    python -m backend.run_reconciliation --data-dir data
"""

import argparse

from backend.pipeline import run_pipeline


def print_report(result):
    ls_result, sb_result = result.ls_result, result.sb_result
    duplicates, drift_classified = result.duplicates, result.drift_classified

    total_orders = len(
        result.ledger.merge(result.settlement, on="order_id", how="outer").drop_duplicates(
            subset=["order_id"]
        )
    )
    tier1_ledger_settlement_matched = len(ls_result.matched.drop_duplicates(subset=["order_id"]))
    tier1_batches_matched = len(sb_result.matched_batches)
    tier1_batches_total = tier1_batches_matched + len(sb_result.unmatched_batches) + len(
        sb_result.unmatched_bank_rows
    )

    print("=" * 60)
    print("RECONCILIATION REPORT")
    print("=" * 60)
    print(f"\nTotal distinct orders considered: {total_orders}")
    print(f"\n--- Tier 1: Ledger <-> Settlement (order_id) ---")
    print(f"  Matched:            {tier1_ledger_settlement_matched}")
    print(f"  Orphan ledger:      {len(ls_result.orphan_ledger)}  (invoiced, never paid)")
    print(f"  Orphan settlement:  {len(ls_result.orphan_settlement)}  (paid, never invoiced)")

    print(f"\n--- Tier 1: Settlement batch <-> Bank (utr / bank_ref) ---")
    print(f"  Clean batch matches:  {tier1_batches_matched} / {tier1_batches_total}")
    print(f"  Sent to Tier 2:       {len(sb_result.unmatched_batches)} batches, "
          f"{len(sb_result.unmatched_bank_rows)} unmatched bank rows")

    print(f"\n--- Tier 2: Duplicate bank rows ---")
    print(f"  Flagged duplicates:   {len(duplicates)}")

    print(f"\n--- Tier 2: Amount drift classification ---")
    if not drift_classified.empty:
        print(drift_classified["category"].value_counts().to_string())
    else:
        print("  (none)")

    print(f"\n--- Tier 2: Subset-sum fallback matches ---")
    print(f"  Resolved via subset-sum: {len(result.subset_matches)}")

    print(f"\n--- Headline numbers ---")
    auto_match_rate = tier1_batches_matched / tier1_batches_total if tier1_batches_total else 0
    print(f"  Tier 1 batch auto-match rate: {auto_match_rate:.1%}")
    print(f"  Fully reconciled orders (end-to-end, no ambiguity): "
          f"{len(result.reconciled_order_ids())} / {total_orders}")

    print("\nFor precision/recall against ground_truth.csv, run:")
    print("  python -m backend.evaluate --data-dir data")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=str, default="data")
    args = parser.parse_args()
    print_report(run_pipeline(args.data_dir))
