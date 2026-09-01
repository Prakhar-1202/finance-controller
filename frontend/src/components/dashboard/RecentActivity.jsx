import { Receipt } from "lucide-react";
import TransactionStatusBadge from "../transactions/TransactionStatusBadge";

// Formats a plain-text field for display only (fallback for missing
// values). Not business logic — no computation, matching, or
// categorization happens here.
function formatValue(value) {
  if (value === undefined || value === null || value === "") return "—";
  return value;
}

// Formats amount fields for display only (cosmetic decimal formatting).
// Not a financial calculation.
function formatAmount(value) {
  if (value === undefined || value === null || value === "") return "—";
  const numericValue = Number(value);
  if (Number.isNaN(numericValue)) return value;
  return numericValue.toFixed(2);
}

/**
 * RecentActivity
 * Purely presentational dashboard widget showing a compact list of
 * recent transactions. Renders exactly the items it's given, in the
 * order it's given them — it does not sort, filter, or determine what
 * counts as "recent"; that ordering is expected to come from the
 * backend/parent (e.g. already sorted by created_at, already limited
 * to N most recent items).
 *
 * Props:
 * - transactions: Array<{
 *     order_id?: string | number,
 *     customer?: string,
 *     invoice_amount?: number | string,
 *     net_amount?: number | string,
 *     reconciliation_status?: string,
 *     tier?: string | number,
 *     category?: string,
 *     utr?: string,
 *     created_at?: string,
 *     ...other fields (ignored by this component)
 *   }>
 * - limit: number -> optional cap on how many items to render (purely
 *                     a display slice, not a data/business decision)
 */
function RecentActivity({ transactions = [], limit }) {
  const hasData = transactions.length > 0;
  const visibleTransactions =
    typeof limit === "number" ? transactions.slice(0, limit) : transactions;

  return (
    <div className="recent-activity">
      <div className="recent-activity-header">
        <span className="recent-activity-title">Recent Activity</span>
      </div>

      {hasData ? (
        <ul className="recent-activity-list">
          {visibleTransactions.map((transaction, index) => {
            const rowKey =
              transaction.order_id ?? transaction.utr ?? `activity-${index}`;

            return (
              <li key={rowKey} className="recent-activity-item">
                <div className="recent-activity-icon">
                  <Receipt size={16} />
                </div>

                <div className="recent-activity-main">
                  <div className="recent-activity-row">
                    <span className="recent-activity-order">
                      {formatValue(transaction.order_id)}
                    </span>
                    <TransactionStatusBadge
                      status={transaction.reconciliation_status}
                    />
                  </div>

                  <div className="recent-activity-row recent-activity-subtext">
                    <span className="recent-activity-customer">
                      {formatValue(transaction.customer)}
                    </span>
                    <span className="recent-activity-tier">
                      Tier {formatValue(transaction.tier)}
                    </span>
                    <span className="recent-activity-category">
                      {formatValue(transaction.category)}
                    </span>
                  </div>

                  <div className="recent-activity-row recent-activity-subtext">
                    <span className="recent-activity-amount">
                      Invoice: {formatAmount(transaction.invoice_amount)}
                    </span>
                    <span className="recent-activity-amount">
                      Net: {formatAmount(transaction.net_amount)}
                    </span>
                    <span className="recent-activity-utr">
                      UTR: {formatValue(transaction.utr)}
                    </span>
                  </div>

                  <div className="recent-activity-timestamp">
                    {formatValue(transaction.created_at)}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <div className="recent-activity-empty">No recent activity</div>
      )}
    </div>
  );
}

export default RecentActivity;