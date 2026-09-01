import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Cell,
  } from "recharts";
  
  // Static color hooks for the two bars. Kept as plain values (not CSS
  // classes) because Recharts requires actual color values via SVG fill
  // props — it cannot resolve CSS classes on internal chart elements.
  const BAR_COLORS = {
    reconciled: "#16a34a",
    unreconciled: "#dc2626",
  };
  
  /**
   * ReconciliationChart
   * Purely presentational bar chart comparing reconciled vs unreconciled
   * orders, built with Recharts.
   *
   * Reads only from the `metrics` prop — performs no calculation beyond
   * shaping the two values into the array Recharts expects. All actual
   * numbers come from the backend (metrics.py).
   *
   * Props:
   * - metrics: {
   *     reconciled_orders: number,
   *     unreconciled_orders: number,
   *     ...other metric fields (ignored by this component)
   *   }
   */
  function ReconciliationChart({ metrics = {} }) {
    const chartData = [
      {
        name: "Reconciled",
        value: metrics.reconciled_orders ?? 0,
        key: "reconciled",
      },
      {
        name: "Unreconciled",
        value: metrics.unreconciled_orders ?? 0,
        key: "unreconciled",
      },
    ];
  
    return (
      <div className="reconciliation-chart">
        <div className="reconciliation-chart-header">
          <span className="reconciliation-chart-title">
            Reconciled vs Unreconciled Orders
          </span>
        </div>
  
        <div className="reconciliation-chart-body">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {chartData.map((entry) => (
                  <Cell key={entry.key} fill={BAR_COLORS[entry.key]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }
  
  export default ReconciliationChart;