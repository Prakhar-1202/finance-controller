"""
pipeline.py
-----------
The single reusable orchestration of Tier 1 (exact) + Tier 2 (fuzzy/batch)
matching. Returns a structured `ReconciliationResult` rather than printing
anything, so it has exactly one implementation shared by:

    - run_reconciliation.py  (CLI report, for local dev/demo)
    - evaluate.py            (precision/recall against ground_truth.csv)
    - backend/main.py        (FastAPI /reconcile endpoint, added later)

Before this file existed, the orchestration logic lived inline inside the
CLI script, which meant the evaluator would have had to duplicate it (and
drift out of sync). This is the fix for that.
"""

from dataclasses import dataclass

import pandas as pd

from backend.data_loader import load_data
from backend.matcher.exact import (
    match_ledger_settlement,
    match_settlement_bank,
    LedgerSettlementResult,
    SettlementBankResult,
)
from backend.matcher.fuzzy_batch import (
    detect_duplicate_bank_rows,
    classify_amount_drift,
    subset_sum_match,
    SubsetSumMatch,
)


@dataclass
class ReconciliationResult:
    bank: pd.DataFrame
    settlement: pd.DataFrame
    ledger: pd.DataFrame

    ls_result: LedgerSettlementResult
    sb_result: SettlementBankResult

    duplicates: pd.DataFrame
    drift_classified: pd.DataFrame
    subset_matches: list  # list[SubsetSumMatch]

    def reconciled_order_ids(self) -> set:
        """Orders that are fully reconciled end-to-end: present in both
        ledger and settlement (Tier 1a), AND their settlement batch cleanly
        matched a bank row with no ambiguity (Tier 1b). This is the
        strictest possible definition of "reconciled" -- an order sharing
        a batch with a fee-drift or duplicate-ref issue does NOT count,
        even though the order-level join succeeded, because the money
        movement for its batch hasn't actually been confirmed clean.
        """
        matched_order_ids = set(self.ls_result.matched["order_id"])
        clean_bank_refs = set(self.sb_result.matched_batches["bank_ref"])
        # utr column on the matched (ledger join settlement) frame identifies the batch
        reconciled = self.ls_result.matched[
            self.ls_result.matched["utr"].isin(clean_bank_refs)
        ]["order_id"]
        return matched_order_ids.intersection(set(reconciled))


def run_pipeline(data_dir: str = "data") -> ReconciliationResult:
    bank, settlement, ledger = load_data(data_dir)

    # --- Tier 1 ---
    ls_result = match_ledger_settlement(ledger, settlement)
    sb_result = match_settlement_bank(settlement, bank)

    # --- Tier 2 ---
    duplicates = detect_duplicate_bank_rows(bank)
    drift_classified = classify_amount_drift(sb_result.unmatched_batches)

    duplicate_bank_row_ids = set(duplicates["bank_row_id"])
    genuinely_unmatched_bank = sb_result.unmatched_bank_rows[
        ~sb_result.unmatched_bank_rows["bank_row_id"].isin(duplicate_bank_row_ids)
    ]

    subset_matches = subset_sum_match(
        settlement[settlement["order_id"].isin(ls_result.orphan_settlement["order_id"])],
        genuinely_unmatched_bank,
    )

    return ReconciliationResult(
        bank=bank,
        settlement=settlement,
        ledger=ledger,
        ls_result=ls_result,
        sb_result=sb_result,
        duplicates=duplicates,
        drift_classified=drift_classified,
        subset_matches=subset_matches,
    )
