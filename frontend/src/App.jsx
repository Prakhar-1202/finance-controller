import { useState } from "react";
import Sidebar from "./components/layout/Sidebar";
import TopBar from "./components/layout/TopBar";
import Dashboard from "./pages/Dashboard";
import Transactions from "./pages/Transactions";
import Exceptions from "./pages/Exceptions";

const PAGES = {
  dashboard: Dashboard,
  transactions: Transactions,
  exceptions: Exceptions,
};

const DEFAULT_PAGE = "dashboard";

function App() {
  const [activePage, setActivePage] = useState(DEFAULT_PAGE);

  const ActivePageComponent = PAGES[activePage] || Dashboard;

  return (
    <div className="app-shell">
      <Sidebar activeItem={activePage} onNavigate={setActivePage} />

      <div className="app-main">
        <TopBar activePage={activePage} onNavigate={setActivePage} />

        <main className="app-content">
          <ActivePageComponent onNavigate={setActivePage} />
        </main>
      </div>
    </div>
  );
}

export default App;