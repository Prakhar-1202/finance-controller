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
const DEFAULT_DATA_DIR = "data";

function App() {
  const [activePage, setActivePage] = useState(DEFAULT_PAGE);
  const [searchQuery, setSearchQuery] = useState("");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [dataDir, setDataDir] = useState(DEFAULT_DATA_DIR);
  const [datasetVersion, setDatasetVersion] = useState(0);

  const handleGlobalSearch = (query) => {
    setSearchQuery(query);
    setActivePage("transactions");
  };

  const handleClearSearch = () => {
    setSearchQuery("");
  };

  const handleDatasetUploaded = (uploadResponse) => {
    if (uploadResponse?.data_dir) {
      setDataDir(uploadResponse.data_dir);
    }
    setDatasetVersion((version) => version + 1);
  };

  const ActivePageComponent = PAGES[activePage] || Dashboard;

  return (
    <div className="app-shell">
      <Sidebar
        activeItem={activePage}
        onNavigate={setActivePage}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
      />

      <div className="app-main">
        <TopBar
          activePage={activePage}
          onNavigate={setActivePage}
          onSearch={handleGlobalSearch}
          onClearSearch={handleClearSearch}
          onOpenSidebar={() => setIsSidebarOpen(true)}
          dataDir={dataDir}
          datasetVersion={datasetVersion}
        />

        <main className="app-content">
          <ActivePageComponent
            onNavigate={setActivePage}
            searchQuery={activePage === "transactions" ? searchQuery : ""}
            dataDir={dataDir}
            datasetVersion={datasetVersion}
            onDatasetUploaded={handleDatasetUploaded}
          />
        </main>
      </div>
    </div>
  );
}

export default App;