"""
main.py
-------
FastAPI entry point for the Finance Controller reconciliation API.

Architecture: all reconciliation logic lives in pipeline.py, categorizer.py,
metrics.py, and llm_reasoner.py -- this file only routes HTTP requests to
the appropriate existing functions and serialises their results into JSON.

No reconciliation logic is duplicated here. Ground truth is never loaded by
this layer; precision/recall evaluation is a separate concern (evaluate.py).

Endpoints:
    POST /api/reconcile            — run the pipeline, return operational metrics
    GET  /api/transactions         — paginated transaction list with status labels
    GET  /api/exceptions           — exceptions broken down by tier/type
    POST /api/exceptions/explain   — LLM-powered exception explanation
    POST /api/upload               — upload a new reconciliation dataset
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any, Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.pipeline import run_pipeline, ReconciliationResult
from backend.categorizer import total_reconciled_order_ids
from backend.metrics import (
    reconciliation_rate as _reconciliation_rate,
    exception_counts as _exception_counts,
)
from backend.matcher.llm_reasoner import ExceptionContext, explain_exception
from backend.upload_handler import (
    UploadValidationError,
    save_uploaded_dataset,
)


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Finance Controller API",
    description="Reconciliation pipeline API for ledger, settlement, and bank matching.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tightened to the React dev-server origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pipeline result cache
# ---------------------------------------------------------------------------

@lru_cache(maxsize=8)
def _cached_pipeline(data_dir: str) -> ReconciliationResult:
    return run_pipeline(data_dir)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(v: Any) -> Optional[float]:
    """Return None for NaN/Inf so JSON serialisation never emits a bare NaN."""
    if v is None:
        return None

    try:
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _safe_str(v: Any) -> Optional[str]:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None

    s = str(v)
    return None if s in ("NaT", "nan", "None") else s


# ---------------------------------------------------------------------------
# Pydantic models — request bodies
# ---------------------------------------------------------------------------

class ReconcileRequest(BaseModel):
    data_dir: str = Field(
        "data",
        description="Path to the directory containing the CSV files.",
    )


class ExplainRequest(BaseModel):
    """Maps directly to llm_reasoner.ExceptionContext."""

    detected_category: str
    order_id: Optional[str] = None
    bank_ref: Optional[str] = None
    bank_amount: Optional[float] = None
    settled_sum: Optional[float] = None
    diff: Optional[float] = None
    invoice_amount: Optional[float] = None
    net_amount: Optional[float] = None
    narration: Optional[str] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Pydantic models — responses
# ---------------------------------------------------------------------------

class MetricsSummary(BaseModel):
    total_orders: int
    reconciled_orders: int
    unreconciled_orders: int
    reconciliation_rate: float
    exception_rate: float


class ExceptionCountsSummary(BaseModel):
    orphan_ledger: int
    orphan_settlement: int
    unmatched_batches: int
    duplicate_bank_rows: int
    drift_by_category: dict[str, int]
    subset_sum_matches: int
    tier3_batch_categories: dict[str, int]
    tier3_order_exceptions: int


class ReconcileResponse(BaseModel):
    metrics: MetricsSummary
    exception_counts: ExceptionCountsSummary


class TransactionItem(BaseModel):
    """Single order row.

    Fields that are not available for a given reconciliation status are
    explicitly None rather than omitted so the frontend always receives a
    consistent schema.
    """

    order_id: str

    reconciliation_status: str
    tier: Optional[str] = None

    # Ledger fields
    invoice_id: Optional[str] = None
    customer: Optional[str] = None
    invoice_amount: Optional[float] = None
    ledger_status: Optional[str] = None
    created_at: Optional[str] = None

    # Settlement fields
    settlement_id: Optional[str] = None
    net_amount: Optional[float] = None
    utr: Optional[str] = None

    # Exception fields
    category: Optional[str] = None
    reason: Optional[str] = None


class PaginatedTransactionsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[TransactionItem]


class DuplicateBankRow(BaseModel):
    bank_row_id: int
    bank_ref: str
    amount: float
    txn_date: Optional[str] = None
    narration: Optional[str] = None
    presumed_original_bank_row_id: int
    confidence: str


class DriftBatch(BaseModel):
    bank_ref: str
    bank_row_id: Optional[int] = None
    settled_sum: Optional[float] = None
    amount: Optional[float] = None
    diff: Optional[float] = None
    bank_ref_count: Optional[int] = None
    category: str
    confidence: str
    txn_date: Optional[str] = None
    narration: Optional[str] = None


class OrderException(BaseModel):
    order_id: str
    bank_ref: Optional[str] = None
    category: str
    reason: str


class BatchReportItem(BaseModel):
    bank_ref: str
    category: str
    n_orders: int
    n_resolved: int
    n_excluded: int
    diff: Optional[float] = None


class ExceptionsResponse(BaseModel):
    duplicate_bank_rows: list[DuplicateBankRow]
    drift_batches: list[DriftBatch]
    tier3_order_exceptions: list[OrderException]
    tier3_batch_report: list[BatchReportItem]


class ReasoningResponse(BaseModel):
    category: str
    explanation: str
    likely_cause: str
    suggested_action: str
    confidence: str


class UploadResponse(BaseModel):
    data_dir: str
    message: str


# ---------------------------------------------------------------------------
# Endpoint: POST /api/reconcile
# ---------------------------------------------------------------------------

@app.post(
    "/api/reconcile",
    response_model=ReconcileResponse,
    tags=["reconciliation"],
)
def reconcile(
    body: ReconcileRequest = ReconcileRequest(),
) -> ReconcileResponse:
    """Run the full reconciliation pipeline and return operational metrics."""
    result = _cached_pipeline(body.data_dir)

    m = _reconciliation_rate(result)
    ec = _exception_counts(result)

    return ReconcileResponse(
        metrics=MetricsSummary(
            total_orders=m.total_orders,
            reconciled_orders=m.reconciled_orders,
            unreconciled_orders=m.unreconciled_orders,
            reconciliation_rate=m.reconciliation_rate,
            exception_rate=m.exception_rate,
        ),
        exception_counts=ExceptionCountsSummary(
            orphan_ledger=ec.orphan_ledger,
            orphan_settlement=ec.orphan_settlement,
            unmatched_batches=ec.unmatched_batches,
            duplicate_bank_rows=ec.duplicate_bank_rows,
            drift_by_category=ec.drift_by_category,
            subset_sum_matches=ec.subset_sum_matches,
            tier3_batch_categories=ec.tier3_batch_categories,
            tier3_order_exceptions=ec.tier3_order_exceptions,
        ),
    )


# ---------------------------------------------------------------------------
# Endpoint: GET /api/transactions
# ---------------------------------------------------------------------------

@app.get(
    "/api/transactions",
    response_model=PaginatedTransactionsResponse,
    tags=["transactions"],
)
def get_transactions(
    status: str = Query(
        "all",
        description="all | reconciled | orphan_ledger | orphan_settlement | exception",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    data_dir: str = Query("data"),
) -> PaginatedTransactionsResponse:

    result = _cached_pipeline(data_dir)

    tier1_ids = result.reconciled_order_ids()
    cat_result = result.cat_result

    all_reconciled = (
        total_reconciled_order_ids(result, cat_result)
        if cat_result
        else tier1_ids
    )

    tier3_ids = all_reconciled - tier1_ids

    items: list[TransactionItem] = []

    # --- Reconciled ---
    if status in ("all", "reconciled"):
        matched = result.ls_result.matched

        for _, row in matched.iterrows():
            oid = row["order_id"]

            if oid not in all_reconciled:
                continue

            tier = "Tier 1 Exact" if oid in tier1_ids else "Tier 3 Recovered"
            recon_status = (
                "reconciled"
                if oid in tier1_ids
                else "tier3_recovered"
            )

            items.append(
                TransactionItem(
                    order_id=oid,
                    reconciliation_status=recon_status,
                    tier=tier,
                    invoice_id=_safe_str(row.get("invoice_id")),
                    customer=_safe_str(row.get("customer")),
                    invoice_amount=_safe_float(row.get("invoice_amount")),
                    ledger_status=_safe_str(row.get("status")),
                    created_at=_safe_str(row.get("created_at")),
                    settlement_id=_safe_str(row.get("settlement_id")),
                    net_amount=_safe_float(row.get("net_amount")),
                    utr=_safe_str(row.get("utr")),
                )
            )

    # --- Orphan Ledger ---
    if status in ("all", "orphan_ledger"):
        for _, row in result.ls_result.orphan_ledger.iterrows():
            items.append(
                TransactionItem(
                    order_id=str(row["order_id"]),
                    reconciliation_status="orphan_ledger",
                    tier=None,
                    invoice_id=_safe_str(row.get("invoice_id")),
                    customer=_safe_str(row.get("customer")),
                    invoice_amount=_safe_float(row.get("invoice_amount")),
                    ledger_status=_safe_str(row.get("status")),
                    created_at=_safe_str(row.get("created_at")),
                    net_amount=None,
                    utr=None,
                    settlement_id=None,
                )
            )

    # --- Orphan Settlement ---
    if status in ("all", "orphan_settlement"):
        for _, row in result.ls_result.orphan_settlement.iterrows():
            items.append(
                TransactionItem(
                    order_id=str(row["order_id"]),
                    reconciliation_status="orphan_settlement",
                    tier=None,
                    invoice_id=None,
                    customer=None,
                    invoice_amount=None,
                    ledger_status=None,
                    created_at=None,
                    settlement_id=_safe_str(row.get("settlement_id")),
                    net_amount=_safe_float(row.get("net_amount")),
                    utr=_safe_str(row.get("utr")),
                )
            )

    # --- Tier 3 Order Exceptions ---
    if status in ("all", "exception") and cat_result is not None:
        for _, row in cat_result.order_exceptions.iterrows():
            items.append(
                TransactionItem(
                    order_id=str(row["order_id"]),
                    reconciliation_status="exception",
                    tier="Tier 3 Exception",
                    utr=_safe_str(row.get("bank_ref")),
                    category=_safe_str(row.get("category")),
                    reason=_safe_str(row.get("reason")),
                )
            )

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size

    return PaginatedTransactionsResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items[start:end],
    )


# ---------------------------------------------------------------------------
# Endpoint: GET /api/exceptions
# ---------------------------------------------------------------------------

@app.get(
    "/api/exceptions",
    response_model=ExceptionsResponse,
    tags=["exceptions"],
)
def get_exceptions(
    data_dir: str = Query("data"),
) -> ExceptionsResponse:

    result = _cached_pipeline(data_dir)

    # Duplicate bank rows
    dup_rows: list[DuplicateBankRow] = []

    for _, row in result.duplicates.iterrows():
        dup_rows.append(
            DuplicateBankRow(
                bank_row_id=int(row["bank_row_id"]),
                bank_ref=str(row["bank_ref"]),
                amount=float(row["amount"]),
                txn_date=_safe_str(row.get("txn_date")),
                narration=_safe_str(row.get("narration")),
                presumed_original_bank_row_id=int(
                    row["presumed_original_bank_row_id"]
                ),
                confidence=str(row["confidence"]),
            )
        )

    # Drift batches
    drift_batches: list[DriftBatch] = []

    for _, row in result.drift_classified.iterrows():
        drift_batches.append(
            DriftBatch(
                bank_ref=str(row["bank_ref"]),
                bank_row_id=(
                    int(row["bank_row_id"])
                    if row.get("bank_row_id") is not None
                    else None
                ),
                settled_sum=_safe_float(row.get("settled_sum")),
                amount=_safe_float(row.get("amount")),
                diff=_safe_float(row.get("diff")),
                bank_ref_count=(
                    int(row["bank_ref_count"])
                    if row.get("bank_ref_count") is not None
                    else None
                ),
                category=str(row["category"]),
                confidence=str(row["confidence"]),
                txn_date=_safe_str(row.get("txn_date")),
                narration=_safe_str(row.get("narration")),
            )
        )

    # Tier 3 exceptions
    order_exceptions: list[OrderException] = []
    batch_report: list[BatchReportItem] = []

    cat_result = result.cat_result

    if cat_result is not None:

        for _, row in cat_result.order_exceptions.iterrows():
            order_exceptions.append(
                OrderException(
                    order_id=str(row["order_id"]),
                    bank_ref=_safe_str(row.get("bank_ref")),
                    category=str(row["category"]),
                    reason=str(row["reason"]),
                )
            )

        for _, row in cat_result.batch_report.iterrows():
            batch_report.append(
                BatchReportItem(
                    bank_ref=str(row["bank_ref"]),
                    category=str(row["category"]),
                    n_orders=int(row["n_orders"]),
                    n_resolved=int(row["n_resolved"]),
                    n_excluded=int(row["n_excluded"]),
                    diff=_safe_float(row.get("diff")),
                )
            )

    return ExceptionsResponse(
        duplicate_bank_rows=dup_rows,
        drift_batches=drift_batches,
        tier3_order_exceptions=order_exceptions,
        tier3_batch_report=batch_report,
    )


# ---------------------------------------------------------------------------
# Endpoint: POST /api/exceptions/explain
# ---------------------------------------------------------------------------

@app.post(
    "/api/exceptions/explain",
    response_model=ReasoningResponse,
    tags=["exceptions"],
)
def explain_exception_endpoint(
    body: ExplainRequest,
) -> ReasoningResponse:

    context = ExceptionContext(
        detected_category=body.detected_category,
        order_id=body.order_id,
        bank_ref=body.bank_ref,
        bank_amount=body.bank_amount,
        settled_sum=body.settled_sum,
        diff=body.diff,
        invoice_amount=body.invoice_amount,
        net_amount=body.net_amount,
        narration=body.narration,
        notes=body.notes,
    )

    reasoning = explain_exception(context)

    return ReasoningResponse(
        category=reasoning.category,
        explanation=reasoning.explanation,
        likely_cause=reasoning.likely_cause,
        suggested_action=reasoning.suggested_action,
        confidence=reasoning.confidence,
    )


# ---------------------------------------------------------------------------
# Endpoint: POST /api/upload
# ---------------------------------------------------------------------------

@app.post(
    "/api/upload",
    response_model=UploadResponse,
    tags=["dataset"],
)
async def upload_dataset(
    bank_statement: UploadFile = File(...),
    razorpay_settlement: UploadFile = File(...),
    internal_ledger: UploadFile = File(...),
) -> UploadResponse:
    """Validate and persist a new reconciliation dataset."""

    try:
        data_dir = save_uploaded_dataset(
            bank_statement=await bank_statement.read(),
            razorpay_settlement=await razorpay_settlement.read(),
            internal_ledger=await internal_ledger.read(),
        )

    except UploadValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    return UploadResponse(
        data_dir=data_dir,
        message="Dataset uploaded successfully.",
    )