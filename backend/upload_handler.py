"""
upload_handler.py
------------------
Validates and persists a user-uploaded reconciliation dataset (bank
statement, Razorpay settlement, internal ledger) so it can be used as the
`data_dir` for the existing pipeline (backend/pipeline.py -> data_loader.py)
without any change to that pipeline.

Design notes:
  - This module is intentionally framework-agnostic: it takes raw bytes,
    not FastAPI's UploadFile, so it has no dependency on the web layer and
    can be unit-tested directly. backend/main.py is responsible for reading
    the UploadFile objects (`await file.read()`) and calling in here.
  - Original uploaded filenames are NEVER used to decide where/how a file
    is written. Each of the three slots (bank_statement, razorpay_settlement,
    internal_ledger) is written under its fixed, expected filename, matching
    exactly what backend/data_loader.py hardcodes. This avoids path traversal
    and guarantees the pipeline can always find the files it expects.
  - Every upload gets its own directory under data/uploads/<id>/, so the
    default demo dataset in data/ is never touched or overwritten, and
    concurrent/successive uploads never collide. This keeps the feature safe
    for a single-active-dataset demo deployment without needing a database.
  - Column validation here mirrors the columns actually consumed across the
    existing pipeline (data_loader.py's parsing + the matcher/categorizer
    stages that read order_id, bank_ref, utr, etc.), not just the handful of
    columns data_loader.py itself casts. Catching a missing column here, at
    upload time, is a clear 400 to the user instead of an opaque KeyError
    deep inside the matching tiers.
"""

from __future__ import annotations

import io
import uuid
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Fixed configuration
# ---------------------------------------------------------------------------

# Root directory for all uploaded datasets. Kept separate from data/ (the
# bundled demo dataset) so uploads can never overwrite it.
UPLOAD_ROOT = "data/uploads"

# Fixed on-disk filenames — these must match backend/data_loader.py exactly.
# The uploaded file's original name is never used for this.
BANK_STATEMENT_FILENAME = "bank_statement.csv"
RAZORPAY_SETTLEMENT_FILENAME = "razorpay_settlement.csv"
INTERNAL_LEDGER_FILENAME = "internal_ledger.csv"

# Required columns per file, based on what data_loader.py and the downstream
# matcher/categorizer stages read from each CSV.
REQUIRED_COLUMNS = {
    BANK_STATEMENT_FILENAME: {
        "txn_date", "narration", "amount", "bank_ref",
    },
    RAZORPAY_SETTLEMENT_FILENAME: {
        "settlement_id", "order_id", "gross_amount", "fee",
        "tax_on_fee", "net_amount", "settled_at", "utr",
    },
    INTERNAL_LEDGER_FILENAME: {
        "invoice_id", "order_id", "invoice_amount", "customer",
        "status", "created_at",
    },
}


class UploadValidationError(ValueError):
    """Raised when an uploaded file fails CSV/schema validation.

    backend/main.py should catch this and translate it into an HTTP 400
    with `str(error)` as the detail message.
    """


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_csv(filename: str, content: bytes) -> None:
    """Ensure `content` is a parseable, non-empty CSV with the required
    columns for `filename`. Raises UploadValidationError otherwise."""
    if not content or not content.strip():
        raise UploadValidationError(f"{filename}: uploaded file is empty.")

    try:
        df = pd.read_csv(io.BytesIO(content))
    except pd.errors.EmptyDataError:
        raise UploadValidationError(f"{filename}: file has no columns or rows.")
    except pd.errors.ParserError as exc:
        raise UploadValidationError(f"{filename}: not a valid CSV ({exc}).")
    except UnicodeDecodeError:
        raise UploadValidationError(f"{filename}: file is not valid UTF-8 text/CSV.")

    if df.empty:
        raise UploadValidationError(f"{filename}: CSV has no data rows.")

    required = REQUIRED_COLUMNS[filename]
    missing = required - set(df.columns)
    if missing:
        raise UploadValidationError(
            f"{filename}: missing required column(s): {', '.join(sorted(missing))}"
        )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_uploaded_dataset(
    bank_statement: bytes,
    razorpay_settlement: bytes,
    internal_ledger: bytes,
    upload_root: str = UPLOAD_ROOT,
) -> str:
    """Validate the three uploaded CSVs and persist them under a new unique
    directory, using the exact filenames the pipeline expects.

    Args:
        bank_statement: raw bytes of the uploaded bank statement CSV.
        razorpay_settlement: raw bytes of the uploaded settlement CSV.
        internal_ledger: raw bytes of the uploaded ledger CSV.
        upload_root: base directory uploads are written under (override
            only used by tests).

    Returns:
        The new data_dir path (e.g. "data/uploads/3f9a1b2c..."), suitable
        for passing straight into backend/pipeline.py::run_pipeline() and
        for returning to the frontend as `data_dir`.

    Raises:
        UploadValidationError: if any of the three files is not a valid
            CSV or is missing required columns. Nothing is written to disk
            if any file fails validation.
    """
    # Validate all three before writing anything, so a bad file never
    # leaves a partially-written dataset directory behind.
    _validate_csv(BANK_STATEMENT_FILENAME, bank_statement)
    _validate_csv(RAZORPAY_SETTLEMENT_FILENAME, razorpay_settlement)
    _validate_csv(INTERNAL_LEDGER_FILENAME, internal_ledger)

    dataset_id = uuid.uuid4().hex
    target_dir = Path(upload_root) / dataset_id
    target_dir.mkdir(parents=True, exist_ok=True)

    (target_dir / BANK_STATEMENT_FILENAME).write_bytes(bank_statement)
    (target_dir / RAZORPAY_SETTLEMENT_FILENAME).write_bytes(razorpay_settlement)
    (target_dir / INTERNAL_LEDGER_FILENAME).write_bytes(internal_ledger)

    # Use forward slashes explicitly (rather than str(target_dir)) so the
    # returned data_dir is stable across OSes and safe to use directly in
    # data_loader.py's f"{data_dir}/bank_statement.csv" string formatting.
    return target_dir.as_posix()