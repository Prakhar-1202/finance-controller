import { useState, useEffect, useCallback } from "react";
import { getExceptions } from "../services/api";
import ExceptionBreakdown from "../components/dashboard/ExceptionBreakdown";

// The four exception groups returned by GET /api/exceptions, in display
// order. Labels are for section headings only — the underlying data
// and field names are rendered exactly as the backend returns them.
const EXCEPTION_GROUPS = [
  { key: "duplicate_bank_rows", label: "Duplicate Bank Rows" },
  { key: "drift_batches", label: "Drift Batches" },
  { key: "tier3_order_exceptions", label: "Tier 3 Order Exceptions" },
  { key: "tier3_batch_report", label: "Tier 3 Batch Report" },
];

/**
 * Flattens all four exception groups into one array for
 * ExceptionBreakdown. Pure concatenation — does not read, set, infer,
 * or rewrite any item's `category` field. Each item's `category`
 * (assigned entirely by the backend's categorizer.py) passes through
 * untouched. Non-array groups are skipped rather than guessed at.
 */
function flattenExceptions(exceptionsData) {
  if (!exceptionsData) return [];

  return EXCEPTION_GROUPS.reduce((flattened, group) => {
    const bucket = exceptionsData[group.key];
    if (Array.isArray(bucket)) {
      return flattened.concat(bucket);
    }
    return flattened;
  }, []);
}

/**
 * Renders a single exception item's fields exactly as returned by the
 * backend, without assuming a fixed schema. Every key/value pair on
 * the object is displayed as-is — no field is invented, renamed, or
 * recategorized. Values that are objects/arrays are JSON-stringified
 * purely for readable display.
 */
function ExceptionItemFields({ item }) {
  const entries = Object.entries(item || {});

  return (
    <dl className="exception-item-fields">
      {entries.map(([fieldKey, fieldValue]) => {
        const displayValue =
          fieldValue !== null && typeof fieldValue === "object"
            ? JSON.stringify(fieldValue)
            : String(fieldValue ?? "—");

        return (
          <div key={fieldKey} className="exception-item-field">
            <dt className="exception-item-field-key">{fieldKey}</dt>
            <dd className="exception-item-field-value">{displayValue}</dd>
          </div>
        );
      })}
    </dl>
  );
}

/**
 * Exceptions
 * Page that fetches and displays reconciliation exceptions grouped
 * exactly as returned by GET /api/exceptions. Owns loading, error, and
 * data state. Fetches exclusively through services/api.js.
 *
 * All backend fields and category values are displayed as-is — this
 * page performs no reconciliation, matching, categorization, or
 * recategorization of any kind.
 */
function Exceptions() {
  const [exceptionsData, setExceptionsData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadExceptions = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await getExceptions();
      setExceptionsData(response || {});
    } catch (err) {
      setError(err.message || "Failed to load exceptions");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadExceptions();
  }, [loadExceptions]);

  const flattenedForChart = flattenExceptions(exceptionsData);

  return (
    <div className="exceptions-page">
      <div className="exceptions-page-header">
        <span className="exceptions-page-title">Exceptions</span>
      </div>

      {error && (
        <div className="exceptions-page-error" role="alert">
          <span>{error}</span>
          <button
            type="button"
            className="exceptions-page-error-retry"
            onClick={loadExceptions}
            disabled={isLoading}
          >
            Retry
          </button>
        </div>
      )}

      {isLoading ? (
        <div className="exceptions-page-loading">Loading exceptions...</div>
      ) : (
        <>
          <section className="exceptions-page-section">
            <ExceptionBreakdown exceptions={flattenedForChart} />
          </section>

          {EXCEPTION_GROUPS.map((group) => {
            const items = exceptionsData?.[group.key];
            const groupItems = Array.isArray(items) ? items : [];
            const hasItems = groupItems.length > 0;

            return (
              <section key={group.key} className="exceptions-page-section">
                <div className="exception-group-header">
                  <span className="exception-group-title">{group.label}</span>
                  <span className="exception-group-count">
                    {groupItems.length}
                  </span>
                </div>

                {hasItems ? (
                  <ul className="exception-group-list">
                    {groupItems.map((item, index) => (
                      <li
                        key={item.order_id ?? item.id ?? `${group.key}-${index}`}
                        className="exception-group-item"
                      >
                        <ExceptionItemFields item={item} />
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="exception-group-empty">
                    No {group.label.toLowerCase()} to display
                  </div>
                )}
              </section>
            );
          })}
        </>
      )}
    </div>
  );
}

export default Exceptions;