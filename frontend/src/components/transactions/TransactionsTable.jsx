import TransactionStatusBadge from "./TransactionStatusBadge";

// Column definitions matching the actual /api/transactions item shape.
// Each column maps a display label to the corresponding field key on
// a transaction item. Kept as config so columns can be reordered or
// extended without touching the render logic below.
const COLUMNS = [
  { key: "order_id", label: "Order ID" },
  { key: "customer", label: "Customer" },
  { key: "invoice_amount", label: "Invoice Amount" },
  { key: "net_amount", label: "Net Amount" },
  { key: "reconciliation_status", label: "Reconciliation Status" },
  { key: "tier", label: "Tier" },
  { key: "category", label: "Category" },
  { key: "utr", label: "UTR" },
  { key: "created_at", label: "Created At" },
];

// Formats a plain-text cell value for display only (fallback for
// missing/empty values). Not business logic — no computation,
// matching, or categorization happens here.
function formatCellValue(value) {
  if (value === undefined || value === null || value === "") return "—";
  return value;
}

// Formats amount fields for display. Purely cosmetic number formatting
// (e.g. 2 decimal places) — not a financial calculation.
function formatAmount(value) {
  if (value === undefined || value === null || value === "") return "—";
  const numericValue = Number(value);
  if (Number.isNaN(numericValue)) return value;
  return numericValue.toFixed(2);
}

/**
 * TransactionsTable
 * Purely presentational, responsive table for displaying transaction
 * items as returned by GET /api/transactions (the `items` array from
 * the paginated response). Does not fetch data, compute anything, or
 * manage state — it only renders whatever is passed in.
 *
 * Props:
 * - transactions: Array<{
 *     order_id?: string | number,
 *     reconciliation_status?: string,
 *     tier?: string | number,
 *     invoice_id?: string | number,
 *     customer?: string,
 *     invoice_amount?: number | string,
 *     ledger_status?: string,
 *     created_at?: string,
 *     settlement_id?: string,
 *     net_amount?: number | string,
 *     utr?: string,
 *     category?: string,
 *     reason?: string,
 *     ...other fields (ignored by this table)
 *   }>
 */
function TransactionsTable({ transactions = [] }) {
  const hasData = transactions.length > 0;

  return (
    <div className="transactions-table-wrapper">
      <table className="transactions-table">
        <thead>
          <tr>
            {COLUMNS.map((column) => (
              <th key={column.key} scope="col">
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {hasData ? (
            transactions.map((transaction, index) => {
              const rowKey =
                transaction.order_id ??
                transaction.invoice_id ??
                `txn-${index}`;

              return (
                <tr key={rowKey}>
                  {COLUMNS.map((column) => {
                    if (column.key === "reconciliation_status") {
                      return (
                        <td key={column.key} data-label={column.label}>
                          <TransactionStatusBadge
                            status={transaction.reconciliation_status}
                          />
                        </td>
                      );
                    }

                    if (
                      column.key === "invoice_amount" ||
                      column.key === "net_amount"
                    ) {
                      return (
                        <td key={column.key} data-label={column.label}>
                          {formatAmount(transaction[column.key])}
                        </td>
                      );
                    }

                    return (
                      <td key={column.key} data-label={column.label}>
                        {formatCellValue(transaction[column.key])}
                      </td>
                    );
                  })}
                </tr>
              );
            })
          ) : (
            <tr>
              <td
                colSpan={COLUMNS.length}
                className="transactions-table-empty"
              >
                No transactions to display
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default TransactionsTable;