import React, { useState, useEffect, useCallback } from "react";
import {
  Download,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
} from "lucide-react";

import {
  runReconciliation,
  getTransactions,
  getExceptions,
} from "../services/api";

import MetricsCards from "../components/dashboard/MetricsCards";
import ReconciliationChart from "../components/dashboard/ReconciliationChart";
import ExceptionBreakdown from "../components/dashboard/ExceptionBreakdown";
import RecentActivity from "../components/dashboard/RecentActivity";

const RECENT_ACTIVITY_LIMIT = 5;

function getFormattedDate() {
  const options = {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  };

  return new Date().toLocaleDateString("en-US", options);
}

function Dashboard({
  onNavigate = () => {},
  dataDir = "data",
  datasetVersion = 0,
}) {
  const [metrics, setMetrics] = useState({});
  const [transactions, setTransactions] = useState([]);
  const [rawExceptions, setRawExceptions] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [isRunningPipeline, setIsRunningPipeline] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const loadDashboardData = useCallback(async () => {
    const reconcileResponse = await runReconciliation({
      data_dir: dataDir,
    });

    setMetrics(reconcileResponse?.metrics || {});

    const [transactionsResponse, exceptionsResponse] = await Promise.all([
      getTransactions({
        page: 1,
        page_size: 10,
        data_dir: dataDir,
      }),
      getExceptions({
        data_dir: dataDir,
      }),
    ]);

    setTransactions(transactionsResponse?.items || []);
    setRawExceptions(exceptionsResponse || {});

    return reconcileResponse;
  }, [dataDir]);

  useEffect(() => {
    (async () => {
      setIsLoading(true);

      try {
        await loadDashboardData();
      } catch (err) {
        setFeedback({
          type: "error",
          message:
            err.message ||
            "Failed to load reconciliation dashboard data",
        });
      } finally {
        setIsLoading(false);
      }
    })();
  }, [loadDashboardData, datasetVersion]);

  const handleRunPipeline = useCallback(async () => {
    if (isRunningPipeline) return;

    setIsRunningPipeline(true);
    setFeedback(null);

    try {
      const reconcileResponse = await loadDashboardData();

      const reconciledCount =
        reconcileResponse?.metrics?.reconciled_orders;

      const totalCount =
        reconcileResponse?.metrics?.total_orders;

      const successMsg =
        reconciledCount !== undefined && totalCount !== undefined
          ? `Pipeline completed successfully • ${reconciledCount} of ${totalCount} orders reconciled`
          : "Pipeline completed successfully • Dashboard metrics updated";

      setFeedback({
        type: "success",
        message: successMsg,
      });

      setTimeout(() => {
        setFeedback((prev) =>
          prev?.type === "success" ? null : prev
        );
      }, 5000);
    } catch (err) {
      setFeedback({
        type: "error",
        message:
          err.message ||
          "Pipeline execution failed. Please check network/backend status.",
      });
    } finally {
      setIsRunningPipeline(false);
    }
  }, [isRunningPipeline, loadDashboardData]);

  const datasetLabel =
    dataDir === "data" ? "Default demo dataset" : "Active dataset";

  if (isLoading) {
    return (
      <div
        className="dashboard-page"
        style={{
          padding: "48px 0",
          textAlign: "center",
        }}
      >
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "10px",
            color: "#5A6A85",
          }}
        >
          <RefreshCw size={18} className="spinning" />
          <span>Loading reconciliation intelligence...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-page">
      {feedback?.type === "error" && (
        <div
          className="alert-banner alert-banner-error"
          role="alert"
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            <AlertCircle size={16} />
            <span>{feedback.message}</span>
          </div>

          <button
            type="button"
            className="alert-banner-btn"
            onClick={handleRunPipeline}
            disabled={isRunningPipeline}
          >
            Retry
          </button>
        </div>
      )}

      {feedback?.type === "success" && (
        <div
          className="alert-banner alert-banner-success"
          role="status"
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            <CheckCircle2 size={16} />
            <span>{feedback.message}</span>
          </div>
        </div>
      )}

      <div className="page-header">
        <div>
          <div className="page-header-pre">
            {getFormattedDate()}
          </div>

          <h1 className="page-header-title">
            Good morning, Alex
          </h1>

          <p className="page-header-desc">
            Here's the latest operational view of your reconciliation cycle.
            <span className="dataset-badge">
              {datasetLabel}
            </span>
          </p>
        </div>

        <div className="page-header-actions">
          <button
            type="button"
            className="btn-primary"
            onClick={handleRunPipeline}
            disabled={isRunningPipeline}
            aria-busy={isRunningPipeline}
            title="Trigger full reconciliation pipeline"
          >
            <RefreshCw
              size={14}
              className={isRunningPipeline ? "spinning" : ""}
            />

            <span>
              {isRunningPipeline
                ? "Running..."
                : "Re-run Pipeline"}
            </span>
          </button>

          <button
            type="button"
            className="btn-secondary"
            onClick={() => window.print()}
            title="Export reconciliation report"
          >
            <Download size={14} />
            <span>Export Report</span>
          </button>
        </div>
      </div>

      <MetricsCards metrics={metrics} />

      <div className="dashboard-analytics-grid">
        <ReconciliationChart metrics={metrics} />

        <ExceptionBreakdown
          exceptionsData={rawExceptions}
          onNavigate={onNavigate}
        />
      </div>

      <RecentActivity
        transactions={transactions}
        limit={RECENT_ACTIVITY_LIMIT}
        onNavigate={onNavigate}
      />
    </div>
  );
}

export default Dashboard;