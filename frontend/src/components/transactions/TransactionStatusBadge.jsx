import { CheckCircle2, XCircle, AlertTriangle, HelpCircle } from "lucide-react";

// Maps known status values (as returned by the backend) to display
// label, icon, and a CSS class hook. Purely a presentation lookup —
// the backend is the single source of truth for what status a
// transaction actually has.
const STATUS_CONFIG = {
  matched: {
    label: "Matched",
    icon: CheckCircle2,
    className: "status-matched",
  },
  reconciled: {
    label: "Reconciled",
    icon: CheckCircle2,
    className: "status-matched",
  },
  unmatched: {
    label: "Unmatched",
    icon: XCircle,
    className: "status-unmatched",
  },
  unreconciled: {
    label: "Unreconciled",
    icon: XCircle,
    className: "status-unmatched",
  },
  exception: {
    label: "Exception",
    icon: AlertTriangle,
    className: "status-exception",
  },
  pending: {
    label: "Pending",
    icon: HelpCircle,
    className: "status-pending",
  },
};

const DEFAULT_CONFIG = {
  label: "Unknown",
  icon: HelpCircle,
  className: "status-unknown",
};

/**
 * TransactionStatusBadge
 * Small reusable presentational badge for showing a transaction's
 * reconciliation status. Renders an icon + label based purely on the
 * `status` prop — does not determine or infer status itself.
 *
 * Props:
 * - status: string  -> e.g. "matched", "unmatched", "exception", "pending"
 *                       (case-insensitive; unrecognized values fall back
 *                       to a neutral "Unknown" badge)
 */
function TransactionStatusBadge({ status }) {
  const normalizedStatus = (status || "").toLowerCase();
  const config = STATUS_CONFIG[normalizedStatus] || DEFAULT_CONFIG;
  const Icon = config.icon;

  return (
    <span className={`status-badge ${config.className}`}>
      <Icon size={14} className="status-badge-icon" />
      <span className="status-badge-label">{config.label}</span>
    </span>
  );
}

export default TransactionStatusBadge;