import { useState } from "react";
import Sidebar from "./components/layout/Sidebar";
import TopBar from "./components/layout/TopBar";
import Dashboard from "./pages/Dashboard";
import Transactions from "./pages/Transactions";
import Exceptions from "./pages/Exceptions";

// Maps each nav key (used by Sidebar) to the page component it renders.
// Kept as config so adding a page later means adding one entry here,
// not touching the render/navigation logic below.
const PAGES = {
  dashboard: Dashboard,
  transactions: Transactions,
  exceptions: Exceptions,
};

const DEFAULT_PAGE = "dashboard";

/**
 * App
 * Top-level shell that composes the persistent layout (Sidebar, TopBar)
 * with simple state-based page switching. No React Router — the active
 * page is tracked with useState and passed to Sidebar for highlighting.
 *
 * No API calls or business logic live here: each page (Dashboard,
 * Transactions, Exceptions) owns its own data fetching and state
 * independently, exactly as already built.
 */
function App() {
  const [activePage, setActivePage] = useState(DEFAULT_PAGE);

  const ActivePageComponent = PAGES[activePage] || Dashboard;

  return (
    <div className="app-shell">
      <Sidebar activeItem={activePage} onNavigate={setActivePage} />

      <div className="app-main">
        <TopBar />

        <main className="app-content">
          <ActivePageComponent />
        </main>
      </div>
    </div>
  );
}

export default App;