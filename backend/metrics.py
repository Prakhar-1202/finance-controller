"""
metrics.py
----------
Reusable metrics helpers consumed by the FastAPI layer, CLI reports, and
anything else that needs numeric summaries of a reconciliation run.

Every function here takes the result dataclasses that pipeline.py and
categorizer.py already produce -- it never re-runs matching or reads CSV
files itself.  This keeps a single source of truth for the actual
reconciliation logic (pipeline.py + categorizer.py) and avoids the drift
that would come from duplicating it here.

Functions fall into two groups:

1. Operational metrics (no ground truth needed):
   - reconciliation_rate   -- what fraction of orders are fully reconciled
   - exception_rate        -- what fraction are NOT reconciled
   - exception_counts      -- breakdown of exceptions by category

2. Evaluation metrics (require a ground_truth DataFrame):
   - precision_recall_f1   -- overall and optionally per-case_type
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from backend.pipeline import ReconciliationResult
from backend.categorizer import CategorizationResult, total_reconciled_order_ids


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _total_distinct_orders(result: ReconciliationResult) -> int:
    """Count the universe of distinct order_ids across ledger and settlement.

    This mirrors the count used by run_reconciliation.py's CLI report so the
    denominator is consistent project-wide.
    """
    all_orders = pd.concat([
        result.ledger[["order_id"]],
        result.settlement[["order_id"]],
    ]).drop_duplicates(subset=["order_id"])
    return len(all_orders)


# ---------------------------------------------------------------------------
# 1. Operational metrics (no ground truth)
# ---------------------------------------------------------------------------

@dataclass
class ReconciliationMetrics:
    total_orders: int
    reconciled_orders: int
    unreconciled_orders: int
    reconciliation_rate: float   # 0.0 – 1.0
    exception_rate: float        # 1.0 - reconciliation_rate
def reconciliation_rate(
    result: ReconciliationResult,
    cat_result: Optional[CategorizationResult] = None,
) -> ReconciliationMetrics:
    """Compute the headline reconciliation / exception rates.

    If *cat_result* is provided (or attached to *result.cat_result*), the
    reconciled set includes Tier 3 recoveries (via ``total_reconciled_order_ids``);
    otherwise only the strict Tier 1 set from ``result.reconciled_order_ids()``
    is used.
    """
    total = _total_distinct_orders(result)
    if cat_result is None:
        cat_result = result.cat_result
    if cat_result is not None:
        reconciled = len(total_reconciled_order_ids(result, cat_result))
    else:
        reconciled = len(result.reconciled_order_ids())

    unreconciled = total - reconciled
    rate = reconciled / total if total else 0.0
    return ReconciliationMetrics(
        total_orders=total,
        reconciled_orders=reconciled,
        unreconciled_orders=unreconciled,
        reconciliation_rate=rate,
        exception_rate=1.0 - rate,
    )


def exception_rate(
    result: ReconciliationResult,
    cat_result: Optional[CategorizationResult] = None,
) -> float:
    """Convenience shortcut -- returns just the exception rate as a float."""
    return reconciliation_rate(result, cat_result).exception_rate


@dataclass
class ExceptionCounts:
    """Breakdown of exception counts by category and measurement unit across tiers.

    Fields and their measurement units:
    - orphan_ledger: count of ledger orders (invoiced but never paid)
    - orphan_settlement: count of settlement orders (paid but never invoiced)
    - unmatched_batches: count of settlement batches / UTRs failing Tier 1b
    - duplicate_bank_rows: count of bank statement rows flagged as duplicates
    - drift_by_category: mapping of category -> count of unmatched batches
    - subset_sum_matches: count of bank statement rows resolved via subset-sum
    - tier3_batch_categories: mapping of category -> count of settlement batches (Tier 3)
    - tier3_order_exceptions: count of individual orders flagged as exceptions (Tier 3)
    """
    orphan_ledger: int               # unit: orders
    orphan_settlement: int           # unit: orders / settlement records
    unmatched_batches: int           # unit: settlement batches (UTRs)
    duplicate_bank_rows: int         # unit: bank statement rows
    drift_by_category: dict[str, int]  # unit: category -> batch count
    subset_sum_matches: int          # unit: bank statement rows / batch matches
    # Tier 3 (only populated when cat_result is supplied)
    tier3_batch_categories: dict[str, int]  # unit: category -> batch count
    tier3_order_exceptions: int           # unit: orders


def exception_counts(
    result: ReconciliationResult,
    cat_result: Optional[CategorizationResult] = None,
) -> ExceptionCounts:
    """Break down exceptions by category across all tiers."""
    if cat_result is None:
        cat_result = result.cat_result

    # Tier 2 drift categories
    drift_cats: dict = {}
    if not result.drift_classified.empty:
        drift_cats = result.drift_classified["category"].value_counts().to_dict()

    # Tier 3
    tier3_batch_cats: dict = {}
    tier3_order_exc = 0
    if cat_result is not None:
        if not cat_result.batch_report.empty:
            tier3_batch_cats = (
                cat_result.batch_report["category"].value_counts().to_dict()
            )
        tier3_order_exc = len(cat_result.order_exceptions)

    return ExceptionCounts(
        orphan_ledger=len(result.ls_result.orphan_ledger),
        orphan_settlement=len(result.ls_result.orphan_settlement),
        unmatched_batches=len(result.sb_result.unmatched_batches),
        duplicate_bank_rows=len(result.duplicates),
        drift_by_category=drift_cats,
        subset_sum_matches=len(result.subset_matches),
        tier3_batch_categories=tier3_batch_cats,
        tier3_order_exceptions=tier3_order_exc,
    )


# ---------------------------------------------------------------------------
# 2. Evaluation metrics (require ground truth)
# ---------------------------------------------------------------------------

@dataclass
class PRFScores:
    tp: int
    fp: int
    tn: int
    fn: int
    precision: float   # NaN when tp + fp == 0
    recall: float      # NaN when tp + fn == 0
    f1: float          # NaN when precision + recall == 0 or either is NaN


def _compute_prf(tp: int, fp: int, tn: int, fn: int) -> PRFScores:
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    if (
        math.isnan(precision)
        or math.isnan(recall)
        or (precision + recall) == 0
    ):
        f1 = float("nan")
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return PRFScores(tp=tp, fp=fp, tn=tn, fn=fn,
                     precision=precision, recall=recall, f1=f1)


def precision_recall_f1(
    result: ReconciliationResult,
    ground_truth: pd.DataFrame,
    cat_result: Optional[CategorizationResult] = None,
    per_case_type: bool = False,
) -> PRFScores | dict[str, PRFScores]:
    """Compute precision / recall / F1 against a labelled ground-truth CSV.

    Parameters
    ----------
    result : ReconciliationResult
        Output of ``run_pipeline()``.
    ground_truth : pd.DataFrame
        Must contain at least ``order_id`` and ``expected_match`` columns.
        Optionally contains ``case_type`` for per-category breakdown.
    cat_result : CategorizationResult, optional
        If provided, the reconciled set includes Tier 3 recoveries.
    per_case_type : bool
        If True, return a dict mapping each ``case_type`` to its own
        ``PRFScores``; the overall scores are keyed under ``"_overall"``.

    Returns
    -------
    PRFScores (when ``per_case_type=False``) or
    dict[str, PRFScores] (when ``per_case_type=True``, overall under
    ``"_overall"``).
    """
    if cat_result is None:
        cat_result = result.cat_result

    if cat_result is not None:
        reconciled_ids = total_reconciled_order_ids(result, cat_result)
    else:
        reconciled_ids = result.reconciled_order_ids()

    gt = ground_truth.copy()
    gt["predicted_match"] = gt["order_id"].isin(reconciled_ids)
    gt["expected_match"] = gt["expected_match"].astype(bool)

    def _scores_for(df: pd.DataFrame) -> PRFScores:
        tp = int(((df["predicted_match"]) & (df["expected_match"])).sum())
        fp = int(((df["predicted_match"]) & (~df["expected_match"])).sum())
        tn = int(((~df["predicted_match"]) & (~df["expected_match"])).sum())
        fn = int(((~df["predicted_match"]) & (df["expected_match"])).sum())
        return _compute_prf(tp, fp, tn, fn)

    overall = _scores_for(gt)

    if not per_case_type:
        return overall

    breakdown: dict[str, PRFScores] = {"_overall": overall}
    if "case_type" in gt.columns:
        for case_type, group in gt.groupby("case_type"):
            breakdown[case_type] = _scores_for(group)
    return breakdown
