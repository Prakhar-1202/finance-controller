"""
generate_data.py
-----------------
Synthetic data generator for the AI Finance Controller reconciliation agent.

Produces three CSVs that mimic the three "versions of the truth" a finance
team has to reconcile every settlement cycle:

    bank_statement.csv       -> what actually hit the bank account
    razorpay_settlement.csv  -> what the gateway says it paid out (per order)
    internal_ledger.csv      -> what the business thinks it's owed (per invoice)

It also writes ground_truth.csv, a held-out label file that is NOT used by
the matching engine. Use it only to measure precision/recall after the
matcher has run — labelling ground truth up front (before building the
matcher) avoids unconsciously tuning your matching thresholds to your own
answer key.

Design: orders are grouped into "settlement batches" (a day's payout).
Each batch produces one bank_statement row (the net sum of the batch) and
one razorpay_settlement row per order in the batch. On top of this clean
structure we inject deliberate messiness so the matching engine has real
work to do:

    - partial_refund     : settlement net_amount reduced by a refund, ledger
                            invoice_amount left at the original value
    - duplicate_bank_row  : a bank statement line is duplicated (bank-side
                            glitch) -> must be flagged, not double-counted
    - fee_drift           : a batch's bank amount is off by a few rupees/paise
                            from the sum of settlement net_amounts (GST
                            rounding-style drift)
    - orphan_ledger       : an invoice exists with no matching settlement or
                            bank entry at all (payment never came)
    - orphan_settlement   : a settlement/payment happened but no invoice was
                            ever raised in the ledger
    - delayed_settlement  : settled_at is far later than created_at, testing
                            whether the date-window matcher is wide enough

Usage:
    python generate_data.py --num-orders 220 --seed 42 --output-dir .
"""

import argparse
import csv
import random
import string
from datetime import timedelta

from faker import Faker

fake = Faker("en_IN")

CASE_TYPES = [
    "clean",
    "partial_refund",
    "orphan_ledger",
    "orphan_settlement",
    "delayed_settlement",
]
# Weights sum to 1.0 across the "per-order" case types.
# duplicate_bank_row and fee_drift are applied afterwards, at the batch level.
CASE_WEIGHTS = [0.68, 0.12, 0.10, 0.06, 0.04]

GST_RATE = 0.18


def rand_id(prefix: str, n: int = 10) -> str:
    chars = string.ascii_lowercase + string.digits
    return f"{prefix}_{''.join(random.choices(chars, k=n))}"


def make_order(order_num: int, base_date):
    """Create one order's underlying facts: amount, dates, customer, case type."""
    invoice_amount = round(random.choice(
        [random.uniform(300, 3000), random.uniform(3000, 25000), random.uniform(25000, 120000)]
    ), 2)
    created_at = base_date + timedelta(days=random.randint(0, 45))
    case_type = random.choices(CASE_TYPES, weights=CASE_WEIGHTS, k=1)[0]

    return {
        "order_id": rand_id("order"),
        "invoice_id": f"INV-{created_at.year}-{order_num:05d}",
        "customer": fake.company(),
        "invoice_amount": invoice_amount,
        "created_at": created_at,
        "case_type": case_type,
    }


def build_batches(orders, batch_size_range=(3, 15)):
    """Group orders into settlement batches. Orders in the same batch settle
    together and roll up into a single bank statement line."""
    batches = []
    i = 0
    orders_sorted = sorted(orders, key=lambda o: o["created_at"])
    while i < len(orders_sorted):
        size = random.randint(*batch_size_range)
        batch = orders_sorted[i:i + size]
        if batch:
            batches.append(batch)
        i += size
    return batches


def generate(num_orders: int, seed: int, output_dir: str, base_date_str: str):
    random.seed(seed)
    Faker.seed(seed)

    from datetime import date
    y, m, d = (int(x) for x in base_date_str.split("-"))
    base_date = date(y, m, d)

    orders = [make_order(i, base_date) for i in range(1, num_orders + 1)]
    batches = build_batches(orders)

    bank_rows = []
    settlement_rows = []
    ledger_rows = []
    ground_truth_rows = []

    for batch in batches:
        settlement_id = rand_id("stl", 9)
        # settlement typically lands 1-3 days after the latest order in the batch,
        # except delayed_settlement cases which stretch this window deliberately.
        latest_created = max(o["created_at"] for o in batch)
        normal_delay = random.randint(1, 3)
        settled_at = latest_created + timedelta(days=normal_delay)

        batch_net_total = 0.0
        bank_ref = f"UTR-{random.randint(10_000_000, 99_999_999)}"

        for o in batch:
            gross = o["invoice_amount"]
            fee = round(gross * random.uniform(0.018, 0.023), 2)  # ~2% gateway fee
            tax_on_fee = round(fee * GST_RATE, 2)
            net = round(gross - fee - tax_on_fee, 2)

            row_settled_at = settled_at
            expected_match = True
            notes = "clean"

            if o["case_type"] == "delayed_settlement":
                row_settled_at = latest_created + timedelta(days=random.randint(8, 20))
                notes = "delayed_settlement: settlement lands well outside a tight date window"

            elif o["case_type"] == "partial_refund":
                refund = round(gross * random.uniform(0.15, 0.6), 2)
                net = round(net - refund, 2)
                notes = f"partial_refund: refund of ~{refund} reduces net vs invoice_amount"

            elif o["case_type"] == "orphan_settlement":
                # settlement exists, but we will simply not write a ledger row for it
                notes = "orphan_settlement: no matching internal ledger invoice exists"

            elif o["case_type"] == "orphan_ledger":
                # ledger row exists, but we skip writing settlement/bank rows for it
                ground_truth_rows.append({
                    "order_id": o["order_id"],
                    "invoice_id": o["invoice_id"],
                    "case_type": "orphan_ledger",
                    "expected_match": False,
                    "expected_category": "orphan_ledger",
                    "notes": "orphan_ledger: payment never received, invoice raised only",
                })
                ledger_rows.append({
                    "invoice_id": o["invoice_id"],
                    "order_id": o["order_id"],
                    "invoice_amount": gross,
                    "customer": o["customer"],
                    "status": "open",
                    "created_at": o["created_at"],
                })
                continue  # no settlement / bank row for this order

            # write settlement row (covers clean, partial_refund, delayed, orphan_settlement)
            settlement_rows.append({
                "settlement_id": settlement_id,
                "payment_id": rand_id("pay", 10),
                "order_id": o["order_id"],
                "gross_amount": gross,
                "fee": fee,
                "tax_on_fee": tax_on_fee,
                "net_amount": net,
                "settled_at": row_settled_at,
                "utr": bank_ref,
            })
            batch_net_total += net

            if o["case_type"] != "orphan_settlement":
                ledger_rows.append({
                    "invoice_id": o["invoice_id"],
                    "order_id": o["order_id"],
                    "invoice_amount": gross,
                    "customer": o["customer"],
                    "status": "closed",
                    "created_at": o["created_at"],
                })
                expected_match = o["case_type"] not in ("delayed_settlement",)
                ground_truth_rows.append({
                    "order_id": o["order_id"],
                    "invoice_id": o["invoice_id"],
                    "case_type": o["case_type"],
                    "expected_match": expected_match,
                    "expected_category": o["case_type"],
                    "notes": notes,
                })
            else:
                ground_truth_rows.append({
                    "order_id": o["order_id"],
                    "invoice_id": None,
                    "case_type": "orphan_settlement",
                    "expected_match": False,
                    "expected_category": "orphan_settlement",
                    "notes": notes,
                })

        # occasionally inject a fee/rounding drift on the whole batch's bank total
        drift = 0.0
        batch_notes = "clean_batch"
        if random.random() < 0.15 and batch_net_total > 0:
            drift = round(random.uniform(-25, 25), 2)
            batch_notes = f"fee_drift: bank total off by {drift} from summed settlement net"

        if batch_net_total > 0:
            bank_rows.append({
                "txn_date": settled_at + timedelta(days=random.randint(0, 1)),
                "narration": f"RAZORPAY SETTLE {settlement_id[-7:].upper()}",
                "amount": round(batch_net_total + drift, 2),
                "bank_ref": bank_ref,
                "batch_notes": batch_notes,
            })

    # inject duplicate bank rows (bank-side glitch) on ~4% of bank lines
    dup_count = max(2, int(len(bank_rows) * 0.08))
    for row in random.sample(bank_rows, dup_count):
        dup = dict(row)
        dup["batch_notes"] = "duplicate_bank_row: erroneous duplicate posting"
        bank_rows.append(dup)

    random.shuffle(bank_rows)
    random.shuffle(settlement_rows)
    random.shuffle(ledger_rows)

    def write_csv(path, rows, fieldnames):
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    import os
    os.makedirs(output_dir, exist_ok=True)

    write_csv(f"{output_dir}/bank_statement.csv", bank_rows,
               ["txn_date", "narration", "amount", "bank_ref", "batch_notes"])
    write_csv(f"{output_dir}/razorpay_settlement.csv", settlement_rows,
               ["settlement_id", "payment_id", "order_id", "gross_amount", "fee",
                "tax_on_fee", "net_amount", "settled_at", "utr"])
    write_csv(f"{output_dir}/internal_ledger.csv", ledger_rows,
               ["invoice_id", "order_id", "invoice_amount", "customer", "status", "created_at"])
    write_csv(f"{output_dir}/ground_truth.csv", ground_truth_rows,
               ["order_id", "invoice_id", "case_type", "expected_match",
                "expected_category", "notes"])

    print(f"Generated {len(orders)} orders across {len(batches)} settlement batches:")
    print(f"  bank_statement.csv       -> {len(bank_rows)} rows")
    print(f"  razorpay_settlement.csv  -> {len(settlement_rows)} rows")
    print(f"  internal_ledger.csv      -> {len(ledger_rows)} rows")
    print(f"  ground_truth.csv         -> {len(ground_truth_rows)} rows (held out -- do not feed to the matcher)")

    from collections import Counter
    counts = Counter(o["case_type"] for o in orders)
    print("\nCase type distribution:")
    for k, v in counts.items():
        print(f"  {k:22s}: {v} ({v / len(orders):.1%})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic reconciliation data.")
    parser.add_argument("--num-orders", type=int, default=220)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=str, default=".")
    parser.add_argument("--base-date", type=str, default="2026-07-01",
                         help="earliest order creation date, YYYY-MM-DD")
    args = parser.parse_args()

    generate(args.num_orders, args.seed, args.output_dir, args.base_date)
