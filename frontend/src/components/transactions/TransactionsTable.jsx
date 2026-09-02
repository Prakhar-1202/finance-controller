import React from "react";
import { MoreHorizontal } from "lucide-react";
import TransactionStatusBadge from "./TransactionStatusBadge";

function formatINR(val) {
  if (val === undefined || val === null || val === "") return "—";
  const num = Number(val);
  if (Number.isNaN(num)) return String(val);
  return `₹${num.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatDate(val) {
  if (!val) return "—";
  try {
    const d = new Date(val);
    if (Number.isNaN(d.getTime())) return String(val);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return String(val);
  }
}

function getTierClass(tier) {
  const str = String(tier || "").toLowerCase();
  if (str.includes("1")) return "tier-1";
  if (str.includes("2")) return "tier-2";
  if (str.includes("3")) return "tier-3";
  return "";
}

function TransactionsTable({ transactions = [] }) {
  const hasData = transactions.length > 0;

  return (
    <div className="table-responsive">
      <table className="stitch-table" aria-label="Transaction Ledger Table">
        <thead>
          <tr>
            <th>Order ID</th>
            <th>Customer</th>
            <th className="th-right">Invoice Amount</th>
            <th className="th-right">Net Amount</th>
            <th>Reconciliation</th>
            <th>Tier</th>
            <th>Category</th>
            <th>UTR</th>
            <th>Created At</th>
            <th style={{ width: "40px" }} aria-label="Actions"></th>
          </tr>
        </thead>
        <tbody>
          {hasData ? (
            transactions.map((txn, index) => {
              const rowKey = txn.order_id || txn.invoice_id || `txn-${index}`;
              const tierStr = txn.tier || (txn.reconciliation_status === "reconciled" ? "Tier 1" : "Tier 2");

              return (
                <tr key={rowKey}>
                  <td className="td-mono">{txn.order_id || "—"}</td>
                  <td className="td-entity">{txn.customer || "Direct / Gateway"}</td>
                  <td className="td-mono td-right">{formatINR(txn.invoice_amount)}</td>
                  <td className="td-mono td-right">{formatINR(txn.net_amount)}</td>
                  <td>
                    <TransactionStatusBadge status={txn.reconciliation_status} />
                  </td>
                  <td className={`td-tier ${getTierClass(tierStr)}`}>
                    {tierStr}
                  </td>
                  <td className="td-category">{txn.category || txn.ledger_status || "Settlement"}</td>
                  <td className="td-mono" style={{ fontSize: "12px", color: "#5A6A85" }}>
                    {txn.utr || "PENDING"}
                  </td>
                  <td style={{ fontSize: "12px", color: "#8896AB" }}>
                    {formatDate(txn.created_at)}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <button
                      type="button"
                      style={{ color: "#7587a7", padding: "4px" }}
                      title="More transaction actions"
                      aria-label="More options"
                    >
                      <MoreHorizontal size={16} />
                    </button>
                  </td>
                </tr>
              );
            })
          ) : (
            <tr>
              <td colSpan={10} style={{ textAlign: "center", padding: "48px 24px", color: "#8896AB" }}>
                No transactions match the selected criteria
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default TransactionsTable;