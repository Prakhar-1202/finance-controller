import React from "react";
import TransactionStatusBadge from "../transactions/TransactionStatusBadge";

function formatINR(val) {
  if (val === undefined || val === null || val === "") return "—";
  const num = Number(val);
  if (Number.isNaN(num)) return String(val);
  return `₹${num.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function RecentActivity({
  transactions = [],
  limit = 5,
  onNavigate = () => {},
}) {
  const visibleItems = typeof limit === "number" ? transactions.slice(0, limit) : transactions;
  const hasData = visibleItems.length > 0;

  return (
    <div className="recent-activity-card" aria-label="Recent Reconciliation Activity">
      <div className="recent-activity-header">
        <h3 className="recent-activity-title">Recent Activity</h3>
        <button
          type="button"
          className="recent-activity-view-all"
          onClick={() => onNavigate("transactions")}
        >
          View all
        </button>
      </div>

      <div className="table-responsive">
        <table className="stitch-table">
          <thead>
            <tr>
              <th>Transaction ID</th>
              <th>Entity</th>
              <th>Amount</th>
              <th>Status</th>
              <th>Tier</th>
            </tr>
          </thead>
          <tbody>
            {hasData ? (
              visibleItems.map((txn, idx) => {
                const key = txn.order_id || txn.invoice_id || `act-${idx}`;
                const amount = txn.invoice_amount ?? txn.net_amount;
                const entity = txn.customer || txn.utr || "Direct Gateway";
                const tierLabel = txn.tier || (txn.reconciliation_status === "reconciled" ? "Tier 1" : "Tier 2");

                return (
                  <tr key={key}>
                    <td className="td-mono">{txn.order_id || "—"}</td>
                    <td className="td-entity">{entity}</td>
                    <td className="td-mono">{formatINR(amount)}</td>
                    <td>
                      <TransactionStatusBadge status={txn.reconciliation_status} />
                    </td>
                    <td className="td-tier">{tierLabel}</td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={5} style={{ textAlign: "center", padding: "32px", color: "#8896AB" }}>
                  No recent transactions available
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default RecentActivity;