import { useState, useEffect, useCallback } from "react";
import { getTransactions } from "../services/api";
import TransactionsTable from "../components/transactions/TransactionsTable";

// Default page size requested from the backend. Purely a UI/query
// concern — pagination itself (what belongs on which page) is decided
// by the backend, not computed here.
const DEFAULT_PAGE_SIZE = 20;

/**
 * Transactions
 * Page that fetches and displays paginated transactions via
 * TransactionsTable. Owns loading, error, data, and pagination state.
 * Fetches exclusively through services/api.js — no direct axios/fetch.
 *
 * Pagination is server-driven: this page only tracks the current
 * `page` and `page_size` it requests, and reads `total`/`page`/
 * `page_size` back from the backend response to decide whether
 * Previous/Next are available. It performs no reconciliation,
 * matching, or categorization logic.
 */
function Transactions() {
  const [items, setItems] = useState([]);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(DEFAULT_PAGE_SIZE);
  const [total, setTotal] = useState(0);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadTransactions = useCallback(async (targetPage) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await getTransactions({
        page: targetPage,
        page_size: pageSize,
      });

      setItems(response?.items || []);
      setTotal(response?.total ?? 0);
      // Trust the backend's reported page in case it clamps/adjusts it.
      setPage(response?.page ?? targetPage);
    } catch (err) {
      setError(err.message || "Failed to load transactions");
    } finally {
      setIsLoading(false);
    }
  }, [pageSize]);

  useEffect(() => {
    loadTransactions(1);
    // Only run on mount; subsequent loads are triggered explicitly
    // by pagination handlers below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const totalPages = total > 0 ? Math.ceil(total / pageSize) : 1;
  const hasPrevious = page > 1;
  const hasNext = page < totalPages;

  const handlePrevious = () => {
    if (hasPrevious && !isLoading) {
      loadTransactions(page - 1);
    }
  };

  const handleNext = () => {
    if (hasNext && !isLoading) {
      loadTransactions(page + 1);
    }
  };

  const handleRetry = () => {
    loadTransactions(page);
  };

  return (
    <div className="transactions-page">
      <div className="transactions-page-header">
        <span className="transactions-page-title">Transactions</span>
      </div>

      {error && (
        <div className="transactions-page-error" role="alert">
          <span>{error}</span>
          <button
            type="button"
            className="transactions-page-error-retry"
            onClick={handleRetry}
            disabled={isLoading}
          >
            Retry
          </button>
        </div>
      )}

      {isLoading ? (
        <div className="transactions-page-loading">Loading transactions...</div>
      ) : (
        <>
          <TransactionsTable transactions={items} />

          <div className="transactions-page-pagination">
            <button
              type="button"
              className="transactions-page-pagination-btn"
              onClick={handlePrevious}
              disabled={!hasPrevious || isLoading}
            >
              Previous
            </button>

            <span className="transactions-page-pagination-info">
              Page {page} of {totalPages} ({total} total)
            </span>

            <button
              type="button"
              className="transactions-page-pagination-btn"
              onClick={handleNext}
              disabled={!hasNext || isLoading}
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export default Transactions;