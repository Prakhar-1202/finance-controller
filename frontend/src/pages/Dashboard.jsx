import { useState, useEffect, useCallback } from "react";
import { runReconciliation, getTransactions, getExceptions } from "../services/api";
import MetricsCards from "../components/dashboard/MetricsCards";
import ReconciliationChart from "../components/dashboard/ReconciliationChart";
import ExceptionBreakdown from "../components/dashboard/ExceptionBreakdown";
import RecentActivity from "../components/dashboard/RecentActivity";

// How many items to show in the Recent Activity widget. Purely a
// display slice for this page's UI — not a business/reconciliation
// decision, and not sent to the backend as a filter.
const RECENT_ACTIVITY_LIMIT = 5;

// The four exception buckets returned by GET /api/exceptions.
// Flattened into a single array for ExceptionBreakdown, which groups
// items by their existing `category` field.
const EXCEPTION_SOURCE_KEYS = [
  "duplicate_bank_rows",
  "drift_batches",
  "tier3_order_exceptions",
  "tier3_batch_report",
];

/**
 * Flattens the /api/exceptions response ({ duplicate_bank_rows,
 * drift_batches, tier3_order_exceptions, tier3_batch_report }) into a
 * single array for ExceptionBreakdown.
 *
 * This is a structural reshape only: it concatenates whichever of the
 * four buckets are arrays, in the order listed above. It does NOT read,
 * set, infer, or rewrite any item's `category` field — each item's
 * `category` (assigned entirely by the backend's categorizer.py) is
 * passed through untouched. Buckets that aren't arrays (e.g. if
 * tier3_batch_report is a summary object rather than a list) are
 * skipped here rather than guessed at.
 */
function normalizeExceptions(exceptionsResponse) {
  if (!exceptionsResponse) return [];

  return EXCEPTION_SOURCE_KEYS.reduce((flattened, key) => {
    const bucket = exceptionsResponse[key];
    if (Array.isArray(bucket)) {
      return flattened.concat(bucket);
    }
    return flattened;
  }, []);
}

/**
 * Dashboard
 * Top-level page that composes the dashboard's presentational
 * components and owns all page-level state (loading, refreshing,
 * error, fetched data). All reconciliation, matching, categorization,
 * and metrics computation happens on the backend — this page only
 * fetches results via services/api.js and passes them down as props.
 *
 * Data flow on both initial mount and refresh:
 * 1. runReconciliation() -> { metrics, exception_counts }
 * 2. getTransactions()   -> { total, page, page_size, items }
 * 3. getExceptions()     -> { duplicate_bank_rows, drift_batches,
 *                             tier3_order_exceptions, tier3_batch_report }
 */
function Dashboard() {
  const [metrics, setMetrics] = useState({});
  const [transactions, setTransactions] = useState([]);
  const [exceptions, setExceptions] = useState([]);

  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const loadDashboardData = useCallback(async () => {
    setError(null);

    try {
      // Refresh must re-run reconciliation before reloading downstream data.
      const reconcileResponse = await runReconciliation();
      setMetrics(reconcileResponse?.metrics || {});

      const [transactionsResponse, exceptionsResponse] = await Promise.all([
        getTransactions(),
        getExceptions(),
      ]);

      setTransactions(transactionsResponse?.items || []);
      setExceptions(normalizeExceptions(exceptionsResponse));
    } catch (err) {
      setError(err.message || "Failed to load dashboard data");
    }
  }, []);

  useEffect(() => {
    (async () => {
      setIsLoading(true);
      await loadDashboardData();
      setIsLoading(false);
    })();
  }, [loadDashboardData]);

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await loadDashboardData();
    setIsRefreshing(false);
  }, [loadDashboardData]);

  if (isLoading) {
    return (
      <div className="dashboard-page">
        <div className="dashboard-loading">Loading dashboard...</div>
      </div>
    );
  }

  return (
    <div className="dashboard-page">
      {error && (
        <div className="dashboard-error" role="alert">
          <span>{error}</span>
          <button
            type="button"
            className="dashboard-error-retry"
            onClick={handleRefresh}
            disabled={isRefreshing}
          >
            Retry
          </button>
        </div>
      )}

      <div className="dashboard-refresh-row">
        <button
          type="button"
          className="dashboard-refresh-btn"
          onClick={handleRefresh}
          disabled={isRefreshing}
        >
          {isRefreshing ? "Refreshing..." : "Refresh Reconciliation"}
        </button>
      </div>

      <section className="dashboard-section">
        <MetricsCards metrics={metrics} />
      </section>

      <section className="dashboard-section dashboard-grid">
        <ReconciliationChart metrics={metrics} />
        <ExceptionBreakdown exceptions={exceptions} />
      </section>

      <section className="dashboard-section">
        <RecentActivity
          transactions={transactions}
          limit={RECENT_ACTIVITY_LIMIT}
        />
      </section>
    </div>
  );
}

export default Dashboard;