import React from "react";
import { Search, RefreshCw, Bell } from "lucide-react";

const PAGE_TITLES = {
  dashboard: "Overview",
  transactions: "Transactions",
  exceptions: "Exceptions",
  reports: "Reports",
  settings: "Settings",
};

function TopBar({
  activePage = "dashboard",
  onRefresh = () => {},
  isRefreshing = false,
}) {
  const currentTitle = PAGE_TITLES[activePage] || "Overview";

  return (
    <header className="topbar">
      {/* Breadcrumbs & Live System Status */}
      <div className="topbar-left">
        <div className="topbar-breadcrumbs">
          <span className="topbar-breadcrumb-parent">Finance Ops</span>
          <span className="topbar-breadcrumb-sep">/</span>
          <span className="topbar-breadcrumb-current">{currentTitle}</span>
        </div>

        <div className="topbar-status-row">
          <div className="topbar-pulse-indicator">
            <span className="topbar-pulse-dot" />
            <span>All systems operational</span>
          </div>
          <span className="topbar-sync-text">Live sync active</span>
        </div>
      </div>

      {/* Global Actions */}
      <div className="topbar-right">
        <div className="topbar-search-box">
          <Search size={15} className="topbar-search-icon" />
          <input
            type="text"
            className="topbar-search-input"
            placeholder="Search orders, UTRs..."
            aria-label="Search orders and UTRs"
          />
        </div>

        <button
          type="button"
          className="topbar-icon-btn"
          onClick={onRefresh}
          disabled={isRefreshing}
          title="Refresh reconciliation"
          aria-label="Refresh reconciliation"
        >
          <RefreshCw
            size={16}
            className={isRefreshing ? "spinning" : ""}
            style={isRefreshing ? { animation: "spin 0.8s linear infinite" } : {}}
          />
        </button>

        <button
          type="button"
          className="topbar-icon-btn"
          title="Notifications"
          aria-label="Notifications"
        >
          <Bell size={16} />
          <span className="topbar-notif-badge" />
        </button>

        <button
          type="button"
          className="topbar-avatar-btn"
          title="Alex Morgan - Finance Controller"
        >
          AM
        </button>
      </div>
    </header>
  );
}

export default TopBar;