import { RefreshCw, CheckCircle2 } from "lucide-react";

/**
 * TopBar
 * Purely presentational top navigation bar for the reconciliation dashboard.
 *
 * No routing, no API calls — refresh behavior and loading state are fully
 * controlled by the parent via props, so this can be wired to a real
 * reconciliation trigger (or polling) later without changing this file.
 *
 * Props:
 * - onRefresh: function  -> callback invoked when the refresh button is clicked
 * - isRefreshing: boolean -> when true, disables the button and shows a spinning icon
 */
function TopBar({ onRefresh = () => {}, isRefreshing = false }) {
  return (
    <header className="topbar">
      <div className="topbar-titles">
        <h1 className="topbar-title">Finance Controller</h1>
        <p className="topbar-subtitle">
          Reconciliation &amp; Monitoring Dashboard
        </p>
      </div>

      <div className="topbar-actions">
        <div className="topbar-status" role="status">
          <CheckCircle2 size={16} className="topbar-status-icon" />
          <span>System Operational</span>
        </div>

        <button
          type="button"
          className="topbar-refresh-btn"
          onClick={onRefresh}
          disabled={isRefreshing}
          aria-busy={isRefreshing}
        >
          <RefreshCw
            size={16}
            className={`topbar-refresh-icon${isRefreshing ? " spinning" : ""}`}
          />
          <span>{isRefreshing ? "Refreshing..." : "Refresh"}</span>
        </button>
      </div>
    </header>
  );
}

export default TopBar;