import React, { useState, useEffect, useCallback } from "react";
import {
  Download,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  ArrowUpRight,
  RefreshCw,
  AlertCircle,
  Sparkles,
} from "lucide-react";
import { getExceptions } from "../services/api";
import ExplainModal from "../components/exceptions/ExplainModal";

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

function Exceptions() {
  const [exceptionsData, setExceptionsData] = useState({
    duplicate_bank_rows: [],
    drift_batches: [],
    tier3_order_exceptions: [],
    tier3_batch_report: [],
  });

  const [expandedSections, setExpandedSections] = useState({
    duplicates: true,
    drift: true,
    tier3_orders: true,
    tier3_batches: true,
  });

  const [activeInspect, setActiveInspect] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadExceptions = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await getExceptions();
      setExceptionsData({
        duplicate_bank_rows: response?.duplicate_bank_rows || [],
        drift_batches: response?.drift_batches || [],
        tier3_order_exceptions: response?.tier3_order_exceptions || [],
        tier3_batch_report: response?.tier3_batch_report || [],
      });
    } catch (err) {
      setError(err.message || "Failed to load reconciliation exceptions");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadExceptions();
  }, [loadExceptions]);

  const toggleSection = (sectionKey) => {
    setExpandedSections((prev) => ({
      ...prev,
      [sectionKey]: !prev[sectionKey],
    }));
  };

  const duplicates = exceptionsData.duplicate_bank_rows;
  const drifts = exceptionsData.drift_batches;
  const tier3Orders = exceptionsData.tier3_order_exceptions;
  const tier3Batches = exceptionsData.tier3_batch_report;

  const totalExceptions = duplicates.length + drifts.length + tier3Orders.length + tier3Batches.length;

  const totalFlaggedAmount =
    duplicates.reduce((sum, r) => sum + (Number(r.amount) || 0), 0) +
    drifts.reduce((sum, r) => sum + Math.abs(Number(r.diff) || 0), 0) +
    tier3Batches.reduce((sum, r) => sum + Math.abs(Number(r.diff) || 0), 0);

  return (
    <div className="exceptions-page">
      {/* Unified Page Header */}
      <div className="page-header">
        <div>
          <div className="page-header-pre">Investigation Queue</div>
          <h1 className="page-header-title">Exceptions center</h1>
          <p className="page-header-desc">
            Prioritize breaks in the reconciliation flow and keep the close moving.
          </p>
        </div>

        <div className="page-header-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={() => window.print()}
            title="Print / download exceptions report"
          >
            <Download size={14} />
            <span>Download report</span>
          </button>
        </div>
      </div>

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
            onClick={loadExceptions}
          >
            Retry
          </button>
        </div>
      )}

      {/* Top Summary Banner Cards */}
      <div className="exceptions-kpi-grid">
        {/* Banner Alert Card */}
        <div className="exception-alert-banner">
          <div className="exception-alert-icon">
            <AlertTriangle size={18} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <h2 className="exception-alert-title">{totalExceptions} open exceptions</h2>
              <span style={{ fontSize: "10.5px", fontWeight: 700, color: "#D58A20", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Active Run
              </span>
            </div>
            <p className="exception-alert-subtext">
              Across 4 categories • {formatINR(totalFlaggedAmount)} total discrepancy identified
            </p>
          </div>
        </div>

        {/* KPI Card 1 */}
        <div className="exception-kpi-card">
          <span className="exception-kpi-label">Oldest open item</span>
          <div className="exception-kpi-val">2d 14h</div>
          <span className="exception-kpi-sub">Within SLA target</span>
        </div>

        {/* KPI Card 2 */}
        <div className="exception-kpi-card">
          <span className="exception-kpi-label">Avg. resolution time</span>
          <div className="exception-kpi-val">4h 22m</div>
          <span className="exception-kpi-sub" style={{ color: "#149B75", fontWeight: 600 }}>
            Under SLA limit
          </span>
        </div>
      </div>

      {/* Main 2-Column Layout */}
      {isLoading ? (
        <div style={{ padding: "48px 0", textAlign: "center", color: "#5A6A85" }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: "10px" }}>
            <RefreshCw size={18} className="spinning" style={{ animation: "spin 0.8s linear infinite" }} />
            <span>Loading exceptions queue...</span>
          </div>
        </div>
      ) : (
        <div className="exceptions-main-layout">
          {/* Left Column: 4 Accordion Groups */}
          <div className="stitch-card">
            {/* 1. Duplicate Bank Rows */}
            <div className="exception-accordion-group">
              <div
                className="exception-accordion-header"
                onClick={() => toggleSection("duplicates")}
              >
                <div className="accordion-title-left">
                  <div className="accordion-badge-icon cyan">DB</div>
                  <div>
                    <h3 className="accordion-title-text">Duplicate Bank Rows</h3>
                    <p className="accordion-subtitle-text">
                      Bank references posted more than once against a single settlement.
                    </p>
                  </div>
                </div>

                <div className="accordion-count-badge">
                  <span>{duplicates.length} rows</span>
                  {expandedSections.duplicates ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                </div>
              </div>

              {expandedSections.duplicates && (
                <div className="table-responsive" style={{ borderTop: "1px solid #E6EBF1" }}>
                  <table className="stitch-table">
                    <thead>
                      <tr>
                        <th>Bank Ref</th>
                        <th>Row ID / Original</th>
                        <th className="th-right">Amount</th>
                        <th>Confidence</th>
                        <th>Date</th>
                        <th style={{ width: "70px" }}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {duplicates.length > 0 ? (
                        duplicates.map((row) => (
                          <tr key={row.bank_row_id}>
                            <td className="td-mono">{row.bank_ref}</td>
                            <td style={{ fontSize: "11.5px", color: "#5A6A85" }}>
                              Row #{row.bank_row_id} (orig #{row.presumed_original_bank_row_id})
                            </td>
                            <td className="td-mono td-right">{formatINR(row.amount)}</td>
                            <td>
                              <span className="status-pill exception">
                                <span className="status-pill-dot" />
                                <span>{row.confidence || "high"}</span>
                              </span>
                            </td>
                            <td style={{ fontSize: "11.5px", color: "#8896AB" }}>
                              {formatDate(row.txn_date)}
                            </td>
                            <td style={{ textAlign: "right" }}>
                              <button
                                type="button"
                                className="inspect-link-btn"
                                onClick={() =>
                                  setActiveInspect({
                                    detected_category: "duplicate_bank_row",
                                    bank_ref: row.bank_ref,
                                    amount: row.amount,
                                    narration: row.narration,
                                  })
                                }
                              >
                                <span>Inspect</span>
                                <ArrowUpRight size={12} />
                              </button>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={6} style={{ textAlign: "center", padding: "20px", color: "#8896AB" }}>
                            No duplicate bank rows detected
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* 2. Drift Batches */}
            <div className="exception-accordion-group">
              <div
                className="exception-accordion-header"
                onClick={() => toggleSection("drift")}
              >
                <div className="accordion-title-left">
                  <div className="accordion-badge-icon amber">DR</div>
                  <div>
                    <h3 className="accordion-title-text">Drift Batches</h3>
                    <p className="accordion-subtitle-text">
                      Net settlement amounts differ from bank statement values.
                    </p>
                  </div>
                </div>

                <div className="accordion-count-badge">
                  <span>{drifts.length} batches</span>
                  {expandedSections.drift ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                </div>
              </div>

              {expandedSections.drift && (
                <div className="table-responsive" style={{ borderTop: "1px solid #E6EBF1" }}>
                  <table className="stitch-table">
                    <thead>
                      <tr>
                        <th>Batch Ref</th>
                        <th className="th-right">Settled Sum</th>
                        <th className="th-right">Bank Amount</th>
                        <th className="th-right">Diff</th>
                        <th>Category</th>
                        <th style={{ width: "70px" }}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {drifts.length > 0 ? (
                        drifts.map((batch) => (
                          <tr key={batch.bank_ref}>
                            <td className="td-mono">{batch.bank_ref}</td>
                            <td className="td-mono td-right">{formatINR(batch.settled_sum)}</td>
                            <td className="td-mono td-right">{formatINR(batch.amount)}</td>
                            <td className="td-mono td-right" style={{ color: "#D95768", fontWeight: 600 }}>
                              {formatINR(batch.diff)}
                            </td>
                            <td>
                              <span className="status-pill unreconciled">
                                <span className="status-pill-dot" />
                                <span>{batch.category || "drift"}</span>
                              </span>
                            </td>
                            <td style={{ textAlign: "right" }}>
                              <button
                                type="button"
                                className="inspect-link-btn"
                                onClick={() =>
                                  setActiveInspect({
                                    detected_category: batch.category || "fee_drift",
                                    bank_ref: batch.bank_ref,
                                    bank_amount: batch.amount,
                                    settled_sum: batch.settled_sum,
                                    diff: batch.diff,
                                    narration: batch.narration,
                                  })
                                }
                              >
                                <span>Inspect</span>
                                <ArrowUpRight size={12} />
                              </button>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={6} style={{ textAlign: "center", padding: "20px", color: "#8896AB" }}>
                            No drift batches detected
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* 3. Tier 3 Order Exceptions */}
            <div className="exception-accordion-group">
              <div
                className="exception-accordion-header"
                onClick={() => toggleSection("tier3_orders")}
              >
                <div className="accordion-title-left">
                  <div className="accordion-badge-icon purple">T3</div>
                  <div>
                    <h3 className="accordion-title-text">Tier 3 Order Exceptions</h3>
                    <p className="accordion-subtitle-text">
                      High-value orders requiring human controller review.
                    </p>
                  </div>
                </div>

                <div className="accordion-count-badge">
                  <span>{tier3Orders.length} orders</span>
                  {expandedSections.tier3_orders ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                </div>
              </div>

              {expandedSections.tier3_orders && (
                <div className="table-responsive" style={{ borderTop: "1px solid #E6EBF1" }}>
                  <table className="stitch-table">
                    <thead>
                      <tr>
                        <th>Order ID</th>
                        <th>Batch Ref</th>
                        <th>Category</th>
                        <th>Reason</th>
                        <th style={{ width: "70px" }}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {tier3Orders.length > 0 ? (
                        tier3Orders.map((ord) => (
                          <tr key={ord.order_id}>
                            <td className="td-mono">{ord.order_id}</td>
                            <td className="td-mono" style={{ fontSize: "11.5px", color: "#5A6A85" }}>
                              {ord.bank_ref || "—"}
                            </td>
                            <td>
                              <span className="status-pill exception">
                                <span className="status-pill-dot" />
                                <span>{ord.category}</span>
                              </span>
                            </td>
                            <td style={{ fontSize: "12px", color: "#44474d" }}>{ord.reason}</td>
                            <td style={{ textAlign: "right" }}>
                              <button
                                type="button"
                                className="inspect-link-btn"
                                onClick={() =>
                                  setActiveInspect({
                                    detected_category: ord.category || "unmatched",
                                    order_id: ord.order_id,
                                    bank_ref: ord.bank_ref,
                                  })
                                }
                              >
                                <span>Inspect</span>
                                <ArrowUpRight size={12} />
                              </button>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={5} style={{ textAlign: "center", padding: "20px", color: "#8896AB" }}>
                            No individual order exceptions in this run
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* 4. Tier 3 Batch Report */}
            <div className="exception-accordion-group">
              <div
                className="exception-accordion-header"
                onClick={() => toggleSection("tier3_batches")}
              >
                <div className="accordion-title-left">
                  <div className="accordion-badge-icon rose">BR</div>
                  <div>
                    <h3 className="accordion-title-text">Tier 3 Batch Report</h3>
                    <p className="accordion-subtitle-text">
                      Consolidated resolution summary of high-priority batches.
                    </p>
                  </div>
                </div>

                <div className="accordion-count-badge">
                  <span>{tier3Batches.length} open</span>
                  {expandedSections.tier3_batches ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                </div>
              </div>

              {expandedSections.tier3_batches && (
                <div className="table-responsive" style={{ borderTop: "1px solid #E6EBF1" }}>
                  <table className="stitch-table">
                    <thead>
                      <tr>
                        <th>Batch Ref</th>
                        <th>Category</th>
                        <th>Orders (Resolved / Excluded)</th>
                        <th className="th-right">Diff</th>
                        <th style={{ width: "70px" }}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {tier3Batches.length > 0 ? (
                        tier3Batches.map((batch) => (
                          <tr key={batch.bank_ref}>
                            <td className="td-mono">{batch.bank_ref}</td>
                            <td>
                              <span className="status-pill unreconciled">
                                <span className="status-pill-dot" />
                                <span>{batch.category}</span>
                              </span>
                            </td>
                            <td style={{ fontSize: "12px", color: "#15233A", fontWeight: 500 }}>
                              {batch.n_orders} orders ({batch.n_resolved} resolved, {batch.n_excluded} excluded)
                            </td>
                            <td className="td-mono td-right" style={{ color: "#D95768" }}>
                              {formatINR(batch.diff)}
                            </td>
                            <td style={{ textAlign: "right" }}>
                              <button
                                type="button"
                                className="inspect-link-btn"
                                onClick={() =>
                                  setActiveInspect({
                                    detected_category: batch.category || "ambiguous_duplicate_ref",
                                    bank_ref: batch.bank_ref,
                                    diff: batch.diff,
                                  })
                                }
                              >
                                <span>Inspect</span>
                                <ArrowUpRight size={12} />
                              </button>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={5} style={{ textAlign: "center", padding: "20px", color: "#8896AB" }}>
                            No batch reports flagged
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Controller Note Card */}
          <div className="controller-note-card">
            <div className="controller-note-tag">Controller Note</div>
            <h3 className="controller-note-title">Keep exceptions moving</h3>
            <p className="controller-note-desc">
              Resolve duplicate bank statement rows and ambiguous batches first to protect settlement ledger accuracy before the daily close.
            </p>

            <hr className="controller-note-divider" />

            <div>
              <div className="controller-stat-row">
                <span className="controller-stat-label">Total active exceptions</span>
                <span className="controller-stat-val">{totalExceptions}</span>
              </div>
              <div className="controller-stat-row">
                <span className="controller-stat-label">Flagged batches</span>
                <span className="controller-stat-val">{drifts.length + tier3Batches.length}</span>
              </div>
              <div className="controller-stat-row">
                <span className="controller-stat-label">AI Reasoning Engine</span>
                <span className="controller-stat-val" style={{ color: "#0C9F9A" }}>
                  Operational
                </span>
              </div>
            </div>

            <button
              type="button"
              className="btn-primary"
              style={{ width: "100%", marginTop: "16px" }}
              onClick={() => {
                if (duplicates.length > 0) {
                  setActiveInspect({
                    detected_category: "duplicate_bank_row",
                    bank_ref: duplicates[0].bank_ref,
                    amount: duplicates[0].amount,
                  });
                } else if (drifts.length > 0) {
                  setActiveInspect({
                    detected_category: drifts[0].category || "fee_drift",
                    bank_ref: drifts[0].bank_ref,
                    diff: drifts[0].diff,
                  });
                }
              }}
            >
              <Sparkles size={15} />
              <span>AI Review Queue</span>
            </button>
          </div>
        </div>
      )}

      {/* AI Explanation Modal */}
      {activeInspect && (
        <ExplainModal
          exceptionContext={activeInspect}
          onClose={() => setActiveInspect(null)}
        />
      )}
    </div>
  );
}

export default Exceptions;