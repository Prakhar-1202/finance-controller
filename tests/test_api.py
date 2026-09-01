"""
test_api.py
-----------
Focused API tests for the FastAPI layer defined in backend/main.py.

Tests use FastAPI's TestClient and monkey-patch _cached_pipeline to inject
small synthetic ReconciliationResult objects so the tests:
 - are fast (no CSV I/O)
 - are deterministic (not dataset-dependent)
 - do not test reconciliation logic (that lives in other test files)
 - verify only routing, serialisation, and schema correctness

Reconciliation correctness is already covered by:
  tests/test_exact_match.py
  tests/test_fuzzy_batch.py
  tests/test_llm_reasoner.py
  tests/test_metrics.py
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.pipeline import ReconciliationResult
from backend.matcher.exact import LedgerSettlementResult, SettlementBankResult
from backend.categorizer import CategorizationResult


# ---------------------------------------------------------------------------
# Fixture helpers (mirrors test_metrics.py lightweight builders)
# ---------------------------------------------------------------------------

def _empty(columns):
    return pd.DataFrame(columns=columns)


def _make_bank(n=2):
    return pd.DataFrame({
        "bank_row_id": list(range(n)),
        "bank_ref": [f"UTR-{i}" for i in range(n)],
        "amount": [1000.0] * n,
        "txn_date": pd.Timestamp("2026-07-01"),
        "narration": ["NEFT"] * n,
        "batch_notes": ["clean"] * n,
    })


def _make_full_result(
    reconciled_oids=("ord_A",),
    orphan_ledger_oids=(),
    orphan_settlement_oids=(),
    dup_rows=None,
    drift_rows=None,
    order_exception_rows=None,
    batch_report_rows=None,
    tier3_resolved_oids=(),
) -> ReconciliationResult:
    """Build a minimal but structurally correct ReconciliationResult."""
    all_oids = list(reconciled_oids) + list(orphan_ledger_oids) + list(orphan_settlement_oids)

    matched_utr = {oid: f"UTR-match-{oid}" for oid in reconciled_oids}
    matched = pd.DataFrame({
        "order_id": list(reconciled_oids),
        "invoice_id": [f"INV-{o}" for o in reconciled_oids],
        "invoice_amount": [5000.0] * len(reconciled_oids),
        "customer": ["Cust"] * len(reconciled_oids),
        "status": ["closed"] * len(reconciled_oids),
        "created_at": pd.Timestamp("2026-06-01"),
        "settlement_id": [f"stl_{o}" for o in reconciled_oids],
        "payment_id": [f"pay_{o}" for o in reconciled_oids],
        "gross_amount": [5200.0] * len(reconciled_oids),
        "fee": [100.0] * len(reconciled_oids),
        "tax_on_fee": [18.0] * len(reconciled_oids),
        "net_amount": [4900.0] * len(reconciled_oids),
        "settled_at": pd.Timestamp("2026-06-05"),
        "utr": list(matched_utr.values()),
    })

    orphan_l = pd.DataFrame({
        "order_id": list(orphan_ledger_oids),
        "invoice_id": [f"INV-{o}" for o in orphan_ledger_oids],
        "invoice_amount": [3000.0] * len(orphan_ledger_oids),
        "customer": ["OldCust"] * len(orphan_ledger_oids),
        "status": ["open"] * len(orphan_ledger_oids),
        "created_at": pd.Timestamp("2026-05-01"),
    })

    orphan_s = pd.DataFrame({
        "order_id": list(orphan_settlement_oids),
        "settlement_id": [f"stl_orphan_{o}" for o in orphan_settlement_oids],
        "payment_id": [f"pay_orphan_{o}" for o in orphan_settlement_oids],
        "gross_amount": [2000.0] * len(orphan_settlement_oids),
        "net_amount": [1900.0] * len(orphan_settlement_oids),
        "settled_at": pd.Timestamp("2026-05-20"),
        "utr": [f"UTR-orphan-{o}" for o in orphan_settlement_oids],
    })

    clean_refs = list(matched_utr.values())
    matched_batches = pd.DataFrame({
        "bank_ref": clean_refs,
        "bank_row_id": list(range(len(clean_refs))),
        "settled_sum": [4900.0] * len(clean_refs),
        "amount": [4900.0] * len(clean_refs),
        "diff": [0.0] * len(clean_refs),
        "txn_date": pd.Timestamp("2026-06-05"),
        "narration": ["NEFT"] * len(clean_refs),
    })

    if dup_rows is None:
        dup_rows = _empty([
            "bank_row_id", "bank_ref", "amount", "txn_date", "narration",
            "presumed_original_bank_row_id", "category", "confidence",
        ])
    if drift_rows is None:
        drift_rows = _empty([
            "bank_ref", "bank_row_id", "settled_sum", "amount", "diff",
            "bank_ref_count", "txn_date", "narration", "category", "confidence",
        ])

    exc_cols = ["order_id", "bank_ref", "category", "reason"]
    rpt_cols = ["bank_ref", "category", "n_orders", "n_resolved", "n_excluded", "diff"]
    cat_result = CategorizationResult(
        resolved_order_ids=set(tier3_resolved_oids),
        order_exceptions=pd.DataFrame(order_exception_rows or [], columns=exc_cols),
        batch_report=pd.DataFrame(batch_report_rows or [], columns=rpt_cols),
    )

    result = ReconciliationResult(
        bank=_make_bank(),
        settlement=pd.DataFrame({
            "order_id": list(reconciled_oids),
            "settlement_id": [f"stl_{o}" for o in reconciled_oids],
            "payment_id": [f"pay_{o}" for o in reconciled_oids],
            "gross_amount": [5200.0] * len(reconciled_oids),
            "fee": [100.0] * len(reconciled_oids),
            "tax_on_fee": [18.0] * len(reconciled_oids),
            "net_amount": [4900.0] * len(reconciled_oids),
            "settled_at": pd.Timestamp("2026-06-05"),
            "utr": list(matched_utr.values()),
        }),
        ledger=pd.DataFrame({
            "order_id": all_oids or list(reconciled_oids),
            "invoice_id": [f"INV-{o}" for o in (all_oids or list(reconciled_oids))],
            "invoice_amount": [5000.0] * len(all_oids or list(reconciled_oids)),
            "customer": ["Cust"] * len(all_oids or list(reconciled_oids)),
            "status": ["closed"] * len(all_oids or list(reconciled_oids)),
            "created_at": pd.Timestamp("2026-06-01"),
        }),
        ls_result=LedgerSettlementResult(
            matched=matched,
            orphan_ledger=orphan_l,
            orphan_settlement=orphan_s,
        ),
        sb_result=SettlementBankResult(
            matched_batches=matched_batches,
            unmatched_batches=_empty([
                "bank_ref", "bank_row_id", "settled_sum", "amount", "diff",
                "bank_ref_count", "txn_date", "narration"
            ]),
            unmatched_bank_rows=_empty([
                "bank_row_id", "bank_ref", "amount", "txn_date", "narration"
            ]),
        ),
        duplicates=dup_rows,
        drift_classified=drift_rows,
        subset_matches=[],
        cat_result=cat_result,
    )
    return result


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def simple_result():
    return _make_full_result()


@pytest.fixture
def rich_result():
    """Result with examples of every exception type."""
    dup_rows = pd.DataFrame({
        "bank_row_id": [5],
        "bank_ref": ["UTR-DUPE"],
        "amount": [50000.0],
        "txn_date": pd.Timestamp("2026-07-10"),
        "narration": ["NEFT"],
        "presumed_original_bank_row_id": [4],
        "category": ["duplicate_bank_row"],
        "confidence": ["high"],
    })
    drift_rows = pd.DataFrame({
        "bank_ref": ["UTR-DRIFT"],
        "bank_row_id": [6],
        "settled_sum": [10000.0],
        "amount": [10004.5],
        "diff": [4.5],
        "bank_ref_count": [1],
        "txn_date": pd.Timestamp("2026-07-12"),
        "narration": ["NEFT"],
        "category": ["fee_drift"],
        "confidence": ["medium"],
    })
    exc_rows = [{"order_id": "ord_EXC", "bank_ref": "UTR-EXC",
                 "category": "unresolved", "reason": "No subset match."}]
    rpt_rows = [{"bank_ref": "UTR-EXC", "category": "unresolved",
                 "n_orders": 2, "n_resolved": 0, "n_excluded": 2, "diff": 100.0}]
    return _make_full_result(
        reconciled_oids=("ord_A", "ord_B"),
        orphan_ledger_oids=("ord_L",),
        orphan_settlement_oids=("ord_S",),
        dup_rows=dup_rows,
        drift_rows=drift_rows,
        order_exception_rows=exc_rows,
        batch_report_rows=rpt_rows,
    )


# ---------------------------------------------------------------------------
# POST /api/reconcile
# ---------------------------------------------------------------------------

class TestReconcileEndpoint:
    def test_returns_200(self, client, simple_result):
        with patch("backend.main._cached_pipeline", return_value=simple_result):
            r = client.post("/api/reconcile", json={})
        assert r.status_code == 200

    def test_response_shape(self, client, simple_result):
        with patch("backend.main._cached_pipeline", return_value=simple_result):
            r = client.post("/api/reconcile", json={})
        body = r.json()
        assert "metrics" in body
        assert "exception_counts" in body

    def test_metrics_fields_present(self, client, simple_result):
        with patch("backend.main._cached_pipeline", return_value=simple_result):
            r = client.post("/api/reconcile", json={})
        m = r.json()["metrics"]
        for field in ("total_orders", "reconciled_orders", "unreconciled_orders",
                      "reconciliation_rate", "exception_rate"):
            assert field in m, f"Missing field: {field}"

    def test_no_ground_truth_in_response(self, client, simple_result):
        with patch("backend.main._cached_pipeline", return_value=simple_result):
            r = client.post("/api/reconcile", json={})
        body = r.json()
        # evaluation block must not be present (requires ground_truth.csv)
        assert "evaluation" not in body
        assert "precision" not in str(body)
        assert "recall" not in str(body)

    def test_reconciled_count_is_computed(self, client, simple_result):
        with patch("backend.main._cached_pipeline", return_value=simple_result):
            r = client.post("/api/reconcile", json={})
        m = r.json()["metrics"]
        assert m["reconciled_orders"] >= 0
        assert m["total_orders"] >= m["reconciled_orders"]

    def test_exception_counts_all_fields(self, client, rich_result):
        with patch("backend.main._cached_pipeline", return_value=rich_result):
            r = client.post("/api/reconcile", json={})
        ec = r.json()["exception_counts"]
        for field in ("orphan_ledger", "orphan_settlement", "unmatched_batches",
                      "duplicate_bank_rows", "drift_by_category", "subset_sum_matches",
                      "tier3_batch_categories", "tier3_order_exceptions"):
            assert field in ec, f"Missing field: {field}"

    def test_custom_data_dir_forwarded(self, client, simple_result):
        with patch("backend.main._cached_pipeline", return_value=simple_result) as mock:
            client.post("/api/reconcile", json={"data_dir": "custom_data"})
            mock.assert_called_with("custom_data")


# ---------------------------------------------------------------------------
# GET /api/transactions
# ---------------------------------------------------------------------------

class TestTransactionsEndpoint:
    def test_returns_200(self, client, simple_result):
        with patch("backend.main._cached_pipeline", return_value=simple_result):
            r = client.get("/api/transactions")
        assert r.status_code == 200

    def test_pagination_shape(self, client, simple_result):
        with patch("backend.main._cached_pipeline", return_value=simple_result):
            r = client.get("/api/transactions")
        body = r.json()
        for field in ("total", "page", "page_size", "items"):
            assert field in body

    def test_item_schema_consistent(self, client, rich_result):
        """Every item regardless of status must have the same top-level keys."""
        with patch("backend.main._cached_pipeline", return_value=rich_result):
            r = client.get("/api/transactions")
        items = r.json()["items"]
        assert len(items) > 0
        required_keys = {"order_id", "reconciliation_status"}
        for item in items:
            assert required_keys.issubset(item.keys()), f"Item missing keys: {item}"

    def test_reconciled_status_has_tier(self, client, simple_result):
        with patch("backend.main._cached_pipeline", return_value=simple_result):
            r = client.get("/api/transactions?status=reconciled")
        items = r.json()["items"]
        for item in items:
            assert item["tier"] in ("Tier 1 Exact", "Tier 3 Recovered")

    def test_orphan_ledger_status_filter(self, client, rich_result):
        with patch("backend.main._cached_pipeline", return_value=rich_result):
            r = client.get("/api/transactions?status=orphan_ledger")
        items = r.json()["items"]
        assert all(i["reconciliation_status"] == "orphan_ledger" for i in items)

    def test_orphan_ledger_has_no_utr(self, client, rich_result):
        with patch("backend.main._cached_pipeline", return_value=rich_result):
            r = client.get("/api/transactions?status=orphan_ledger")
        items = r.json()["items"]
        assert len(items) > 0
        for item in items:
            assert item["utr"] is None, "orphan_ledger should have utr=None"

    def test_orphan_settlement_has_no_invoice_id(self, client, rich_result):
        with patch("backend.main._cached_pipeline", return_value=rich_result):
            r = client.get("/api/transactions?status=orphan_settlement")
        items = r.json()["items"]
        assert len(items) > 0
        for item in items:
            assert item["invoice_id"] is None

    def test_exception_status_filter(self, client, rich_result):
        with patch("backend.main._cached_pipeline", return_value=rich_result):
            r = client.get("/api/transactions?status=exception")
        items = r.json()["items"]
        assert all(i["reconciliation_status"] == "exception" for i in items)

    def test_pagination_limits_items(self, client, rich_result):
        with patch("backend.main._cached_pipeline", return_value=rich_result):
            r = client.get("/api/transactions?page=1&page_size=1")
        items = r.json()["items"]
        assert len(items) <= 1

    def test_page_2_offset(self, client, rich_result):
        with patch("backend.main._cached_pipeline", return_value=rich_result):
            r1 = client.get("/api/transactions?page=1&page_size=1")
            r2 = client.get("/api/transactions?page=2&page_size=1")
        items1 = r1.json()["items"]
        items2 = r2.json()["items"]
        if items1 and items2:
            assert items1[0]["order_id"] != items2[0]["order_id"]


# ---------------------------------------------------------------------------
# GET /api/exceptions
# ---------------------------------------------------------------------------

class TestExceptionsEndpoint:
    def test_returns_200(self, client, simple_result):
        with patch("backend.main._cached_pipeline", return_value=simple_result):
            r = client.get("/api/exceptions")
        assert r.status_code == 200

    def test_response_top_level_keys(self, client, simple_result):
        with patch("backend.main._cached_pipeline", return_value=simple_result):
            r = client.get("/api/exceptions")
        body = r.json()
        for key in ("duplicate_bank_rows", "drift_batches",
                    "tier3_order_exceptions", "tier3_batch_report"):
            assert key in body

    def test_empty_exceptions_returns_empty_lists(self, client, simple_result):
        with patch("backend.main._cached_pipeline", return_value=simple_result):
            r = client.get("/api/exceptions")
        body = r.json()
        assert body["duplicate_bank_rows"] == []
        assert body["drift_batches"] == []
        assert body["tier3_order_exceptions"] == []

    def test_duplicate_rows_schema(self, client, rich_result):
        with patch("backend.main._cached_pipeline", return_value=rich_result):
            r = client.get("/api/exceptions")
        dups = r.json()["duplicate_bank_rows"]
        assert len(dups) == 1
        row = dups[0]
        for field in ("bank_row_id", "bank_ref", "amount", "confidence",
                      "presumed_original_bank_row_id"):
            assert field in row

    def test_drift_batches_are_batch_level(self, client, rich_result):
        """drift_batches must NOT be expanded to individual orders."""
        with patch("backend.main._cached_pipeline", return_value=rich_result):
            r = client.get("/api/exceptions")
        drifts = r.json()["drift_batches"]
        assert len(drifts) == 1
        assert "bank_ref" in drifts[0]
        assert "category" in drifts[0]
        # Must NOT have order_id — drift is a batch-level concept
        assert "order_id" not in drifts[0]

    def test_tier3_order_exceptions_schema(self, client, rich_result):
        with patch("backend.main._cached_pipeline", return_value=rich_result):
            r = client.get("/api/exceptions")
        excs = r.json()["tier3_order_exceptions"]
        assert len(excs) == 1
        exc = excs[0]
        for field in ("order_id", "category", "reason"):
            assert field in exc

    def test_batch_report_schema(self, client, rich_result):
        with patch("backend.main._cached_pipeline", return_value=rich_result):
            r = client.get("/api/exceptions")
        report = r.json()["tier3_batch_report"]
        assert len(report) == 1
        for field in ("bank_ref", "category", "n_orders", "n_resolved", "n_excluded"):
            assert field in report[0]


# ---------------------------------------------------------------------------
# POST /api/exceptions/explain
# ---------------------------------------------------------------------------

class TestExplainEndpoint:
    def test_returns_200_with_valid_category(self, client):
        r = client.post("/api/exceptions/explain", json={
            "detected_category": "fee_drift",
        })
        assert r.status_code == 200

    def test_response_schema(self, client):
        r = client.post("/api/exceptions/explain", json={
            "detected_category": "fee_drift",
        })
        body = r.json()
        for field in ("category", "explanation", "likely_cause",
                      "suggested_action", "confidence"):
            assert field in body

    def test_optional_fields_accepted(self, client):
        r = client.post("/api/exceptions/explain", json={
            "detected_category": "fee_drift",
            "order_id": "ord_123",
            "bank_ref": "UTR-9999",
            "bank_amount": 10000.0,
            "settled_sum": 9995.5,
            "diff": 4.5,
        })
        assert r.status_code == 200

    def test_all_optional_except_detected_category(self, client):
        """Sending only detected_category must succeed."""
        r = client.post("/api/exceptions/explain", json={
            "detected_category": "duplicate",
        })
        assert r.status_code == 200

    def test_missing_detected_category_returns_422(self, client):
        r = client.post("/api/exceptions/explain", json={})
        assert r.status_code == 422

    def test_fallback_for_all_valid_categories(self, client):
        for cat in ("fee_drift", "ambiguous_duplicate_ref", "unmatched",
                    "partial_refund", "duplicate"):
            r = client.post("/api/exceptions/explain", json={"detected_category": cat})
            assert r.status_code == 200, f"Failed for category: {cat}"

    def test_aliased_category_resolves(self, client):
        """llm_reasoner normalises category aliases."""
        r = client.post("/api/exceptions/explain", json={
            "detected_category": "duplicate_bank_row",  # alias for 'duplicate'
        })
        assert r.status_code == 200
        assert r.json()["category"] == "duplicate"


# ---------------------------------------------------------------------------
# Misc / edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_reconcile_default_data_dir(self, client, simple_result):
        with patch("backend.main._cached_pipeline", return_value=simple_result) as mock:
            client.post("/api/reconcile", json={})
            mock.assert_called_with("data")

    def test_transactions_invalid_status_returns_empty(self, client, simple_result):
        """An unknown status filter should return an empty item list, not an error."""
        with patch("backend.main._cached_pipeline", return_value=simple_result):
            r = client.get("/api/transactions?status=nonexistent_status")
        assert r.status_code == 200
        assert r.json()["items"] == []

    def test_transactions_total_reflects_all_statuses(self, client, rich_result):
        with patch("backend.main._cached_pipeline", return_value=rich_result):
            r_all = client.get("/api/transactions?page_size=500")
        assert r_all.json()["total"] == len(r_all.json()["items"])
