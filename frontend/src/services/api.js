import axios from "axios";

// Central Axios instance for all backend communication.
// Base URL comes from Vite env (VITE_API_BASE_URL) with a local fallback.
const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000, // reconciliation runs can be slow; generous timeout
});

// --- Response/error normalization -------------------------------------
// Every function below returns response.data on success and throws a
// normalized Error on failure, so components/pages never touch Axios
// internals (error.response.data, etc.) directly.
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      "Unexpected API error";
    return Promise.reject(new Error(message));
  }
);

// --- API methods ---------------------------------------------------------
// One function per backend endpoint. No business logic here — just
// request/response plumbing. Pages/components call these directly.

/**
 * Triggers a reconciliation run across ledger, Razorpay, and bank data.
 * @param {object} [payload] - optional reconciliation parameters (date range, etc.)
 */
export async function runReconciliation(payload = {}) {
  const { data } = await apiClient.post("/api/reconcile", payload);
  return data;
}

/**
 * Fetches transactions (matched + unmatched) from the backend.
 * @param {object} [params] - optional query params (filters, pagination)
 */
export async function getTransactions(params = {}) {
  const { data } = await apiClient.get("/api/transactions", { params });
  return data;
}

/**
 * Fetches categorized reconciliation exceptions.
 * @param {object} [params] - optional query params (tier, category, status)
 */
export async function getExceptions(params = {}) {
  const { data } = await apiClient.get("/api/exceptions", { params });
  return data;
}

/**
 * Requests an LLM-generated explanation for a specific exception.
 * @param {object} payload - exception identifier / details required by backend
 */
export async function explainException(payload) {
  const { data } = await apiClient.post("/api/exceptions/explain", payload);
  return data;
}

export default apiClient;