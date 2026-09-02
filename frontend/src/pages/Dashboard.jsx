import React, { useState, useEffect, useCallback } from "react";
import { Download, RefreshCw, AlertCircle } from "lucide-react";
import { runReconciliation, getTransactions, getExceptions } from "../services/api";
import MetricsCards from "../components/dashboard/MetricsCards";
import ReconciliationChart from "../components/dashboard/ReconciliationChart";
import ExceptionBreakdown from "../components/dashboard/ExceptionBreakdown";
import RecentActivity from "../components/dashboard/RecentActivity";

const RECENT_ACTIVITY_LIMIT = 5;

function getFormattedDate() {
  const options = { weekday: "long", day: "numeric", month: "long", year: "numeric" };
  return new Date().toLocaleDateString("en-US", options);
}

function Dashboard({ onNavigate = () => {} }) {
  const [metrics, setMetrics] = useState({});
  const [transactions, setTransactions] = useState([]);
  const [rawExceptions, setRawExceptions] = useState({});

  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const loadDashboardData = useCallback(async () => {
    setError(null);

    try {
      const reconcileResponse = await runReconciliation();
      setMetrics(reconcileResponse?.metrics || {});

      const [transactionsResponse, exceptionsResponse] = await Promise.all([
        getTransactions({ page: 1, page_size: 10 }),
        getExceptions(),
      ]);

      setTransactions(transactionsResponse?.items || []);
      setRawExceptions(exceptionsResponse || {});
    } catch (err) {
      setError(err.message || "Failed to load reconciliation dashboard data");
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
      <div className="dashboard-page" style={{ padding: "48px 0", textAlign: "center" }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: "10px", color: "#5A6A85" }}>
          <RefreshCw size={18} className="spinning" style={{ animation: "spin 0.8s linear infinite" }} />
          <span>Loading reconciliation intelligence...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-page">
      {/* Error Alert */}
      {error && (
        <div className="alert-banner alert-banner-error" role="alert">
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
          <button
            type="button"
            className="alert-banner-btn"
            onClick={handleRefresh}
            disabled={isRefreshing}
          >
            Retry
          </button>
        </div>
      )}

      {/* Unified Page Header */}
      <div className="page-header">
        <div>
          <div className="page-header-pre">{getFormattedDate()}</div>
          <h1 className="page-header-title">Good morning, Alex</h1>
          <p className="page-header-desc">
            Here's the latest operational view of your reconciliation cycle.
          </p>
        </div>

        <div className="page-header-actions">
          <button
            type="button"
            className="btn-primary"
            onClick={handleRefresh}
            disabled={isRefreshing}
          >
            <RefreshCw size={14} className={isRefreshing ? "spinning" : ""} />
            <span>{isRefreshing ? "Refreshing..." : "Re-run Pipeline"}</span>
          </button>

          <button
            type="button"
            className="btn-secondary"
            onClick={() => window.print()}
          >
            <Download size={14} />
            <span>Export Report</span>
          </button>
        </div>
      </div>

      {/* Row 1: KPI Summary Metrics Cards */}
      <MetricsCards metrics={metrics} />

      {/* Row 2: Analytics Grid (Health Donut + Exception Breakdown) */}
      <div className="dashboard-analytics-grid">
        <ReconciliationChart metrics={metrics} />
        <ExceptionBreakdown
          exceptionsData={rawExceptions}
          onNavigate={onNavigate}
        />
      </div>

      {/* Row 3: Recent Activity Table */}
      <RecentActivity
        transactions={transactions}
        limit={RECENT_ACTIVITY_LIMIT}
        onNavigate={onNavigate}
      />
    </div>
  );
}

export default Dashboard;