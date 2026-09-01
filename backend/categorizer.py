"""
categorizer.py
---------------
Tier 3: batch decomposition.

Tier 1 and Tier 2 correctly identify WHICH settlement batches don't
cleanly match a bank row, but a batch is evaluated as all-or-nothing --
one problem order (or a few rupees of aggregate drift) fails the entire
batch, which drags down every genuinely clean order sharing that bank_ref
with it. Measured against ground_truth.csv, this cascade accounted for 52
of 58 order-level false negatives: individually-clean orders wrongly
marked unreconciled purely because of who they were batched with.

This stage re-examines each unresolved batch and asks a narrower
question per batch, in this order:

1. Was the mismatch caused by a duplicate bank posting we already
   flagged? If so, re-check the batch's settled sum against the *real*
   (non-duplicate) bank amount -- once bank_ref_count is 1 rather than 2,
   the batch usually clears cleanly.
2. Is the residual gap explainable as GST/fee rounding drift (small,
   proportionally tiny)? If so, accept the whole batch -- the drift is
   immaterial and doesn't implicate any specific order.
3. Otherwise: does excluding some SMALL subset of the batch's own orders
   make the rest sum to the bank amount? If so, recover the excluded
   subset as resolved and report the excluded order(s) as a targeted,
   order-level exception -- instead of failing all N orders in the batch.
4. If nothing above resolves it, the batch stays genuinely unresolved and
   every order in it is reported as an exception. This is the honest
   floor: not everything should resolve, and pretending otherwise would
   just move the false-negative problem into a false-positive problem.

Every resolution here is visible in `batch_report` with its category and
the residual diff, and every order pulled OUT of a batch is named
individually in `order_exceptions` with a reason -- nothing is silently
absorbed.
"""

from dataclasses import dataclass, field

import pandas as pd

from backend.matcher.exact import EXACT_AMOUNT_TOLERANCE
from backend.matcher.fuzzy_batch import (
    DRIFT_ABSOLUTE_CAP,
    DRIFT_RELATIVE_TOLERANCE,
    _search_subset,
)


@dataclass
class _BatchResolution:
    category: str
    resolved_order_ids: list
    excluded_order_ids: list
    diff: float


@dataclass
class CategorizationResult:
    resolved_order_ids: set
    order_exceptions: pd.DataFrame   # order_id, bank_ref, category, reason
    batch_report: pd.DataFrame       # bank_ref, category, n_orders, n_resolved, n_excluded, diff


def _resolve_batch(order_ids, amounts, target_amount) -> _BatchResolution:
    settled_sum = round(sum(amounts), 2)
    diff = round(target_amount - settled_sum, 2)

    if abs(diff) <= EXACT_AMOUNT_TOLERANCE:
        return _BatchResolution("exact_after_dedup", list(order_ids), [], diff)

    rel = abs(diff) / settled_sum if settled_sum else 1.0
    if abs(diff) <= DRIFT_ABSOLUTE_CAP and rel <= DRIFT_RELATIVE_TOLERANCE:
        return _BatchResolution("fee_drift_accepted", list(order_ids), [], diff)

    # Bounded to this batch's own orders -- batches are capped at ~15 by
    # construction, so this reuses the same bounded subset-sum search as
    # Tier 2's cross-source fallback, just scoped to "which of THIS
    # batch's orders belong" rather than "which orders form a batch at all".
    found = _search_subset(list(amounts), list(order_ids), target_amount, tolerance=EXACT_AMOUNT_TOLERANCE)
    if found is None:
        return _BatchResolution("unresolved", [], list(order_ids), diff)

    matched_ids, matched_sum = found
    if set(matched_ids) == set(order_ids):
        # shouldn't normally happen (would have cleared Tier 1 / the exact
        # check above), but handle it rather than assume it can't occur
        return _BatchResolution("exact_after_dedup", list(order_ids), [], round(target_amount - matched_sum, 2))

    excluded_ids = [oid for oid in order_ids if oid not in matched_ids]
    return _BatchResolution(
        "partial_exclusion_resolved", matched_ids, excluded_ids, round(target_amount - matched_sum, 2)
    )


def categorize(result) -> CategorizationResult:
    settlement = result.settlement
    bank = result.bank
    drift_classified = result.drift_classified

    if drift_classified.empty:
        return CategorizationResult(
            resolved_order_ids=set(),
            order_exceptions=pd.DataFrame(columns=["order_id", "bank_ref", "category", "reason"]),
            batch_report=pd.DataFrame(columns=["bank_ref", "category", "n_orders", "n_resolved",
                                                "n_excluded", "diff"]),
        )

    duplicate_ids_by_ref = {}
    for bank_ref, group in result.duplicates.groupby("bank_ref"):
        duplicate_ids_by_ref[bank_ref] = set(group["bank_row_id"])

    resolved_order_ids = set()
    order_exceptions = []
    batch_report = []

    problem_bank_refs = drift_classified["bank_ref"].unique()

    for bank_ref in problem_bank_refs:
        batch_settlement = settlement[settlement["utr"] == bank_ref]
        order_ids = list(batch_settlement["order_id"])
        amounts = list(batch_settlement["net_amount"])

        bank_rows_for_ref = bank[bank["bank_ref"] == bank_ref]
        dup_ids = duplicate_ids_by_ref.get(bank_ref, set())
        real_bank_rows = bank_rows_for_ref[~bank_rows_for_ref["bank_row_id"].isin(dup_ids)]
        is_duplicate_case = len(bank_rows_for_ref) > 1

        if len(real_bank_rows) != 1:
            # 0 or >1 candidates left after removing flagged duplicates --
            # genuinely ambiguous, don't guess. Defensive fallback; not
            # expected to trigger given how detect_duplicate_bank_rows works.
            batch_report.append({
                "bank_ref": bank_ref, "category": "unresolved_ambiguous_bank_rows",
                "n_orders": len(order_ids), "n_resolved": 0, "n_excluded": len(order_ids),
                "diff": None,
            })
            for oid in order_ids:
                order_exceptions.append({
                    "order_id": oid, "bank_ref": bank_ref,
                    "category": "unresolved_ambiguous_bank_rows",
                    "reason": "Could not identify a single unambiguous bank row for this "
                              "batch's reference even after duplicate resolution.",
                })
            continue

        target_amount = real_bank_rows.iloc[0]["amount"]
        resolution = _resolve_batch(order_ids, amounts, target_amount)

        category = resolution.category
        if is_duplicate_case and category != "unresolved":
            category = f"duplicate_{category}"

        resolved_order_ids.update(resolution.resolved_order_ids)

        for oid in resolution.excluded_order_ids:
            if category.startswith("duplicate_") or category == "partial_exclusion_resolved":
                reason = (
                    f"Excluded so the remaining {len(resolution.resolved_order_ids)} order(s) in "
                    f"batch {bank_ref} sum to the bank amount within tolerance; this order's own "
                    f"net_amount doesn't fit the batch total."
                )
            else:
                reason = (
                    f"Batch {bank_ref} could not be reconciled by any means -- no duplicate "
                    f"explanation, drift too large, and no subset of its orders sums to the "
                    f"bank amount within tolerance."
                )
            order_exceptions.append({
                "order_id": oid, "bank_ref": bank_ref, "category": category, "reason": reason,
            })

        batch_report.append({
            "bank_ref": bank_ref,
            "category": category,
            "n_orders": len(order_ids),
            "n_resolved": len(resolution.resolved_order_ids),
            "n_excluded": len(resolution.excluded_order_ids),
            "diff": resolution.diff,
        })

    return CategorizationResult(
        resolved_order_ids=resolved_order_ids,
        order_exceptions=pd.DataFrame(order_exceptions, columns=["order_id", "bank_ref", "category", "reason"]),
        batch_report=pd.DataFrame(batch_report, columns=["bank_ref", "category", "n_orders",
                                                            "n_resolved", "n_excluded", "diff"]),
    )


def total_reconciled_order_ids(result, cat_result: CategorizationResult) -> set:
    """The full picture: Tier 1's cleanly-matched orders, plus whatever
    Tier 3 recovered from otherwise-failing batches."""
    return result.reconciled_order_ids() | cat_result.resolved_order_ids
