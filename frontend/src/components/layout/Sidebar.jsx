import { LayoutDashboard, ArrowLeftRight, AlertTriangle } from "lucide-react";

// Static nav config — kept outside the component so it isn't
// recreated on every render, and so routing/pages can later reuse
// the same list (labels, keys, icons) without duplicating it.
const NAV_ITEMS = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "transactions", label: "Transactions", icon: ArrowLeftRight },
  { key: "exceptions", label: "Exceptions", icon: AlertTriangle },
];

/**
 * Sidebar
 * Purely presentational navigation sidebar for the reconciliation dashboard.
 *
 * No routing is wired up yet — navigation is controlled entirely via props
 * so this component can later be connected to react-router (or any router)
 * without changing its internals.
 *
 * Props:
 * - activeItem: string   -> key of the currently active nav item (e.g. "dashboard")
 * - onNavigate: function -> callback invoked with the item key when a nav item is clicked
 */
function Sidebar({ activeItem = "dashboard", onNavigate = () => {} }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <span className="sidebar-title">Finance Controller</span>
      </div>

      <nav className="sidebar-nav">
        <ul>
          {NAV_ITEMS.map(({ key, label, icon: Icon }) => {
            const isActive = key === activeItem;
            return (
              <li key={key}>
                <button
                  type="button"
                  className={`sidebar-nav-item${isActive ? " active" : ""}`}
                  aria-current={isActive ? "page" : undefined}
                  onClick={() => onNavigate(key)}
                >
                  <Icon size={18} className="sidebar-nav-icon" />
                  <span>{label}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}

export default Sidebar;