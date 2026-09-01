import pandas as pd
from backend.matcher.fuzzy_batch import (
    detect_duplicate_bank_rows,
    classify_amount_drift,
    subset_sum_match,
    _search_subset,
)


def _bank_row(bank_ref, amount, bank_row_id, txn_date="2026-08-03"):
    return {"bank_row_id": bank_row_id, "bank_ref": bank_ref, "amount": amount,
            "txn_date": pd.Timestamp(txn_date), "narration": "RAZORPAY SETTLE"}


def test_detect_duplicate_bank_rows_flags_only_extras():
    bank = pd.DataFrame([
        _bank_row("UTR-1", 100.0, 0),
        _bank_row("UTR-1", 100.0, 1),   # duplicate of row 0
        _bank_row("UTR-2", 200.0, 2),   # unrelated, not a duplicate
    ])

    flagged = detect_duplicate_bank_rows(bank)

    assert len(flagged) == 1
    assert flagged.iloc[0]["bank_row_id"] == 1
    assert flagged.iloc[0]["presumed_original_bank_row_id"] == 0
    assert flagged.iloc[0]["category"] == "duplicate_bank_row"


def test_detect_duplicate_bank_rows_no_false_positives_on_same_amount_different_ref():
    """Two different batches that happen to settle for the same rupee
    amount are NOT duplicates -- they have different bank_ref/UTR."""
    bank = pd.DataFrame([
        _bank_row("UTR-1", 500.0, 0),
        _bank_row("UTR-2", 500.0, 1),
    ])

    flagged = detect_duplicate_bank_rows(bank)

    assert flagged.empty


def test_classify_amount_drift_small_gap_is_fee_drift():
    unmatched = pd.DataFrame([{
        "bank_ref": "UTR-1", "bank_row_id": 0, "settled_sum": 10000.0,
        "amount": 10012.0, "diff": 12.0, "bank_ref_count": 1,
        "txn_date": pd.Timestamp("2026-08-03"), "narration": "x",
    }])

    out = classify_amount_drift(unmatched)

    assert out.iloc[0]["category"] == "fee_drift"
    assert out.iloc[0]["confidence"] == "medium"


def test_classify_amount_drift_large_gap_is_unresolved():
    unmatched = pd.DataFrame([{
        "bank_ref": "UTR-1", "bank_row_id": 0, "settled_sum": 10000.0,
        "amount": 8000.0, "diff": -2000.0, "bank_ref_count": 1,
        "txn_date": pd.Timestamp("2026-08-03"), "narration": "x",
    }])

    out = classify_amount_drift(unmatched)

    assert out.iloc[0]["category"] == "unresolved_amount_gap"


def test_classify_amount_drift_duplicate_ref_left_ambiguous():
    unmatched = pd.DataFrame([{
        "bank_ref": "UTR-1", "bank_row_id": 0, "settled_sum": 100.0,
        "amount": 100.0, "diff": 0.0, "bank_ref_count": 2,
        "txn_date": pd.Timestamp("2026-08-03"), "narration": "x",
    }])

    out = classify_amount_drift(unmatched)

    assert out.iloc[0]["category"] == "ambiguous_duplicate_ref"


def test_search_subset_finds_exact_combination():
    amounts = [100.0, 250.0, 75.0, 40.0]
    order_ids = ["o1", "o2", "o3", "o4"]

    result = _search_subset(amounts, order_ids, target=175.0, tolerance=0.02)

    assert result is not None
    matched_ids, matched_sum = result
    assert set(matched_ids) == {"o1", "o3"}
    assert matched_sum == 175.0


def test_search_subset_returns_none_when_no_combination_fits():
    amounts = [100.0, 250.0]
    order_ids = ["o1", "o2"]

    result = _search_subset(amounts, order_ids, target=999.0, tolerance=0.02)

    assert result is None


def test_subset_sum_match_end_to_end_within_date_window():
    settlement = pd.DataFrame([
        {"order_id": "o1", "net_amount": 300.0, "settled_at": pd.Timestamp("2026-08-01")},
        {"order_id": "o2", "net_amount": 450.0, "settled_at": pd.Timestamp("2026-08-02")},
        {"order_id": "o3", "net_amount": 999.0, "settled_at": pd.Timestamp("2026-08-01")},
    ])
    bank_rows = pd.DataFrame([_bank_row("UTR-X", 750.0, bank_row_id=5, txn_date="2026-08-03")])

    results = subset_sum_match(settlement, bank_rows, date_window_days=5)

    assert len(results) == 1
    assert set(results[0].matched_order_ids) == {"o1", "o2"}
    assert results[0].matched_sum == 750.0


def test_subset_sum_match_warns_and_still_finds_match_when_over_max_items():
    """With more than max_items candidates in the window, we should still
    find a valid match if its components are among the closest-by-date
    candidates, and the caller should be warned that truncation happened."""
    settlement_rows = [
        {"order_id": f"noise_{i}", "net_amount": 10.0 + i,
         "settled_at": pd.Timestamp("2026-08-01") + pd.Timedelta(days=i)}
        for i in range(10)
    ]
    # the true match: two rows closest to the bank txn_date (day 3 and 4)
    settlement_rows += [
        {"order_id": "real_1", "net_amount": 300.0, "settled_at": pd.Timestamp("2026-08-04")},
        {"order_id": "real_2", "net_amount": 450.0, "settled_at": pd.Timestamp("2026-08-05")},
    ]
    settlement = pd.DataFrame(settlement_rows)
    bank_rows = pd.DataFrame([_bank_row("UTR-X", 750.0, bank_row_id=9, txn_date="2026-08-05")])

    import warnings
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        results = subset_sum_match(settlement, bank_rows, date_window_days=10, max_items=5)

    assert any("more than max_items" in str(w.message) for w in caught)
    assert len(results) == 1
    assert set(results[0].matched_order_ids) == {"real_1", "real_2"}


def test_subset_sum_match_respects_date_window():
    """A settlement row far outside the date window must not be pulled
    into a match even if the amount would fit."""
    settlement = pd.DataFrame([
        {"order_id": "o1", "net_amount": 750.0, "settled_at": pd.Timestamp("2026-01-01")},
    ])
    bank_rows = pd.DataFrame([_bank_row("UTR-X", 750.0, bank_row_id=5, txn_date="2026-08-03")])

    results = subset_sum_match(settlement, bank_rows, date_window_days=5)

    assert results == []
