import pandas as pd
from backend.matcher.exact import match_ledger_settlement, match_settlement_bank


def _ledger_row(order_id, amount, invoice_id="INV-1"):
    return {"order_id": order_id, "invoice_id": invoice_id, "invoice_amount": amount,
            "customer": "Acme", "status": "closed", "created_at": pd.Timestamp("2026-08-01")}


def _settlement_row(order_id, net_amount, utr, settlement_id="stl_1"):
    return {"settlement_id": settlement_id, "payment_id": f"pay_{order_id}", "order_id": order_id,
            "gross_amount": net_amount + 10, "fee": 8, "tax_on_fee": 2, "net_amount": net_amount,
            "settled_at": pd.Timestamp("2026-08-02"), "utr": utr}


def _bank_row(bank_ref, amount, bank_row_id=0):
    return {"txn_date": pd.Timestamp("2026-08-03"), "narration": "RAZORPAY SETTLE",
            "amount": amount, "bank_ref": bank_ref, "batch_notes": "", "bank_row_id": bank_row_id}


def test_ledger_settlement_clean_match():
    ledger = pd.DataFrame([_ledger_row("order_1", 100.0)])
    settlement = pd.DataFrame([_settlement_row("order_1", 90.0, "UTR-1")])

    result = match_ledger_settlement(ledger, settlement)

    assert len(result.matched) == 1
    assert result.orphan_ledger.empty
    assert result.orphan_settlement.empty


def test_ledger_settlement_orphan_ledger():
    """An invoice exists but the order was never settled -- must NOT be
    silently dropped, it must show up as an orphan_ledger row."""
    ledger = pd.DataFrame([_ledger_row("order_1", 100.0)])
    settlement = pd.DataFrame(columns=["order_id", "settlement_id", "payment_id",
                                        "gross_amount", "fee", "tax_on_fee",
                                        "net_amount", "settled_at", "utr"])

    result = match_ledger_settlement(ledger, settlement)

    assert result.matched.empty
    assert len(result.orphan_ledger) == 1
    assert result.orphan_ledger.iloc[0]["order_id"] == "order_1"


def test_ledger_settlement_orphan_settlement():
    """A settlement/payment happened but no invoice was ever raised."""
    ledger = pd.DataFrame(columns=["order_id", "invoice_id", "invoice_amount",
                                    "customer", "status", "created_at"])
    settlement = pd.DataFrame([_settlement_row("order_1", 90.0, "UTR-1")])

    result = match_ledger_settlement(ledger, settlement)

    assert result.matched.empty
    assert len(result.orphan_settlement) == 1
    assert result.orphan_settlement.iloc[0]["order_id"] == "order_1"


def test_settlement_bank_clean_batch_match():
    """Two orders settle together into one bank line -- the classic
    many-to-one batch case -- and should clear Tier 1 cleanly."""
    settlement = pd.DataFrame([
        _settlement_row("order_1", 100.0, "UTR-1"),
        _settlement_row("order_2", 200.0, "UTR-1"),
    ])
    bank = pd.DataFrame([_bank_row("UTR-1", 300.0, bank_row_id=0)])

    result = match_settlement_bank(settlement, bank)

    assert len(result.matched_batches) == 1
    assert result.matched_batches.iloc[0]["diff"] == 0.0
    assert result.unmatched_batches.empty


def test_settlement_bank_amount_mismatch_goes_to_tier2():
    """A batch whose bank total doesn't match the settled sum must NOT be
    silently accepted -- it belongs in unmatched_batches for Tier 2."""
    settlement = pd.DataFrame([_settlement_row("order_1", 100.0, "UTR-1")])
    bank = pd.DataFrame([_bank_row("UTR-1", 117.0, bank_row_id=0)])  # off by 17

    result = match_settlement_bank(settlement, bank)

    assert result.matched_batches.empty
    assert len(result.unmatched_batches) == 1
    assert result.unmatched_batches.iloc[0]["diff"] == 17.0


def test_settlement_bank_rounding_within_tolerance_still_matches():
    """A one-paise rounding difference should still clear Tier 1 -- this
    tier's tolerance is for float/paise noise only."""
    settlement = pd.DataFrame([_settlement_row("order_1", 100.005, "UTR-1")])
    bank = pd.DataFrame([_bank_row("UTR-1", 100.0, bank_row_id=0)])

    result = match_settlement_bank(settlement, bank, tolerance=0.02)

    assert len(result.matched_batches) == 1


def test_settlement_bank_duplicate_ref_not_auto_matched():
    """Two bank rows sharing the same bank_ref (a possible duplicate
    posting) must never be silently auto-matched -- ambiguity here is a
    Tier 2 / exception-list concern, not something Tier 1 should guess at."""
    settlement = pd.DataFrame([_settlement_row("order_1", 100.0, "UTR-1")])
    bank = pd.DataFrame([
        _bank_row("UTR-1", 100.0, bank_row_id=0),
        _bank_row("UTR-1", 100.0, bank_row_id=1),
    ])

    result = match_settlement_bank(settlement, bank)

    assert result.matched_batches.empty
    assert len(result.unmatched_batches) == 2
    assert all(result.unmatched_batches["bank_ref_count"] == 2)


def test_settlement_bank_unmatched_bank_row_with_no_settlement():
    """A bank credit with a utr that never shows up in the settlement
    export at all -- e.g. a stray/manual bank entry -- should be returned
    as an unmatched bank row, not dropped."""
    settlement = pd.DataFrame([_settlement_row("order_1", 100.0, "UTR-1")])
    bank = pd.DataFrame([
        _bank_row("UTR-1", 100.0, bank_row_id=0),
        _bank_row("UTR-MYSTERY", 55.0, bank_row_id=1),
    ])

    result = match_settlement_bank(settlement, bank)

    assert len(result.matched_batches) == 1
    assert len(result.unmatched_bank_rows) == 1
    assert result.unmatched_bank_rows.iloc[0]["bank_ref"] == "UTR-MYSTERY"
