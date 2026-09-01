"""
data_loader.py
--------------
Loads and normalizes the three source CSVs so every downstream stage
(matching tiers, the categorizer, metrics, and the FastAPI layer) works
with consistent types (parsed dates, floats rounded to paise).

Lives at backend/ root rather than inside matcher/ because it's shared
infrastructure -- categorizer.py and metrics.py will need it too, not just
the matcher.

Deliberately does NOT deduplicate or "fix" anything here — normalization
should only change representation (types, whitespace), never decide what's
a duplicate or an error. That decision belongs to the matching tiers, where
it's visible and auditable.
"""

import pandas as pd


def load_data(data_dir: str = "data"):
    bank = pd.read_csv(f"{data_dir}/bank_statement.csv")
    settlement = pd.read_csv(f"{data_dir}/razorpay_settlement.csv")
    ledger = pd.read_csv(f"{data_dir}/internal_ledger.csv")

    bank["txn_date"] = pd.to_datetime(bank["txn_date"])
    bank["amount"] = bank["amount"].round(2)
    bank["narration"] = bank["narration"].astype(str).str.strip()

    settlement["settled_at"] = pd.to_datetime(settlement["settled_at"])
    for col in ["gross_amount", "fee", "tax_on_fee", "net_amount"]:
        settlement[col] = settlement[col].round(2)

    ledger["created_at"] = pd.to_datetime(ledger["created_at"])
    ledger["invoice_amount"] = ledger["invoice_amount"].round(2)
    ledger["customer"] = ledger["customer"].astype(str).str.strip()

    # bank rows get a stable row id up front -- duplicate rows will share
    # everything except this id, which is exactly how we detect them later.
    bank = bank.reset_index(drop=True)
    bank["bank_row_id"] = bank.index

    return bank, settlement, ledger
