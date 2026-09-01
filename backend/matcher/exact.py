"""
exact.py
--------
Tier 1 of the matching pipeline: cheap, deterministic, high-confidence
matching on exact keys. This tier should resolve the majority of records
with zero ambiguity -- if something lands here, a human should be able to
trust it without re-checking.

Two independent matches happen at this tier:

1. Ledger <-> Settlement, keyed on order_id.
   Tells us: "did this order actually get paid out by the gateway?"

2. Settlement (grouped by utr into a batch) <-> Bank statement row,
   keyed on utr / bank_ref, confirmed by a strict amount tolerance.
   Tells us: "did the money the gateway says it sent actually land in
   the bank for the amount we expect?"

Anything that fails either check is NOT discarded -- it's returned as an
explicit unmatched/mismatched record for Tier 2 (fuzzy_batch.py) to
attempt, and if that also fails, for the LLM reasoning layer to explain.
"""

from dataclasses import dataclass, field

import pandas as pd

EXACT_AMOUNT_TOLERANCE = 0.02  # ₹0.02 -- covers float/paise rounding only,
                                # NOT genuine drift. Genuine drift is a Tier 2 concern.


@dataclass
class LedgerSettlementResult:
    matched: pd.DataFrame            # order_id, invoice_id, settlement rows joined
    orphan_ledger: pd.DataFrame      # ledger rows with no settlement at all
    orphan_settlement: pd.DataFrame  # settlement rows with no ledger entry


@dataclass
class SettlementBankResult:
    matched_batches: pd.DataFrame     # utr, bank_row_id, settled sum, bank amount, diff
    unmatched_batches: pd.DataFrame   # utr batches whose sum didn't hit the bank amount
    unmatched_bank_rows: pd.DataFrame  # bank rows with no utr in settlement at all


def match_ledger_settlement(ledger: pd.DataFrame, settlement: pd.DataFrame) -> LedgerSettlementResult:
    """Tier 1a: exact order_id join between the internal ledger and the
    gateway settlement export."""
    merged = ledger.merge(
        settlement, on="order_id", how="outer", indicator=True, suffixes=("_ledger", "_settlement")
    )

    matched = merged[merged["_merge"] == "both"].drop(columns="_merge")
    orphan_ledger = merged[merged["_merge"] == "left_only"].drop(columns="_merge")
    orphan_settlement = merged[merged["_merge"] == "right_only"].drop(columns="_merge")

    return LedgerSettlementResult(
        matched=matched.reset_index(drop=True),
        orphan_ledger=orphan_ledger[["order_id", "invoice_id", "invoice_amount", "customer",
                                      "status", "created_at"]].reset_index(drop=True),
        orphan_settlement=orphan_settlement[["order_id", "settlement_id", "payment_id",
                                              "gross_amount", "net_amount", "settled_at",
                                              "utr"]].reset_index(drop=True),
    )


def match_settlement_bank(settlement: pd.DataFrame, bank: pd.DataFrame,
                           tolerance: float = EXACT_AMOUNT_TOLERANCE) -> SettlementBankResult:
    """Tier 1b: group settlement rows into their batch (by utr), sum the
    net_amount, and check it lands exactly on a single bank statement row
    with the same utr / bank_ref.

    A batch only clears Tier 1 if:
      - exactly one bank row carries that bank_ref (no duplicates), AND
      - the settled sum matches the bank amount within `tolerance`.

    Everything else -- multiple bank rows sharing a ref (possible
    duplicate), or a sum that's off by more than rounding -- is handed to
    Tier 2 rather than guessed at here.
    """
    batch_sums = (
        settlement.groupby("utr", as_index=False)["net_amount"]
        .sum()
        .rename(columns={"net_amount": "settled_sum", "utr": "bank_ref"})
    )

    bank_ref_counts = bank.groupby("bank_ref").size().rename("bank_ref_count")
    bank_with_counts = bank.join(bank_ref_counts, on="bank_ref")

    merged = batch_sums.merge(bank_with_counts, on="bank_ref", how="outer", indicator=True)

    unmatched_bank_rows = merged[merged["_merge"] == "right_only"][
        ["bank_row_id", "bank_ref", "amount", "txn_date", "narration"]
    ].reset_index(drop=True)

    both = merged[merged["_merge"] == "both"].copy()
    both["diff"] = (both["amount"] - both["settled_sum"]).round(2)
    both["within_tolerance"] = both["diff"].abs() <= tolerance
    both["is_unique_bank_ref"] = both["bank_ref_count"] == 1

    is_clean_match = both["within_tolerance"] & both["is_unique_bank_ref"]

    matched_batches = both[is_clean_match][
        ["bank_ref", "bank_row_id", "settled_sum", "amount", "diff", "txn_date", "narration"]
    ].reset_index(drop=True)

    unmatched_batches = both[~is_clean_match][
        ["bank_ref", "bank_row_id", "settled_sum", "amount", "diff",
         "bank_ref_count", "txn_date", "narration"]
    ].reset_index(drop=True)

    return SettlementBankResult(
        matched_batches=matched_batches,
        unmatched_batches=unmatched_batches,
        unmatched_bank_rows=unmatched_bank_rows,
    )
