import {
    ListOrdered,
    CheckCircle2,
    AlertCircle,
    Percent,
    TrendingDown,
  } from "lucide-react";
  
  // Static card config — maps each metric to its label, icon, and the
  // key it reads from the `metrics` prop. Kept outside the component so
  // it isn't recreated on every render and is easy to extend later.
  const CARD_CONFIG = [
    {
      key: "total_orders",
      label: "Total Orders",
      icon: ListOrdered,
    },
    {
      key: "reconciled_orders",
      label: "Reconciled Orders",
      icon: CheckCircle2,
    },
    {
      key: "unreconciled_orders",
      label: "Unreconciled Orders",
      icon: AlertCircle,
    },
    {
      key: "reconciliation_rate",
      label: "Reconciliation Rate",
      icon: Percent,
    },
    {
      key: "exception_rate",
      label: "Exception Rate",
      icon: TrendingDown,
    },
  ];
  
  // Keys whose values are rates/percentages rather than raw counts,
  // used only to decide display formatting — no calculation happens here.
  const RATE_KEYS = new Set(["reconciliation_rate", "exception_rate"]);
  
  /**
   * MetricsCards
   * Purely presentational grid of reconciliation metric cards.
   *
   * Displays exactly what is passed in via `metrics`. Does not fetch data,
   * compute derived values, or manage any state — the backend (metrics.py)
   * is the single source of truth for these numbers.
   *
   * Props:
   * - metrics: {
   *     total_orders: number,
   *     reconciled_orders: number,
   *     unreconciled_orders: number,
   *     reconciliation_rate: number, // e.g. 96.4 (percent)
   *     exception_rate: number,      // e.g. 3.6 (percent)
   *   }
   */
  function MetricsCards({ metrics = {} }) {
    return (
      <div className="metrics-cards">
        {CARD_CONFIG.map(({ key, label, icon: Icon }) => {
          const rawValue = metrics[key];
          const hasValue = rawValue !== undefined && rawValue !== null;
          const displayValue = hasValue
            ? RATE_KEYS.has(key)
              ? `${rawValue}%`
              : rawValue
            : "—";
  
          return (
            <div key={key} className="metric-card" data-metric={key}>
              <div className="metric-card-icon">
                <Icon size={20} />
              </div>
              <div className="metric-card-content">
                <span className="metric-card-label">{label}</span>
                <span className="metric-card-value">{displayValue}</span>
              </div>
            </div>
          );
        })}
      </div>
    );
  }
  
  export default MetricsCards;