"""
fuzzy_batch.py
--------------
Tier 2 of the matching pipeline: handles everything Tier 1's strict exact
match correctly refused to resolve. Three separate jobs, kept separate on
purpose so each one is auditable on its own:

1. detect_duplicate_bank_rows   -- flags bank rows that look like an
                                    erroneous duplicate posting.
2. classify_amount_drift        -- for batches whose sum was close but not
                                    exact, decides whether the gap looks
                                    like GST/fee rounding drift (small,
                                    proportionally tiny) vs. something that
                                    needs a human or the LLM layer.
3. subset_sum_match             -- a bounded subset-sum search that groups
                                    settlement rows into whatever bank
                                    amount they should sum to, for the case
                                    where you can't rely on a shared key
                                    (e.g. bank data doesn't carry the UTR
                                    reliably, or a bank_ref is ambiguous
                                    because of a duplicate). Capped at 15
                                    items -- unrestricted subset-sum is
                                    exponential, and no real settlement
                                    batch in this business is larger than
                                    that.

Nothing here silently resolves an ambiguity with high confidence. Every
function returns a confidence level so the categorizer (next stage) can
decide what's safe to auto-close vs. what belongs in the exception list.
"""

import warnings
from itertools import combinations
from dataclasses import dataclass
from datetime import timedelta

import pandas as pd

DRIFT_RELATIVE_TOLERANCE = 0.01   # 1% of batch value
DRIFT_ABSOLUTE_CAP = 50.0         # never call something "drift" above ₹50 regardless of %
SUBSET_SUM_TOLERANCE = 0.02       # ₹0.02
SUBSET_SUM_MAX_ITEMS = 15
SUBSET_SUM_DATE_WINDOW_DAYS = 5


def detect_duplicate_bank_rows(bank: pd.DataFrame) -> pd.DataFrame:
    """Flags bank rows sharing (bank_ref, amount) more than once.
    Returns one row per *extra* occurrence, marked as a likely duplicate,
    keeping the first occurrence as the presumed-real posting.

    This is deliberately a flag, not a silent drop -- an actual duplicate
    bank credit is something a finance controller needs to see and confirm,
    not something software should delete on their behalf.
    """
    dupe_groups = bank.groupby(["bank_ref", "amount"])
    flagged = []
    for (bank_ref, amount), group in dupe_groups:
        if len(group) > 1:
            group_sorted = group.sort_values("bank_row_id")
            kept = group_sorted.iloc[0]
            extras = group_sorted.iloc[1:]
            for _, row in extras.iterrows():
                flagged.append({
                    "bank_row_id": row["bank_row_id"],
                    "bank_ref": bank_ref,
                    "amount": amount,
                    "txn_date": row["txn_date"],
                    "narration": row["narration"],
                    "presumed_original_bank_row_id": kept["bank_row_id"],
                    "category": "duplicate_bank_row",
                    "confidence": "high",
                })
    return pd.DataFrame(flagged, columns=[
        "bank_row_id", "bank_ref", "amount", "txn_date", "narration",
        "presumed_original_bank_row_id", "category", "confidence",
    ])


def classify_amount_drift(unmatched_batches: pd.DataFrame) -> pd.DataFrame:
    """Takes Tier 1's leftover unmatched batches (bank amount vs settled
    sum didn't line up exactly) and separates likely rounding/fee drift
    from gaps too large to wave through.

    - Batches flagged as duplicate bank_ref (bank_ref_count > 1) are left
      alone here -- that's detect_duplicate_bank_rows' job, not this one's.
    - Everything else gets a category + confidence, never an auto-match.
    """
    if unmatched_batches.empty:
        return unmatched_batches.assign(category=[], confidence=[])

    out = unmatched_batches.copy()

    def classify(row):
        if row["bank_ref_count"] > 1:
            return "ambiguous_duplicate_ref", "low"
        rel = abs(row["diff"]) / row["settled_sum"] if row["settled_sum"] else 1.0
        if abs(row["diff"]) <= DRIFT_ABSOLUTE_CAP and rel <= DRIFT_RELATIVE_TOLERANCE:
            return "fee_drift", "medium"
        return "unresolved_amount_gap", "low"

    out[["category", "confidence"]] = out.apply(
        lambda r: pd.Series(classify(r)), axis=1
    )
    return out


@dataclass
class SubsetSumMatch:
    bank_row_id: int
    matched_order_ids: list
    matched_sum: float
    bank_amount: float
    diff: float


def subset_sum_match(settlement: pd.DataFrame, bank_rows: pd.DataFrame,
                      tolerance: float = SUBSET_SUM_TOLERANCE,
                      max_items: int = SUBSET_SUM_MAX_ITEMS,
                      date_window_days: int = SUBSET_SUM_DATE_WINDOW_DAYS):
    """For each unmatched bank row, search unmatched settlement rows within
    a date window for a subset whose net_amount sums to the bank amount
    within `tolerance`.

    This is the fallback for when you can't rely on a shared key (utr) --
    e.g. bank data that doesn't reliably carry the gateway's reference, or
    a bank_ref that's ambiguous because of a duplicate posting. Bounded to
    `max_items` candidates per search: unrestricted subset-sum is
    exponential (2^n), and real settlement batches at this business size
    don't exceed ~15 orders, so this is a deliberate, documented trade-off
    rather than an oversight.

    KNOWN LIMITATION: if more than `max_items` settlement rows fall inside
    the date window, we can only search a subset of them, which can miss a
    valid match whose components got excluded. We reduce (not eliminate)
    this risk by keeping the `max_items` candidates closest in time to the
    bank posting date, on the reasoning that a batch is more likely to be
    made of the settlements nearest the payout date than ones at the edge
    of the window -- but this is a heuristic, not a guarantee. A caller is
    warned (via `warnings.warn`) whenever truncation actually happens, so
    it's visible rather than silent. For a business with settlement
    batches routinely larger than ~15 orders, this should be replaced with
    a proper bounded dynamic-programming subset-sum (index sums by rounded
    paise value) or a meet-in-the-middle search, both of which scale to
    much larger n without the exponential blowup -- left as a follow-up
    since it wasn't needed to pass this dataset's actual batch sizes.

    Returns a list of SubsetSumMatch for bank rows where a candidate subset
    was found, and leaves everything else for the LLM reasoning layer.
    """
    results = []
    if bank_rows.empty or settlement.empty:
        return results

    for _, bank_row in bank_rows.iterrows():
        window_start = bank_row["txn_date"] - timedelta(days=date_window_days)
        window_end = bank_row["txn_date"] + timedelta(days=date_window_days)
        candidates = settlement[
            (settlement["settled_at"] >= window_start) & (settlement["settled_at"] <= window_end)
        ].copy()

        if candidates.empty:
            continue

        if len(candidates) > max_items:
            warnings.warn(
                f"subset_sum_match: bank_row_id={bank_row['bank_row_id']} has "
                f"{len(candidates)} candidate settlement rows in its date window, "
                f"more than max_items={max_items}. Keeping the {max_items} closest "
                f"by date to the bank posting -- a valid match could still be missed "
                f"if it relies on an excluded row. See KNOWN LIMITATION in "
                f"subset_sum_match's docstring.",
                stacklevel=2,
            )
            candidates["_date_distance"] = (candidates["settled_at"] - bank_row["txn_date"]).abs()
            candidates = candidates.sort_values("_date_distance").head(max_items)

        amounts = candidates["net_amount"].tolist()
        order_ids = candidates["order_id"].tolist()
        target = bank_row["amount"]

        found = _search_subset(amounts, order_ids, target, tolerance)
        if found is not None:
            matched_ids, matched_sum = found
            results.append(SubsetSumMatch(
                bank_row_id=bank_row["bank_row_id"],
                matched_order_ids=matched_ids,
                matched_sum=round(matched_sum, 2),
                bank_amount=target,
                diff=round(target - matched_sum, 2),
            ))

    return results


def _search_subset(amounts, order_ids, target, tolerance):
    """Bounded brute-force subset-sum over <= SUBSET_SUM_MAX_ITEMS amounts.
    2^15 = 32,768 combinations worst case -- trivial at this size.
    Returns (matched_order_ids, matched_sum) for the first subset found
    within tolerance, preferring smaller subsets (checked in size order).
    """
    n = len(amounts)
    for size in range(1, n + 1):
        for combo in combinations(range(n), size):
            s = round(sum(amounts[i] for i in combo), 2)
            if abs(s - target) <= tolerance:
                return [order_ids[i] for i in combo], s
    return None
