import {
    PieChart,
    Pie,
    Cell,
    Tooltip,
    Legend,
    ResponsiveContainer,
  } from "recharts";
  
  // Static color palette for exception categories, cycled by index.
  // Purely a display concern — does not affect categorization, which
  // is owned entirely by the backend's categorizer.py.
  const CATEGORY_COLORS = [
    "#dc2626", // red
    "#f59e0b", // amber
    "#2563eb", // blue
    "#7c3aed", // violet
    "#0d9488", // teal
    "#db2777", // pink
    "#65a30d", // lime
  ];
  
  const FALLBACK_CATEGORY_LABEL = "Uncategorized";
  
  /**
   * ExceptionBreakdown
   * Purely presentational Recharts visualization showing the distribution
   * of reconciliation exceptions by category.
   *
   * The backend (categorizer.py) is the single source of truth for what
   * category each exception belongs to. This component only counts how
   * many already-categorized exceptions fall into each category label,
   * for chart rendering — it does not perform any reconciliation,
   * matching, or categorization logic itself.
   *
   * Props:
   * - exceptions: Array<{
   *     category?: string,   // e.g. "AMOUNT_MISMATCH", "MISSING_IN_BANK"
   *     ...other exception fields (ignored by this component)
   *   }>
   */
  function ExceptionBreakdown({ exceptions = [] }) {
    const categoryCounts = exceptions.reduce((counts, exception) => {
      const category = exception?.category || FALLBACK_CATEGORY_LABEL;
      counts[category] = (counts[category] || 0) + 1;
      return counts;
    }, {});
  
    const chartData = Object.entries(categoryCounts).map(([category, count]) => ({
      name: category,
      value: count,
    }));
  
    const hasData = chartData.length > 0;
  
    return (
      <div className="exception-breakdown">
        <div className="exception-breakdown-header">
          <span className="exception-breakdown-title">
            Exception Breakdown by Category
          </span>
        </div>
  
        <div className="exception-breakdown-body">
          {hasData ? (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={chartData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  label
                >
                  {chartData.map((entry, index) => (
                    <Cell
                      key={entry.name}
                      fill={CATEGORY_COLORS[index % CATEGORY_COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="exception-breakdown-empty">
              No exceptions to display
            </div>
          )}
        </div>
      </div>
    );
  }
  
  export default ExceptionBreakdown;