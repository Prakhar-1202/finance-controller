import React, { useState, useEffect, useCallback } from "react";
import { Download, Search, Filter, ChevronLeft, ChevronRight, RefreshCw, AlertCircle } from "lucide-react";
import { getTransactions } from "../services/api";
import TransactionsTable from "../components/transactions/TransactionsTable";

const DEFAULT_PAGE_SIZE = 20;

const STATUS_OPTIONS = [
  { value: "all", label: "All statuses" },
  { value: "reconciled", label: "Reconciled" },
  { value: "orphan_ledger", label: "Orphan Ledger" },
  { value: "orphan_settlement", label: "Orphan Settlement" },
  { value: "exception", label: "Exceptions" },
];

function Transactions() {
  const [items, setItems] = useState([]);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(DEFAULT_PAGE_SIZE);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadTransactions = useCallback(async (targetPage, currentStatus) => {
    setIsLoading(true);
    setError(null);

    try {
      const params = {
        page: targetPage,
        page_size: pageSize,
      };
      if (currentStatus && currentStatus !== "all") {
        params.status = currentStatus;
      }

      const response = await getTransactions(params);
      setItems(response?.items || []);
      setTotal(response?.total ?? 0);
      setPage(response?.page ?? targetPage);
    } catch (err) {
      setError(err.message || "Failed to load transactions");
    } finally {
      setIsLoading(false);
    }
  }, [pageSize]);

  useEffect(() => {
    loadTransactions(1, statusFilter);
  }, [loadTransactions, statusFilter]);

  const totalPages = total > 0 ? Math.ceil(total / pageSize) : 1;
  const startIdx = total > 0 ? (page - 1) * pageSize + 1 : 0;
  const endIdx = Math.min(page * pageSize, total);

  const handlePrevious = () => {
    if (page > 1 && !isLoading) {
      loadTransactions(page - 1, statusFilter);
    }
  };

  const handleNext = () => {
    if (page < totalPages && !isLoading) {
      loadTransactions(page + 1, statusFilter);
    }
  };

  // Client-side search across order_id, customer, and utr
  const filteredItems = items.filter((item) => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    return (
      (item.order_id && String(item.order_id).toLowerCase().includes(term)) ||
      (item.customer && String(item.customer).toLowerCase().includes(term)) ||
      (item.utr && String(item.utr).toLowerCase().includes(term)) ||
      (item.category && String(item.category).toLowerCase().includes(term))
    );
  });

  const exportCSV = () => {
    if (!items.length) return;
    const headers = ["Order ID", "Customer", "Invoice Amount", "Net Amount", "Status", "Tier", "Category", "UTR", "Created At"];
    const rows = filteredItems.map((i) => [
      i.order_id || "",
      i.customer || "",
      i.invoice_amount || "",
      i.net_amount || "",
      i.reconciliation_status || "",
      i.tier || "",
      i.category || "",
      i.utr || "",
      i.created_at || "",
    ]);
    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `transactions_page_${page}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="transactions-page">
      {/* Unified Page Header */}
      <div className="page-header">
        <div>
          <div className="page-header-pre">Transaction Ledger</div>
          <h1 className="page-header-title">All transactions</h1>
          <p className="page-header-desc">
            Review, filter, and trace every order in the reconciliation cycle.
          </p>
        </div>

        <div className="page-header-actions">
          <button
            type="button"
            className="btn-primary"
            onClick={exportCSV}
            title="Export current page transactions as CSV"
          >
            <Download size={14} />
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="alert-banner alert-banner-error" role="alert">
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
          <button
            type="button"
            className="alert-banner-btn"
            onClick={() => loadTransactions(page, statusFilter)}
          >
            Retry
          </button>
        </div>
      )}

      {/* Table Card Container */}
      <div className="stitch-card">
        {/* Table Toolbar */}
        <div className="table-toolbar">
          <div className="table-toolbar-left">
            <div className="table-toolbar-search">
              <Search
                size={14}
                style={{
                  position: "absolute",
                  left: "11px",
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: "#8896AB",
                }}
              />
              <input
                type="text"
                className="topbar-search-input"
                placeholder="Search order, customer, UTR..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>

            <select
              className="table-toolbar-select"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              aria-label="Filter transactions by reconciliation status"
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <button
              type="button"
              className="btn-secondary"
              style={{ height: "36px", padding: "0 12px", fontSize: "12.5px" }}
              onClick={() => loadTransactions(page, statusFilter)}
            >
              <Filter size={14} />
              <span>Filters</span>
            </button>
          </div>
        </div>

        {/* Data Table */}
        {isLoading ? (
          <div style={{ padding: "48px 0", textAlign: "center", color: "#5A6A85" }}>
            <div style={{ display: "inline-flex", alignItems: "center", gap: "10px" }}>
              <RefreshCw size={18} className="spinning" style={{ animation: "spin 0.8s linear infinite" }} />
              <span>Loading ledger data...</span>
            </div>
          </div>
        ) : (
          <TransactionsTable transactions={filteredItems} />
        )}

        {/* Pagination Footer */}
        <div className="table-pagination-footer">
          <div className="pagination-text">
            Showing <strong>{startIdx}–{endIdx}</strong> of <strong>{total.toLocaleString()}</strong> transactions
          </div>

          <div className="pagination-controls">
            <button
              type="button"
              className="pagination-btn"
              onClick={handlePrevious}
              disabled={page <= 1 || isLoading}
              title="Previous page"
              aria-label="Previous page"
            >
              <ChevronLeft size={15} />
            </button>

            <button type="button" className="pagination-btn active">
              {page}
            </button>

            <button
              type="button"
              className="pagination-btn"
              onClick={handleNext}
              disabled={page >= totalPages || isLoading}
              title="Next page"
              aria-label="Next page"
            >
              <ChevronRight size={15} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Transactions;