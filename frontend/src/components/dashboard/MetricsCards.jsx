import React from "react";
import {
  TrendingUp,
  CheckCircle2,
  AlertTriangle,
  ShieldCheck,
  AlertCircle,
} from "lucide-react";

function formatNumber(val) {
  if (val === undefined || val === null || val === "") return "—";
  const num = Number(val);
  return Number.isNaN(num) ? String(val) : num.toLocaleString();
}

function formatRate(val) {
  if (val === undefined || val === null || val === "") return "—";
  const num = Number(val);
  if (Number.isNaN(num)) return String(val);
  const pct = num <= 1.0 && num >= 0 ? num * 100 : num;
  return pct % 1 === 0 ? pct.toFixed(0) : pct.toFixed(1);
}

function MetricsCards({ metrics = {} }) {
  const total = metrics.total_orders ?? 0;
  const reconciled = metrics.reconciled_orders ?? 0;
  const unreconciled = metrics.unreconciled_orders ?? 0;
  const reconRate = metrics.reconciliation_rate;
  const excRate = metrics.exception_rate;

  const reconPctFormatted = formatRate(reconRate);
  const excPctFormatted = formatRate(excRate);

  return (
    <section className="metrics-cards" aria-label="Summary Performance Indicators">
      {/* 1. Total Orders */}
      <article className="metric-card metric-card-slate">
        <div className="metric-card-top">
          <span className="metric-card-label">Total orders</span>
          <div className="metric-card-icon" aria-hidden="true">
            <TrendingUp size={16} strokeWidth={2.2} />
          </div>
        </div>
        <div className="metric-card-content">
          <div className="metric-card-value-row">
            <span className="metric-card-value">{formatNumber(total)}</span>
          </div>
          <div className="metric-card-bottom">
            <span className="metric-card-badge neutral">Active cycle</span>
            <span className="metric-card-subtext">total considered</span>
          </div>
        </div>
      </article>

      {/* 2. Reconciled Orders */}
      <article className="metric-card metric-card-green">
        <div className="metric-card-top">
          <span className="metric-card-label">Reconciled orders</span>
          <div className="metric-card-icon" aria-hidden="true">
            <CheckCircle2 size={16} strokeWidth={2.2} />
          </div>
        </div>
        <div className="metric-card-content">
          <div className="metric-card-value-row">
            <span className="metric-card-value">{formatNumber(reconciled)}</span>
          </div>
          <div className="metric-card-bottom">
            <span className="metric-card-badge positive">
              {reconPctFormatted !== "—" ? `${reconPctFormatted}%` : "Clean match"}
            </span>
            <span className="metric-card-subtext">of total orders</span>
          </div>
        </div>
      </article>

      {/* 3. Unreconciled Orders */}
      <article className="metric-card metric-card-amber">
        <div className="metric-card-top">
          <span className="metric-card-label">Unreconciled orders</span>
          <div className="metric-card-icon" aria-hidden="true">
            <AlertTriangle size={16} strokeWidth={2.2} />
          </div>
        </div>
        <div className="metric-card-content">
          <div className="metric-card-value-row">
            <span className="metric-card-value">{formatNumber(unreconciled)}</span>
          </div>
          <div className="metric-card-bottom">
            <span className="metric-card-badge warning">Needs review</span>
            <span className="metric-card-subtext">attention required</span>
          </div>
        </div>
      </article>

      {/* 4. Reconciliation Rate */}
      <article className="metric-card metric-card-indigo">
        <div className="metric-card-top">
          <span className="metric-card-label">Reconciliation rate</span>
          <div className="metric-card-icon" aria-hidden="true">
            <ShieldCheck size={16} strokeWidth={2.2} />
          </div>
        </div>
        <div className="metric-card-content">
          <div className="metric-card-value-row">
            <span className="metric-card-value">{reconPctFormatted}</span>
            {reconPctFormatted !== "—" && (
              <span className="metric-card-percent-mark">%</span>
            )}
          </div>
          <div className="metric-card-bottom">
            <span className="metric-card-badge positive">High accuracy</span>
            <span className="metric-card-subtext">Tier 1 + 3 combined</span>
          </div>
        </div>
      </article>

      {/* 5. Exception Rate */}
      <article className="metric-card metric-card-rose">
        <div className="metric-card-top">
          <span className="metric-card-label">Exception rate</span>
          <div className="metric-card-icon" aria-hidden="true">
            <AlertCircle size={16} strokeWidth={2.2} />
          </div>
        </div>
        <div className="metric-card-content">
          <div className="metric-card-value-row">
            <span className="metric-card-value">{excPctFormatted}</span>
            {excPctFormatted !== "—" && (
              <span className="metric-card-percent-mark">%</span>
            )}
          </div>
          <div className="metric-card-bottom">
            <span className="metric-card-badge warning">
              {formatNumber(unreconciled)} exceptions
            </span>
            <span className="metric-card-subtext">pipeline breaks</span>
          </div>
        </div>
      </article>
    </section>
  );
}

export default MetricsCards;