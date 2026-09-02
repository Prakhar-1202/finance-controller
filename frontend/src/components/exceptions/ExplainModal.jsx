import React, { useState, useEffect } from "react";
import { X, Sparkles, AlertTriangle, CheckCircle2, RefreshCw } from "lucide-react";
import { explainException } from "../../services/api";

function formatINR(val) {
  if (val === undefined || val === null || val === "") return null;
  const num = Number(val);
  return Number.isNaN(num) ? String(val) : `₹${num.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function ExplainModal({ exceptionContext = null, onClose = () => {} }) {
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!exceptionContext) return;

    let isMounted = true;
    (async () => {
      setIsLoading(true);
      setError(null);
      try {
        const payload = {
          detected_category: exceptionContext.detected_category || exceptionContext.category || "unmatched",
          order_id: exceptionContext.order_id,
          bank_ref: exceptionContext.bank_ref,
          bank_amount: exceptionContext.amount ? Number(exceptionContext.amount) : undefined,
          settled_sum: exceptionContext.settled_sum ? Number(exceptionContext.settled_sum) : undefined,
          diff: exceptionContext.diff ? Number(exceptionContext.diff) : undefined,
          narration: exceptionContext.narration,
        };

        const res = await explainException(payload);
        if (isMounted) {
          setResult(res);
        }
      } catch (err) {
        if (isMounted) {
          setError(err.message || "Failed to generate exception explanation");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    })();

    return () => {
      isMounted = false;
    };
  }, [exceptionContext]);

  if (!exceptionContext) return null;

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "8px",
                background: "rgba(12, 159, 154, 0.12)",
                color: "#0C9F9A",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Sparkles size={16} />
            </div>
            <div>
              <h2 className="modal-title">AI Exception Reasoner</h2>
              <p style={{ fontSize: "11px", color: "#5A6A85" }}>
                Root-cause intelligence for {exceptionContext.bank_ref || exceptionContext.order_id || "batch"}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ color: "#7587a7", padding: "6px", borderRadius: "6px" }}
            aria-label="Close dialog"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body">
          {isLoading ? (
            <div style={{ padding: "40px 0", textAlign: "center", color: "#5A6A85" }}>
              <div style={{ display: "inline-flex", alignItems: "center", gap: "10px" }}>
                <RefreshCw size={18} className="spinning" style={{ animation: "spin 0.8s linear infinite" }} />
                <span>Synthesizing exception context...</span>
              </div>
            </div>
          ) : error ? (
            <div
              style={{
                padding: "16px",
                background: "rgba(217, 87, 104, 0.1)",
                borderRadius: "8px",
                color: "#D95768",
                fontSize: "13px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                <AlertTriangle size={16} />
                <strong>Reasoning Error</strong>
              </div>
              <p>{error}</p>
            </div>
          ) : result ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {/* Category & Confidence Header */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "10px 14px",
                  background: "#F7F9FC",
                  borderRadius: "8px",
                  border: "1px solid #E6EBF1",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ fontSize: "12px", color: "#5A6A85", fontWeight: 500 }}>Category:</span>
                  <span
                    style={{
                      fontSize: "12px",
                      fontWeight: 700,
                      color: "#15233A",
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                    }}
                  >
                    {result.category}
                  </span>
                </div>
                <div
                  style={{
                    fontSize: "11px",
                    fontWeight: 600,
                    padding: "2px 8px",
                    borderRadius: "4px",
                    background: result.confidence === "high" ? "rgba(20, 155, 117, 0.1)" : "rgba(213, 138, 32, 0.1)",
                    color: result.confidence === "high" ? "#149B75" : "#D58A20",
                  }}
                >
                  {result.confidence ? `${result.confidence.toUpperCase()} CONFIDENCE` : "VALIDATED"}
                </div>
              </div>

              {/* Explanation Box */}
              <div>
                <span style={{ fontSize: "11px", fontWeight: 700, color: "#5A6A85", textTransform: "uppercase", letterSpacing: "0.06em", display: "block", marginBottom: "4px" }}>
                  Explanation
                </span>
                <p style={{ fontSize: "13px", color: "#15233A", lineHeight: 1.5, background: "#FFFFFF", padding: "12px", borderRadius: "8px", border: "1px solid #E6EBF1" }}>
                  {result.explanation}
                </p>
              </div>

              {/* Likely Cause */}
              {result.likely_cause && (
                <div>
                  <span style={{ fontSize: "11px", fontWeight: 700, color: "#5A6A85", textTransform: "uppercase", letterSpacing: "0.06em", display: "block", marginBottom: "4px" }}>
                    Likely Root Cause
                  </span>
                  <p style={{ fontSize: "13px", color: "#15233A", lineHeight: 1.5 }}>
                    {result.likely_cause}
                  </p>
                </div>
              )}

              {/* Suggested Action */}
              {result.suggested_action && (
                <div
                  style={{
                    padding: "14px",
                    background: "rgba(12, 159, 154, 0.08)",
                    border: "1px solid rgba(12, 159, 154, 0.2)",
                    borderRadius: "8px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#0C9F9A", fontWeight: 600, fontSize: "12px", marginBottom: "4px" }}>
                    <CheckCircle2 size={15} />
                    <span>Recommended Controller Action</span>
                  </div>
                  <p style={{ fontSize: "13px", color: "#15233A", lineHeight: 1.4 }}>
                    {result.suggested_action}
                  </p>
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default ExplainModal;
