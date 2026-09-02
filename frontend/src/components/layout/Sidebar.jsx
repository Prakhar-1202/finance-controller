import React from "react";
import {
  Shield,
  LayoutDashboard,
  Receipt,
  AlertTriangle,
  BarChart3,
  Settings,
  ChevronDown,
  CheckCircle2,
  MoreHorizontal,
} from "lucide-react";

const MONITOR_ITEMS = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "transactions", label: "Transactions", icon: Receipt },
  { key: "exceptions", label: "Exceptions", icon: AlertTriangle, warningBadge: true },
];

const WORKSPACE_ITEMS = [
  { key: "reports", label: "Reports", icon: BarChart3 },
  { key: "settings", label: "Settings", icon: Settings },
];

function Sidebar({ activeItem = "dashboard", onNavigate = () => {} }) {
  return (
    <aside className="sidebar" aria-label="Main Navigation">
      {/* Brand Header */}
      <div className="sidebar-header">
        <div className="sidebar-brand-icon">
          <Shield size={20} strokeWidth={2.5} />
        </div>
        <div className="sidebar-brand-titles">
          <span className="sidebar-brand-title">LedgerLens</span>
          <span className="sidebar-brand-subtitle">Controller workspace</span>
        </div>
      </div>

      {/* Workspace Selector */}
      <button type="button" className="sidebar-workspace-btn" title="Current Workspace">
        <div className="sidebar-workspace-left">
          <div className="sidebar-workspace-avatar">F</div>
          <div className="sidebar-workspace-text">
            <span className="sidebar-workspace-tag">Workspace</span>
            <span className="sidebar-workspace-name">Finance Ops</span>
          </div>
        </div>
        <ChevronDown size={15} color="#7587a7" />
      </button>

      {/* Navigation Sections */}
      <nav className="sidebar-nav">
        <div className="sidebar-section-label">Monitor</div>
        {MONITOR_ITEMS.map(({ key, label, icon: Icon, warningBadge }) => {
          const isActive = key === activeItem;
          return (
            <button
              key={key}
              type="button"
              className={`sidebar-nav-item${isActive ? " active" : ""}`}
              aria-current={isActive ? "page" : undefined}
              onClick={() => onNavigate(key)}
            >
              <div className="sidebar-nav-item-left">
                <Icon size={18} strokeWidth={isActive ? 2.2 : 1.8} />
                <span>{label}</span>
              </div>
            </button>
          );
        })}

        <div className="sidebar-section-label" style={{ marginTop: "12px" }}>
          Workspace
        </div>
        {WORKSPACE_ITEMS.map(({ key, label, icon: Icon }) => {
          const isActive = key === activeItem;
          return (
            <button
              key={key}
              type="button"
              className={`sidebar-nav-item${isActive ? " active" : ""}`}
              aria-current={isActive ? "page" : undefined}
              onClick={() => onNavigate(key)}
            >
              <div className="sidebar-nav-item-left">
                <Icon size={18} strokeWidth={1.8} />
                <span>{label}</span>
              </div>
            </button>
          );
        })}
      </nav>

      {/* Sidebar Footer */}
      <div className="sidebar-footer">
        <div className="sidebar-sync-status">
          <CheckCircle2 size={15} color="#149B75" />
          <span>Sync is healthy</span>
        </div>

        <div className="sidebar-user-card">
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div className="sidebar-user-avatar">AM</div>
            <div className="sidebar-user-info">
              <span className="sidebar-user-name">Alex Morgan</span>
              <span className="sidebar-user-role">Finance controller</span>
            </div>
          </div>
          <MoreHorizontal size={16} color="#7587a7" />
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;