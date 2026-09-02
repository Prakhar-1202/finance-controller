import React from "react";

const STATUS_MAP = {
  reconciled: {
    label: "Reconciled",
    className: "reconciled",
  },
  tier3_recovered: {
    label: "Tier 3 Recovered",
    className: "tier3_recovered",
  },
  matched: {
    label: "Reconciled",
    className: "reconciled",
  },
  unreconciled: {
    label: "Unreconciled",
    className: "unreconciled",
  },
  orphan_ledger: {
    label: "Orphan Ledger",
    className: "orphan_ledger",
  },
  orphan_settlement: {
    label: "Orphan Settlement",
    className: "orphan_settlement",
  },
  unmatched: {
    label: "Unreconciled",
    className: "unreconciled",
  },
  exception: {
    label: "Exception",
    className: "exception",
  },
};

const DEFAULT_STATUS = {
  label: "Pending",
  className: "unreconciled",
};

function TransactionStatusBadge({ status }) {
  const normalized = (status || "").toLowerCase();
  const config = STATUS_MAP[normalized] || DEFAULT_STATUS;

  return (
    <span className={`status-pill ${config.className}`}>
      <span className="status-pill-dot" />
      <span>{config.label}</span>
    </span>
  );
}

export default TransactionStatusBadge;