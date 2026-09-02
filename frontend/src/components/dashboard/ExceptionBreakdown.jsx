import React from "react";
import { ArrowUpRight, SlidersHorizontal } from "lucide-react";

function formatCurrency(val) {
  if (val === undefined || val === null || val === 0) return "₹0.00";
  const num = Number(val);
  return Number.isNaN(num) ? String(val) : `₹${num.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function ExceptionBreakdown({
  exceptions = [],
  exceptionsData = {},
  onNavigate = () => {},
}) {
  // Extract groups from structured exceptionsData or count from flat exceptions
  const duplicateRows = exceptionsData?.duplicate_bank_rows || [];
  const driftBatches = exceptionsData?.drift_batches || [];
  const tier3Exceptions = exceptionsData?.tier3_order_exceptions || [];
  const batchReports = exceptionsData?.tier3_batch_report || [];

  // Sum amounts where available
  const duplicateSum = duplicateRows.reduce((acc, r) => acc + (Number(r.amount) || 0), 0);
  const driftSum = driftBatches.reduce((acc, r) => acc + Math.abs(Number(r.diff) || 0), 0);
  const batchReportSum = batchReports.reduce((acc, r) => acc + Math.abs(Number(r.diff) || 0), 0);

  // Group items
  const items = [
    {
      num: "01",
      name: "Duplicate bank rows",
      count: duplicateRows.length,
      desc: "Same UTR posted more than once",
      amountText: duplicateSum > 0 ? formatCurrency(duplicateSum) : `${duplicateRows.length} flagged`,
      tone: "amber",
      fillPct: duplicateRows.length > 0 ? 80 : 10,
    },
    {
      num: "02",
      name: "Amount drift batches",
      count: driftBatches.length,
      desc: "Invoice and settlement differ",
      amountText: driftSum > 0 ? formatCurrency(driftSum) : `${driftBatches.length} batches`,
      tone: "cyan",
      fillPct: driftBatches.length > 0 ? 65 : 10,
    },
    {
      num: "03",
      name: "Tier 3 batch reports",
      count: batchReports.length,
      desc: "Unresolved batch health status",
      amountText: batchReportSum > 0 ? formatCurrency(batchReportSum) : `${batchReports.length} reports`,
      tone: "rose",
      fillPct: batchReports.length > 0 ? 50 : 10,
    },
    {
      num: "04",
      name: "Tier 3 order exceptions",
      count: tier3Exceptions.length,
      desc: "Requires controller review",
      amountText: `${tier3Exceptions.length} orders`,
      tone: "purple",
      fillPct: tier3Exceptions.length > 0 ? 35 : 10,
    },
  ];

  return (
    <div className="breakdown-card" aria-label="Exception Breakdown">
      {/* Header */}
      <div className="breakdown-card-header">
        <div>
          <span className="breakdown-card-tag">Exception Breakdown</span>
          <h3 className="breakdown-card-title">Where attention is needed</h3>
        </div>
        <button
          type="button"
          style={{ color: "#7587a7", padding: "6px", borderRadius: "8px", border: "1px solid #E6EBF1" }}
          title="Filter categories"
          aria-label="Filter categories"
        >
          <SlidersHorizontal size={16} />
        </button>
      </div>

      {/* 4-Item Grid */}
      <div className="breakdown-grid">
        {items.map((item) => (
          <div key={item.num} className="breakdown-item">
            <div className={`breakdown-item-num ${item.tone}`}>{item.num}</div>
            <div className="breakdown-item-main">
              <div className="breakdown-item-top">
                <span className="breakdown-item-name">{item.name}</span>
                <span className="breakdown-item-count">{item.count}</span>
              </div>
              <div className="breakdown-item-desc-row">
                <span>{item.desc}</span>
                <span className="breakdown-item-amount">{item.amountText}</span>
              </div>
              <div className="breakdown-progress-track">
                <div
                  className={`breakdown-progress-fill ${item.tone}`}
                  style={{ width: `${item.fillPct}%` }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Footer Navigation Link */}
      <div className="breakdown-card-footer">
        <button
          type="button"
          className="breakdown-footer-link"
          onClick={() => onNavigate("exceptions")}
        >
          <span>View all exceptions</span>
          <ArrowUpRight size={15} />
        </button>
      </div>
    </div>
  );
}

export default ExceptionBreakdown;