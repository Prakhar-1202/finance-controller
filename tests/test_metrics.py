"""
test_metrics.py
---------------
Tests for backend.metrics — the reusable metrics helpers.

All tests build small, self-contained DataFrames and result objects so they
are deterministic and don't depend on the real CSV data.  The test fixtures
construct the same dataclass shapes that pipeline.py and categorizer.py
produce, exercising every public function in metrics.py.
"""

import math
from dataclasses import dataclass

import pandas as pd
import pytest

from backend.pipeline import ReconciliationResult
from backend.matcher.exact import LedgerSettlementResult, SettlementBankResult
from backend.categorizer import CategorizationResult, total_reconciled_order_ids
from backend.metrics import (
    reconciliation_rate,
    exception_rate,
    exception_counts,
    precision_recall_f1,
    ReconciliationMetrics,
    ExceptionCounts,
    PRFScores,
    _total_distinct_orders,
    _compute_prf,
)


# ---------------------------------------------------------------------------
# Helpers to build lightweight result objects
# ---------------------------------------------------------------------------

def _empty_df(columns):
    return pd.DataFrame(columns=columns)


def _make_ledger(order_ids):
    return pd.DataFrame({"order_id": order_ids})


def _make_settlement(order_ids, utrs=None):
    if utrs is None:
        utrs = [f"utr_{oid}" for oid in order_ids]
    return pd.DataFrame({"order_id": order_ids, "utr": utrs, "net_amount": [100.0] * len(order_ids)})


def _make_ls_result(matched_oids, orphan_ledger_oids=None, orphan_settlement_oids=None):
    """Build a minimal LedgerSettlementResult."""
    matched = pd.DataFrame({
        "order_id": matched_oids,
        "utr": [f"utr_{oid}" for oid in matched_oids],
    })
    orphan_ledger_oids = orphan_ledger_oids or []
    orphan_settlement_oids = orphan_settlement_oids or []
    return LedgerSettlementResult(
        matched=matched,
        orphan_ledger=pd.DataFrame({
            "order_id": orphan_ledger_oids,
            "invoice_id": [f"INV-{o}" for o in orphan_ledger_oids],
            "invoice_amount": [0.0] * len(orphan_ledger_oids),
            "customer": ["c"] * len(orphan_ledger_oids),
            "status": ["paid"] * len(orphan_ledger_oids),
            "created_at": pd.NaT,
        }),
        orphan_settlement=pd.DataFrame({
            "order_id": orphan_settlement_oids,
            "settlement_id": [f"S-{o}" for o in orphan_settlement_oids],
            "payment_id": [f"P-{o}" for o in orphan_settlement_oids],
            "gross_amount": [0.0] * len(orphan_settlement_oids),
            "net_amount": [0.0] * len(orphan_settlement_oids),
            "settled_at": pd.NaT,
            "utr": [f"utr_{o}" for o in orphan_settlement_oids],
        }),
    )


def _make_sb_result(matched_refs, unmatched_batch_refs=None, unmatched_bank_rows=None):
    """Build a minimal SettlementBankResult."""
    matched = pd.DataFrame({
        "bank_ref": matched_refs,
        "bank_row_id": list(range(len(matched_refs))),
        "settled_sum": [100.0] * len(matched_refs),
        "amount": [100.0] * len(matched_refs),
        "diff": [0.0] * len(matched_refs),
        "txn_date": pd.NaT,
        "narration": [""] * len(matched_refs),
    })
    unmatched_batch_refs = unmatched_batch_refs or []
    base_id = len(matched_refs)
    unmatched_batches = pd.DataFrame({
        "bank_ref": unmatched_batch_refs,
        "bank_row_id": list(range(base_id, base_id + len(unmatched_batch_refs))),
        "settled_sum": [100.0] * len(unmatched_batch_refs),
        "amount": [105.0] * len(unmatched_batch_refs),
        "diff": [5.0] * len(unmatched_batch_refs),
        "bank_ref_count": [1] * len(unmatched_batch_refs),
        "txn_date": pd.NaT,
        "narration": [""] * len(unmatched_batch_refs),
    })
    unmatched_bank_rows = unmatched_bank_rows or []
    ub_base = base_id + len(unmatched_batch_refs)
    ub_df = pd.DataFrame({
        "bank_row_id": list(range(ub_base, ub_base + len(unmatched_bank_rows))),
        "bank_ref": unmatched_bank_rows,
        "amount": [200.0] * len(unmatched_bank_rows),
        "txn_date": pd.NaT,
        "narration": [""] * len(unmatched_bank_rows),
    })
    return SettlementBankResult(
        matched_batches=matched,
        unmatched_batches=unmatched_batches,
        unmatched_bank_rows=ub_df,
    )


def _make_recon_result(
    ledger_oids,
    settlement_oids,
    matched_ls_oids,
    matched_sb_refs,
    orphan_ledger_oids=None,
    orphan_settlement_oids=None,
    unmatched_batch_refs=None,
    unmatched_bank_rows=None,
    duplicates=None,
    drift_classified=None,
    subset_matches=None,
):
    """Build a minimal ReconciliationResult from order IDs and refs.

    The matched_ls_oids utrs must appear in matched_sb_refs for
    reconciled_order_ids() to count them as fully reconciled.
    """
    bank_refs_in_matched = [f"utr_{oid}" for oid in matched_ls_oids]
    # Ensure the settlement UTRs for matched orders are in the matched bank refs
    sb_matched_refs = list(set(matched_sb_refs) | set(bank_refs_in_matched))

    ls = _make_ls_result(matched_ls_oids, orphan_ledger_oids, orphan_settlement_oids)
    sb = _make_sb_result(
        sb_matched_refs,
        unmatched_batch_refs,
        unmatched_bank_rows,
    )

    bank = pd.DataFrame({
        "bank_row_id": list(range(10)),
        "bank_ref": [f"ref_{i}" for i in range(10)],
        "amount": [100.0] * 10,
        "txn_date": pd.NaT,
        "narration": [""] * 10,
        "batch_notes": ["clean"] * 10,
    })

    if duplicates is None:
        duplicates = _empty_df([
            "bank_row_id", "bank_ref", "amount", "txn_date", "narration",
            "presumed_original_bank_row_id", "category", "confidence",
        ])
    if drift_classified is None:
        drift_classified = _empty_df([
            "bank_ref", "bank_row_id", "settled_sum", "amount", "diff",
            "bank_ref_count", "txn_date", "narration", "category", "confidence",
        ])
    if subset_matches is None:
        subset_matches = []

    return ReconciliationResult(
        bank=bank,
        settlement=_make_settlement(settlement_oids),
        ledger=_make_ledger(ledger_oids),
        ls_result=ls,
        sb_result=sb,
        duplicates=duplicates,
        drift_classified=drift_classified,
        subset_matches=subset_matches,
    )


def _make_cat_result(resolved_oids=None, exception_rows=None, batch_rows=None):
    resolved_oids = resolved_oids or set()
    exception_rows = exception_rows or []
    batch_rows = batch_rows or []
    return CategorizationResult(
        resolved_order_ids=set(resolved_oids),
        order_exceptions=pd.DataFrame(
            exception_rows,
            columns=["order_id", "bank_ref", "category", "reason"],
        ),
        batch_report=pd.DataFrame(
            batch_rows,
            columns=["bank_ref", "category", "n_orders", "n_resolved", "n_excluded", "diff"],
        ),
    )


# ---------------------------------------------------------------------------
# Tests: _compute_prf
# ---------------------------------------------------------------------------

class TestComputePRF:
    def test_perfect(self):
        scores = _compute_prf(tp=10, fp=0, tn=5, fn=0)
        assert scores.precision == 1.0
        assert scores.recall == 1.0
        assert scores.f1 == 1.0

    def test_all_wrong(self):
        scores = _compute_prf(tp=0, fp=5, tn=0, fn=5)
        assert scores.precision == 0.0
        assert scores.recall == 0.0
        # F1 is NaN when precision + recall == 0
        assert math.isnan(scores.f1)

    def test_no_predictions(self):
        scores = _compute_prf(tp=0, fp=0, tn=5, fn=3)
        assert math.isnan(scores.precision)
        assert scores.recall == 0.0
        assert math.isnan(scores.f1)

    def test_no_positives_in_ground_truth(self):
        scores = _compute_prf(tp=0, fp=3, tn=5, fn=0)
        assert scores.precision == 0.0
        assert math.isnan(scores.recall)
        assert math.isnan(scores.f1)

    def test_partial(self):
        scores = _compute_prf(tp=4, fp=1, tn=3, fn=2)
        assert scores.precision == pytest.approx(4 / 5)
        assert scores.recall == pytest.approx(4 / 6)
        expected_f1 = 2 * (4 / 5) * (4 / 6) / ((4 / 5) + (4 / 6))
        assert scores.f1 == pytest.approx(expected_f1)


# ---------------------------------------------------------------------------
# Tests: _total_distinct_orders
# ---------------------------------------------------------------------------

class TestTotalDistinctOrders:
    def test_overlap(self):
        result = _make_recon_result(
            ledger_oids=["A", "B", "C"],
            settlement_oids=["B", "C", "D"],
            matched_ls_oids=["B", "C"],
            matched_sb_refs=[],
        )
        assert _total_distinct_orders(result) == 4  # A, B, C, D

    def test_no_overlap(self):
        result = _make_recon_result(
            ledger_oids=["A", "B"],
            settlement_oids=["C", "D"],
            matched_ls_oids=[],
            matched_sb_refs=[],
        )
        assert _total_distinct_orders(result) == 4

    def test_identical(self):
        result = _make_recon_result(
            ledger_oids=["A", "B"],
            settlement_oids=["A", "B"],
            matched_ls_oids=["A", "B"],
            matched_sb_refs=[],
        )
        assert _total_distinct_orders(result) == 2


# ---------------------------------------------------------------------------
# Tests: reconciliation_rate / exception_rate
# ---------------------------------------------------------------------------

class TestReconciliationRate:
    def test_all_reconciled(self):
        result = _make_recon_result(
            ledger_oids=["A", "B"],
            settlement_oids=["A", "B"],
            matched_ls_oids=["A", "B"],
            matched_sb_refs=[],
        )
        m = reconciliation_rate(result)
        assert m.total_orders == 2
        assert m.reconciled_orders == 2
        assert m.unreconciled_orders == 0
        assert m.reconciliation_rate == 1.0
        assert m.exception_rate == 0.0

    def test_partial_reconciliation(self):
        result = _make_recon_result(
            ledger_oids=["A", "B", "C", "D"],
            settlement_oids=["A", "B", "C", "D"],
            matched_ls_oids=["A", "B"],  # only 2 of 4 matched + bank-confirmed
            matched_sb_refs=[],
        )
        m = reconciliation_rate(result)
        assert m.total_orders == 4
        assert m.reconciled_orders == 2
        assert m.reconciliation_rate == pytest.approx(0.5)
        assert m.exception_rate == pytest.approx(0.5)

    def test_none_reconciled(self):
        result = _make_recon_result(
            ledger_oids=["A", "B"],
            settlement_oids=["A", "B"],
            matched_ls_oids=[],
            matched_sb_refs=[],
        )
        m = reconciliation_rate(result)
        assert m.reconciled_orders == 0
        assert m.reconciliation_rate == 0.0
        assert m.exception_rate == 1.0

    def test_with_categorizer_recovery(self):
        """Tier 3 recovers extra orders, increasing the reconciled count."""
        result = _make_recon_result(
            ledger_oids=["A", "B", "C", "D"],
            settlement_oids=["A", "B", "C", "D"],
            matched_ls_oids=["A", "B"],
            matched_sb_refs=[],
        )
        cat = _make_cat_result(resolved_oids={"C"})
        m = reconciliation_rate(result, cat)
        assert m.reconciled_orders == 3  # A, B from Tier 1 + C from Tier 3
        assert m.reconciliation_rate == pytest.approx(0.75)


class TestExceptionRate:
    def test_shortcut_matches_full(self):
        result = _make_recon_result(
            ledger_oids=["A", "B", "C", "D"],
            settlement_oids=["A", "B", "C", "D"],
            matched_ls_oids=["A"],
            matched_sb_refs=[],
        )
        full = reconciliation_rate(result)
        short = exception_rate(result)
        assert short == full.exception_rate


# ---------------------------------------------------------------------------
# Tests: exception_counts
# ---------------------------------------------------------------------------

class TestExceptionCounts:
    def test_basic_counts(self):
        result = _make_recon_result(
            ledger_oids=["A", "B", "C"],
            settlement_oids=["A", "B", "D"],
            matched_ls_oids=["A", "B"],
            matched_sb_refs=[],
            orphan_ledger_oids=["C"],
            orphan_settlement_oids=["D"],
            unmatched_batch_refs=["bad_batch_1", "bad_batch_2"],
        )
        ec = exception_counts(result)
        assert ec.orphan_ledger == 1
        assert ec.orphan_settlement == 1
        assert ec.unmatched_batches == 2
        assert ec.duplicate_bank_rows == 0
        assert ec.drift_by_category == {}
        assert ec.subset_sum_matches == 0
        assert ec.tier3_batch_categories == {}
        assert ec.tier3_order_exceptions == 0

    def test_with_duplicates(self):
        dupes = pd.DataFrame({
            "bank_row_id": [5, 6],
            "bank_ref": ["ref_x", "ref_x"],
            "amount": [100.0, 100.0],
            "txn_date": pd.NaT,
            "narration": ["", ""],
            "presumed_original_bank_row_id": [4, 4],
            "category": ["duplicate_bank_row", "duplicate_bank_row"],
            "confidence": ["high", "high"],
        })
        result = _make_recon_result(
            ledger_oids=["A"],
            settlement_oids=["A"],
            matched_ls_oids=["A"],
            matched_sb_refs=[],
            duplicates=dupes,
        )
        ec = exception_counts(result)
        assert ec.duplicate_bank_rows == 2

    def test_with_drift_classified(self):
        drift = pd.DataFrame({
            "bank_ref": ["r1", "r2", "r3"],
            "bank_row_id": [10, 11, 12],
            "settled_sum": [100, 200, 300],
            "amount": [102, 205, 500],
            "diff": [2, 5, 200],
            "bank_ref_count": [1, 1, 1],
            "txn_date": pd.NaT,
            "narration": ["", "", ""],
            "category": ["fee_drift", "fee_drift", "unresolved_amount_gap"],
            "confidence": ["medium", "medium", "low"],
        })
        result = _make_recon_result(
            ledger_oids=["A"],
            settlement_oids=["A"],
            matched_ls_oids=["A"],
            matched_sb_refs=[],
            drift_classified=drift,
        )
        ec = exception_counts(result)
        assert ec.drift_by_category == {"fee_drift": 2, "unresolved_amount_gap": 1}

    def test_with_categorizer(self):
        result = _make_recon_result(
            ledger_oids=["A"],
            settlement_oids=["A"],
            matched_ls_oids=["A"],
            matched_sb_refs=[],
        )
        cat = _make_cat_result(
            resolved_oids={"X"},
            exception_rows=[
                {"order_id": "Y", "bank_ref": "r1", "category": "unresolved", "reason": "no match"},
                {"order_id": "Z", "bank_ref": "r2", "category": "unresolved", "reason": "no match"},
            ],
            batch_rows=[
                {"bank_ref": "r1", "category": "duplicate_exact_after_dedup", "n_orders": 3,
                 "n_resolved": 2, "n_excluded": 1, "diff": 0.01},
                {"bank_ref": "r2", "category": "unresolved", "n_orders": 2,
                 "n_resolved": 0, "n_excluded": 2, "diff": 50.0},
            ],
        )
        ec = exception_counts(result, cat)
        assert ec.tier3_order_exceptions == 2
        assert ec.tier3_batch_categories == {
            "duplicate_exact_after_dedup": 1,
            "unresolved": 1,
        }


# ---------------------------------------------------------------------------
# Tests: precision_recall_f1
# ---------------------------------------------------------------------------

class TestPrecisionRecallF1:
    def _ground_truth(self, rows):
        """Build a ground_truth DataFrame from (order_id, expected_match, case_type) tuples."""
        return pd.DataFrame(rows, columns=["order_id", "expected_match", "case_type"])

    def test_perfect_scores(self):
        result = _make_recon_result(
            ledger_oids=["A", "B", "C"],
            settlement_oids=["A", "B", "C"],
            matched_ls_oids=["A", "B"],
            matched_sb_refs=[],
        )
        gt = self._ground_truth([
            ("A", True, "clean"),
            ("B", True, "clean"),
            ("C", False, "orphan"),
        ])
        scores = precision_recall_f1(result, gt)
        assert scores.tp == 2
        assert scores.fn == 0
        assert scores.fp == 0
        assert scores.tn == 1
        assert scores.precision == 1.0
        assert scores.recall == 1.0
        assert scores.f1 == 1.0

    def test_false_positives_and_negatives(self):
        # A is reconciled but shouldn't be (FP), D should be but isn't (FN)
        result = _make_recon_result(
            ledger_oids=["A", "B", "C", "D"],
            settlement_oids=["A", "B", "C", "D"],
            matched_ls_oids=["A", "B"],
            matched_sb_refs=[],
        )
        gt = self._ground_truth([
            ("A", False, "delayed"),    # FP: reconciled but expected False
            ("B", True, "clean"),       # TP
            ("C", False, "orphan"),     # TN
            ("D", True, "clean"),       # FN: not reconciled but expected True
        ])
        scores = precision_recall_f1(result, gt)
        assert scores.tp == 1
        assert scores.fp == 1
        assert scores.tn == 1
        assert scores.fn == 1
        assert scores.precision == pytest.approx(0.5)
        assert scores.recall == pytest.approx(0.5)

    def test_per_case_type(self):
        result = _make_recon_result(
            ledger_oids=["A", "B", "C", "D"],
            settlement_oids=["A", "B", "C", "D"],
            matched_ls_oids=["A", "B"],
            matched_sb_refs=[],
        )
        gt = self._ground_truth([
            ("A", True, "clean"),
            ("B", True, "clean"),
            ("C", False, "orphan"),
            ("D", True, "delayed"),
        ])
        breakdown = precision_recall_f1(result, gt, per_case_type=True)
        assert "_overall" in breakdown
        assert "clean" in breakdown
        assert "orphan" in breakdown
        assert "delayed" in breakdown

        # clean: A(TP), B(TP) → precision=1.0, recall=1.0
        assert breakdown["clean"].tp == 2
        assert breakdown["clean"].precision == 1.0
        assert breakdown["clean"].recall == 1.0

        # orphan: C(TN) → no predicted positives, no actual positives
        assert breakdown["orphan"].tn == 1
        assert breakdown["orphan"].tp == 0

        # delayed: D(FN) → missed
        assert breakdown["delayed"].fn == 1

    def test_with_categorizer(self):
        """Tier 3 recoveries change the predicted set."""
        result = _make_recon_result(
            ledger_oids=["A", "B", "C"],
            settlement_oids=["A", "B", "C"],
            matched_ls_oids=["A"],
            matched_sb_refs=[],
        )
        cat = _make_cat_result(resolved_oids={"B"})
        gt = self._ground_truth([
            ("A", True, "clean"),
            ("B", True, "clean"),
            ("C", False, "orphan"),
        ])
        # Without cat: A reconciled → TP=1, FN=1 (B missed)
        scores_no_cat = precision_recall_f1(result, gt)
        assert scores_no_cat.tp == 1
        assert scores_no_cat.fn == 1

        # With cat: A + B reconciled → TP=2, FN=0
        scores_with_cat = precision_recall_f1(result, gt, cat)
        assert scores_with_cat.tp == 2
        assert scores_with_cat.fn == 0
        assert scores_with_cat.precision == 1.0
        assert scores_with_cat.recall == 1.0
        assert scores_with_cat.f1 == 1.0

    def test_empty_ground_truth(self):
        result = _make_recon_result(
            ledger_oids=["A"],
            settlement_oids=["A"],
            matched_ls_oids=["A"],
            matched_sb_refs=[],
        )
        gt = self._ground_truth([])
        scores = precision_recall_f1(result, gt)
        assert scores.tp == 0
        assert math.isnan(scores.precision)
        assert math.isnan(scores.recall)

    def test_no_case_type_column_returns_overall_only(self):
        """per_case_type=True with no case_type column still works."""
        result = _make_recon_result(
            ledger_oids=["A"],
            settlement_oids=["A"],
            matched_ls_oids=["A"],
            matched_sb_refs=[],
        )
        gt = pd.DataFrame({"order_id": ["A"], "expected_match": [True]})
        breakdown = precision_recall_f1(result, gt, per_case_type=True)
        assert "_overall" in breakdown
        assert len(breakdown) == 1  # only _overall, no case_type groups
