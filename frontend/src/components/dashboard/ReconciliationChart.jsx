import React from "react";
import { MoreHorizontal } from "lucide-react";

function ReconciliationChart({ metrics = {} }) {
  const total = metrics.total_orders ?? 0;
  const reconciled = metrics.reconciled_orders ?? 0;
  const unreconciled = metrics.unreconciled_orders ?? 0;

  // Rate calculation
  const rawRate = metrics.reconciliation_rate;
  const numRate = Number(rawRate);
  const pct = !Number.isNaN(numRate) && rawRate !== undefined && rawRate !== null
    ? (numRate <= 1.0 && numRate >= 0 ? numRate * 100 : numRate)
    : (total > 0 ? (reconciled / total) * 100 : 0);

  const rateFormatted = pct.toFixed(1);

  // Estimates for breakdown bars based on pipeline results
  // Reconciled is clean matches; unreconciled is pending
  const reconciledPct = total > 0 ? ((reconciled / total) * 100).toFixed(1) : 0;
  const pendingPct = total > 0 ? ((unreconciled / total) * 100).toFixed(1) : 0;

  // Stroke calculation for circular donut: circumference = 2 * PI * r = 100
  const radius = 15.9155;
  const strokeDashoffset = 25; // start from 12 o'clock

  return (
    <div className="health-card" aria-label="Reconciliation Health Analysis">
      <div className="health-card-header">
        <h3 className="health-card-title">Reconciliation Health</h3>
        <button
          type="button"
          style={{ color: "#7587a7", padding: "4px" }}
          title="More options"
          aria-label="More options"
        >
          <MoreHorizontal size={18} />
        </button>
      </div>

      <div className="health-card-body">
        {/* Radial Circular Donut */}
        <div className="health-donut-wrapper">
          <svg className="w-full h-full" viewBox="0 0 36 36" style={{ transform: "rotate(-90deg)" }}>
            {/* Background Track */}
            <circle
              cx="18"
              cy="18"
              r={radius}
              fill="none"
              stroke="rgba(214, 227, 252, 0.45)"
              strokeWidth="3.2"
            />
            {/* Primary Reconciled Arc */}
            <circle
              cx="18"
              cy="18"
              r={radius}
              fill="none"
              stroke="#0C9F9A"
              strokeWidth="3.2"
              strokeDasharray={`${Math.min(pct, 100)}, 100`}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              style={{ transition: "stroke-dasharray 600ms ease" }}
            />
          </svg>

          <div className="health-donut-center">
            <span className="health-donut-rate">{rateFormatted}%</span>
            <span className="health-donut-label">Healthy</span>
          </div>
        </div>

        {/* Status Breakdown Bars */}
        <div className="health-breakdown-list">
          {/* Reconciled Volume */}
          <div className="health-breakdown-item">
            <div className="health-breakdown-row">
              <span className="health-breakdown-label">Reconciled (Clean &amp; Recovered)</span>
              <span className="health-breakdown-val">
                {reconciled.toLocaleString()} ({reconciledPct}%)
              </span>
            </div>
            <div className="health-breakdown-track">
              <div
                className="health-breakdown-fill teal"
                style={{ width: `${reconciledPct}%` }}
              />
            </div>
          </div>

          {/* Pending / Unreconciled */}
          <div className="health-breakdown-item">
            <div className="health-breakdown-row">
              <span className="health-breakdown-label">Pending / Unreconciled</span>
              <span className="health-breakdown-val">
                {unreconciled.toLocaleString()} ({pendingPct}%)
              </span>
            </div>
            <div className="health-breakdown-track">
              <div
                className="health-breakdown-fill amber"
                style={{ width: `${pendingPct}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ReconciliationChart;