import React, { useState, useEffect, useRef } from "react";
import {
  Search,
  RefreshCw,
  Bell,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  X,
  Menu,
} from "lucide-react";
import { getExceptions } from "../../services/api";

const PAGE_TITLES = {
  dashboard: "Overview",
  transactions: "Transactions",
  exceptions: "Exceptions",
  reports: "Reports",
  settings: "Settings",
};

function TopBar({
  activePage = "dashboard",
  onNavigate = () => {},
  onSearch = () => {},
  onClearSearch = () => {},
  onOpenSidebar = () => {},
  dataDir = "data",
  datasetVersion = 0,
}) {
  const currentTitle = PAGE_TITLES[activePage] || "Overview";

  // Search state
  const [searchValue, setSearchValue] = useState("");

  // Dropdown states
  const [isNotifOpen, setIsNotifOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  // Real exception data for notifications
  const [exceptionCounts, setExceptionCounts] = useState({
    duplicates: 0,
    drift: 0,
    tier3Orders: 0,
    tier3Batches: 0,
    total: 0,
  });

  const notifRef = useRef(null);
  const profileRef = useRef(null);

  // Load real exception stats for notifications
  useEffect(() => {
    let isMounted = true;
    (async () => {
      try {
        const data = await getExceptions({ data_dir: dataDir });
        if (isMounted && data) {
          const dups = data.duplicate_bank_rows?.length || 0;
          const drifts = data.drift_batches?.length || 0;
          const t3Orders = data.tier3_order_exceptions?.length || 0;
          const t3Batches = data.tier3_batch_report?.length || 0;
          setExceptionCounts({
            duplicates: dups,
            drift: drifts,
            tier3Orders: t3Orders,
            tier3Batches: t3Batches,
            total: dups + drifts + t3Orders + t3Batches,
          });
        }
      } catch {
        // Silently preserve previous counts if error
      }
    })();

    return () => {
      isMounted = false;
    };
  }, [dataDir, datasetVersion]);

  // Click outside to close dropdowns
  useEffect(() => {
    function handleClickOutside(event) {
      if (notifRef.current && !notifRef.current.contains(event.target)) {
        setIsNotifOpen(false);
      }
      if (profileRef.current && !profileRef.current.contains(event.target)) {
        setIsProfileOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (searchValue.trim()) {
      onSearch(searchValue.trim());
    }
  };

  // Reset Search Action
  const handleResetSearch = () => {
    setSearchValue("");
    if (onClearSearch) {
      onClearSearch();
    }
  };

  return (
    <header className="topbar">
      {/* Breadcrumbs & Live System Status */}
      <div className="topbar-left">
        {/* Hamburger — visible only on mobile via CSS */}
        <button
          type="button"
          className="topbar-hamburger"
          onClick={onOpenSidebar}
          title="Open navigation"
          aria-label="Open navigation"
        >
          <Menu size={18} />
        </button>

        <div className="topbar-left-text">
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
      </div>

      {/* Global Actions */}
      <div className="topbar-right">
        {/* 1. GLOBAL SEARCH */}
        <form className="topbar-search-box" onSubmit={handleSearchSubmit}>
          <Search size={14} className="topbar-search-icon" />
          <input
            type="text"
            className="topbar-search-input"
            placeholder="Search orders, customer, UTR..."
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            aria-label="Search orders, customers, and UTRs"
          />
        </form>

        {/* 2. SEARCH RESET BUTTON */}
        <button
          type="button"
          className="topbar-icon-btn topbar-search-reset"
          onClick={handleResetSearch}
          title="Reset search query"
          aria-label="Reset search query"
        >
          <RefreshCw size={15} />
        </button>

        {/* 3. NOTIFICATIONS DROPDOWN */}
        <div className="topbar-popover-wrapper" ref={notifRef}>
          <button
            type="button"
            className="topbar-icon-btn"
            onClick={() => {
              setIsNotifOpen(!isNotifOpen);
              setIsProfileOpen(false);
            }}
            title="Reconciliation Notifications"
            aria-label="Reconciliation Notifications"
            aria-expanded={isNotifOpen}
          >
            <Bell size={15} />
            {exceptionCounts.total > 0 && <span className="topbar-notif-badge" />}
          </button>

          {isNotifOpen && (
            <div className="topbar-popover" role="dialog" aria-label="Notifications Panel">
              <div className="topbar-popover-header">
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <AlertTriangle size={14} color="#D58A20" />
                  <span className="topbar-popover-title">Exception Alerts</span>
                </div>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: "11px",
                    fontWeight: 700,
                    padding: "1px 6px",
                    borderRadius: "4px",
                    background: "rgba(213, 138, 32, 0.12)",
                    color: "#D58A20",
                  }}
                >
                  {exceptionCounts.total} active
                </span>
              </div>

              <div className="topbar-popover-body">
                <div
                  className="topbar-popover-item"
                  onClick={() => {
                    setIsNotifOpen(false);
                    onNavigate("exceptions");
                  }}
                >
                  <div>
                    <strong style={{ color: "#15233A" }}>Duplicate Bank Rows</strong>
                    <div style={{ fontSize: "11px", color: "#5A6A85" }}>Multiple statement entries</div>
                  </div>
                  <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                    {exceptionCounts.duplicates}
                  </span>
                </div>

                <div
                  className="topbar-popover-item"
                  onClick={() => {
                    setIsNotifOpen(false);
                    onNavigate("exceptions");
                  }}
                >
                  <div>
                    <strong style={{ color: "#15233A" }}>Amount Drift Batches</strong>
                    <div style={{ fontSize: "11px", color: "#5A6A85" }}>Net settlement variance</div>
                  </div>
                  <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                    {exceptionCounts.drift}
                  </span>
                </div>

                <div
                  className="topbar-popover-item"
                  onClick={() => {
                    setIsNotifOpen(false);
                    onNavigate("exceptions");
                  }}
                >
                  <div>
                    <strong style={{ color: "#15233A" }}>Tier 3 Order Exceptions</strong>
                    <div style={{ fontSize: "11px", color: "#5A6A85" }}>Controller review queue</div>
                  </div>
                  <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                    {exceptionCounts.tier3Orders}
                  </span>
                </div>

                <div
                  className="topbar-popover-item"
                  onClick={() => {
                    setIsNotifOpen(false);
                    onNavigate("exceptions");
                  }}
                >
                  <div>
                    <strong style={{ color: "#15233A" }}>Batch Reports</strong>
                    <div style={{ fontSize: "11px", color: "#5A6A85" }}>Consolidated batches</div>
                  </div>
                  <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                    {exceptionCounts.tier3Batches}
                  </span>
                </div>
              </div>

              <div className="topbar-popover-footer">
                <button
                  type="button"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "4px",
                    fontSize: "12px",
                    fontWeight: 600,
                    color: "#0C9F9A",
                  }}
                  onClick={() => {
                    setIsNotifOpen(false);
                    onNavigate("exceptions");
                  }}
                >
                  <span>Exceptions Center</span>
                  <ArrowRight size={13} />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* 4. PROFILE BADGE DROPDOWN */}
        <div className="topbar-popover-wrapper" ref={profileRef}>
          <button
            type="button"
            className="topbar-avatar-btn"
            onClick={() => {
              setIsProfileOpen(!isProfileOpen);
              setIsNotifOpen(false);
            }}
            title="Alex Morgan - Finance Controller"
            aria-label="User Profile"
            aria-expanded={isProfileOpen}
          >
            AM
          </button>

          {isProfileOpen && (
            <div className="topbar-popover" style={{ width: "260px" }} role="dialog" aria-label="Profile Panel">
              <div className="topbar-popover-header">
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <div
                    style={{
                      width: "30px",
                      height: "30px",
                      borderRadius: "50%",
                      background: "rgba(11, 31, 58, 0.1)",
                      color: "#0b1f3a",
                      fontWeight: 700,
                      fontSize: "11px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    AM
                  </div>
                  <div>
                    <div style={{ fontSize: "13px", fontWeight: 600, color: "#15233A" }}>Alex Morgan</div>
                    <div style={{ fontSize: "11px", color: "#5A6A85" }}>Finance controller</div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setIsProfileOpen(false)}
                  style={{ color: "#7587a7", padding: "4px" }}
                  aria-label="Close"
                >
                  <X size={14} />
                </button>
              </div>

              <div style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: "8px", fontSize: "12px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", color: "#5A6A85" }}>
                  <span>Workspace:</span>
                  <strong style={{ color: "#15233A" }}>Finance Ops</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", color: "#5A6A85" }}>
                  <span>Permissions:</span>
                  <span style={{ color: "#149B75", fontWeight: 600 }}>Full Controller</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", color: "#5A6A85" }}>
                  <span>Status:</span>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: "4px", color: "#149B75", fontWeight: 500 }}>
                    <CheckCircle2 size={12} /> Active
                  </span>
                </div>
              </div>

              <div className="topbar-popover-footer" style={{ justifyContent: "flex-end" }}>
                <button
                  type="button"
                  className="btn-secondary"
                  style={{ height: "30px", padding: "0 10px", fontSize: "11.5px" }}
                  onClick={() => setIsProfileOpen(false)}
                >
                  Close
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

export default TopBar;