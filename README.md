# Finance Controller

An automated financial reconciliation system that matches **internal ledger**, **Razorpay settlement**, and **bank statement** data through a tiered, deterministic-first reconciliation pipeline. It identifies discrepancies, categorizes exceptions, and provides an optional LLM-powered explanation layer for human review.

### 🔗 Links

* **Live Demo:** https://finance-controller-ebon.vercel.app/
* **Backend API:** https://finance-controller-58zn.onrender.com/
* **API Docs:** https://finance-controller-58zn.onrender.com/docs
* **Source Code:** https://github.com/Prakhar-1202/finance-controller

---

## Overview

Financial reconciliation often requires comparing records from multiple independent sources:

* **Internal Ledger** — what the business invoiced and expects to receive
* **Razorpay Settlement** — what the payment gateway reports as settled
* **Bank Statement** — what actually reached the bank account

These sources can contain missing records, duplicate transactions, amount differences, or unreliable references.

Finance Controller automates this process using a multi-tier reconciliation pipeline. Strong matches are resolved deterministically first, while ambiguous cases are progressively analyzed and surfaced as exceptions instead of being silently ignored.

The system also provides a React dashboard where finance users can monitor reconciliation health, inspect transactions, investigate exceptions, and upload new datasets.

---

## Key Features

* **Three-source reconciliation** across ledger, Razorpay settlement, and bank statement data
* **Tiered reconciliation pipeline** using exact matching, heuristic analysis, batch matching, and exception categorization
* **Duplicate bank transaction detection**
* **Amount drift classification** for small fee, GST, and rounding differences
* **Subset-sum matching** for reconstructing settlement batches when reference-based matching is unreliable
* **Order-level exception recovery** so one problematic order does not automatically invalidate an entire batch
* **Optional LLM-powered exception explanations** with deterministic fallback reasoning
* **CSV dataset upload** for testing different financial datasets without redeploying
* **Transaction explorer** with search, filtering, status indicators, and pagination
* **Exception dashboard** with categories, confidence levels, and explanations
* **Reconciliation metrics dashboard** with reconciliation and exception rates
* **Precision/recall evaluation** against a ground-truth dataset
* **Synthetic dataset generator** for creating test data with known outcomes

---

## Reconciliation Pipeline

The reconciliation engine uses a tiered approach so that high-confidence matches are resolved first and uncertain cases are progressively investigated.

### Tier 1 — Exact Matching

The first tier performs deterministic, high-confidence matching.

#### Ledger → Razorpay Settlement

Transactions are matched using `order_id`.

This determines whether an order present in the internal ledger also appears in the payment gateway settlement data.

#### Razorpay Settlement → Bank Statement

Settlement records are grouped by `utr` and compared with bank statement rows using `bank_ref`.

A batch is considered clean only when:

1. Exactly one bank row has the corresponding reference.
2. The settlement `net_amount` sum matches the bank amount within the strict ₹0.02 tolerance.

Records that fail these checks are passed to the next tier rather than being discarded.

---

### Tier 2 — Heuristic and Batch Matching

Tier 2 handles cases that cannot be safely resolved through exact matching.

It includes:

#### Duplicate Detection

Bank rows sharing the same `(bank_ref, amount)` are flagged as potential duplicate postings.

The system does not silently delete them. They remain visible so a finance controller can review them.

#### Amount Drift Classification

Small differences between the settlement total and bank amount are classified as potential fee, GST, or rounding drift.

The current implementation uses:

* **1% relative tolerance**
* **₹50 absolute cap**

Larger unexplained differences remain unresolved.

#### Subset-Sum Matching

When a bank transaction cannot be reliably matched using a reference key, the system searches for a subset of settlement rows whose `net_amount` values sum to the bank amount within ₹0.02 tolerance.

The search is intentionally bounded to a maximum of 15 candidate items to avoid unrestricted exponential search.

---

### Tier 3 — Batch Decomposition

Tier 3 revisits unresolved settlement batches at the order level.

It attempts to:

1. Reconcile batches after removing flagged duplicate bank postings.
2. Accept immaterial fee or rounding drift.
3. Identify a small subset of problematic orders whose exclusion makes the remaining batch reconcile.
4. Leave the entire batch unresolved when no safe resolution is available.

This prevents one problematic order from causing every otherwise valid order in the same settlement batch to appear unreconciled.

All recovered and excluded orders remain visible in the reconciliation results with their associated reason.

---

### Tier 4 — LLM Exception Explanation

The LLM layer is **not responsible for deciding whether a transaction reconciles**.

Instead, it receives an exception that has already been detected and classified by the deterministic pipeline and generates a structured explanation containing:

* Category
* Explanation
* Likely cause
* Suggested action
* Confidence

The LLM provider uses an OpenAI-compatible chat-completions API.

If no LLM API key is configured, the system automatically falls back to deterministic, template-based explanations.

This keeps reconciliation outcomes independent of the LLM.

---

## Dataset Upload

The dashboard supports uploading a new set of three CSV files:

```text
bank_statement.csv
razorpay_settlement.csv
internal_ledger.csv
```

The backend validates all three files before writing anything to disk.

### Required columns

**Bank Statement**

```text
txn_date
narration
amount
bank_ref
```

**Razorpay Settlement**

```text
settlement_id
order_id
gross_amount
fee
tax_on_fee
net_amount
settled_at
utr
```

**Internal Ledger**

```text
invoice_id
order_id
invoice_amount
customer
status
created_at
```

Each uploaded dataset is stored in a unique directory under:

```text
data/uploads/<dataset-id>/
```

The generated dataset directory is then used by the reconciliation pipeline as the active dataset for the current session.

Invalid CSV files or missing required columns are rejected before the dataset is written.

---

## Dashboard

The React frontend provides:

* Reconciliation KPI cards
* Reconciliation health visualization
* Exception breakdown
* Recent activity
* Transaction search and filtering
* Paginated transaction table
* Exception investigation
* LLM/fallback explanation modal
* Dataset upload
* Pipeline re-run
* Export functionality
* Responsive desktop and mobile layouts

---

## Architecture

```text
                        User Browser
                             |
                             v
                    React + Vite Frontend
                             |
                             | REST API
                             v
                       FastAPI Backend
                             |
                             v
                    Reconciliation Pipeline
                             |
              +--------------+--------------+
              |              |              |
              v              v              v
        Internal Ledger   Razorpay       Bank Statement
                         Settlement
              |              |              |
              +--------------+--------------+
                             |
                             v
                    Tier 1 Exact Matching
                             |
                             v
                 Tier 2 Heuristic / Batch
                             |
                             v
                    Tier 3 Categorization
                             |
                             v
                 Reconciliation Results
                             |
                             v
                  Optional Tier 4 LLM
                       Explanation
```

---

## Project Structure

### Backend

```text
backend/
├── main.py
├── data_loader.py
├── pipeline.py
├── metrics.py
├── categorizer.py
├── evaluate.py
├── run_reconciliation.py
├── upload_handler.py
└── matcher/
    ├── exact.py
    ├── fuzzy_batch.py
    └── llm_reasoner.py
```

### Frontend

```text
frontend/src/
├── components/
│   ├── dashboard/
│   │   ├── MetricsCards.jsx
│   │   ├── ReconciliationChart.jsx
│   │   ├── ExceptionBreakdown.jsx
│   │   ├── RecentActivity.jsx
│   │   └── UploadDataset.jsx
│   ├── transactions/
│   │   ├── TransactionsTable.jsx
│   │   └── TransactionStatusBadge.jsx
│   ├── exceptions/
│   │   └── ExplainModal.jsx
│   └── layout/
│       ├── Sidebar.jsx
│       └── TopBar.jsx
├── pages/
│   ├── Dashboard.jsx
│   ├── Transactions.jsx
│   └── Exceptions.jsx
├── services/
│   └── api.js
├── App.jsx
├── App.css
├── index.css
└── main.jsx
```

---

## Tech Stack

### Backend

* **Python**
* **FastAPI**
* **Uvicorn**
* **Pandas**
* **NumPy**
* **RapidFuzz**
* **Faker**
* **Pytest**
* **python-multipart**

### Frontend

* **React 19**
* **Vite**
* **Axios**
* **Recharts**
* **Lucide React**
* **ESLint**

---

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/Prakhar-1202/finance-controller.git
cd finance-controller
```

### 2. Set up the backend

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 3. Run the reconciliation pipeline

```bash
python -m backend.run_reconciliation --data-dir data
```

### 4. Run the evaluation

```bash
python -m backend.evaluate --data-dir data
```

### 5. Run backend tests

```bash
pytest -q
```

### 6. Start the FastAPI server

```bash
uvicorn backend.main:app --reload
```

The backend will be available at:

```text
http://localhost:8000
```

Interactive API documentation:

```text
http://localhost:8000/docs
```

---

## Frontend Setup

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

The Vite development server will provide the frontend URL in the terminal.

For local development, the frontend uses:

```text
http://127.0.0.1:8000
```

as the default backend URL.

To use a different backend URL, create:

```text
frontend/.env
```

and add:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

For the deployed frontend, `VITE_API_BASE_URL` points to the deployed Render backend.

---

## Optional LLM Configuration

The reconciliation pipeline works without an LLM API key.

To enable LLM-powered exception explanations, configure:

```bash
export FINANCE_LLM_API_KEY=your_api_key
```

Optional configuration:

```bash
export FINANCE_LLM_API_BASE=https://api.openai.com/v1/chat/completions
export FINANCE_LLM_MODEL=gpt-4o-mini
```

The application falls back to deterministic explanations when the API key is not configured or an LLM request fails validation.

---

## API Endpoints

| Method | Endpoint                  | Description                                                                  |
| ------ | ------------------------- | ---------------------------------------------------------------------------- |
| `POST` | `/api/reconcile`          | Runs the reconciliation pipeline and returns reconciliation metrics          |
| `GET`  | `/api/transactions`       | Returns a paginated list of transactions with reconciliation status          |
| `GET`  | `/api/exceptions`         | Returns detected exceptions and batch-level reconciliation details           |
| `POST` | `/api/exceptions/explain` | Generates an LLM or deterministic explanation for a pre-classified exception |
| `POST` | `/api/upload`             | Validates and uploads a new three-file reconciliation dataset                |

Complete request and response schemas are available through FastAPI's interactive `/docs` interface.

---

## Testing

The project includes automated backend tests covering:

* Tier 1 exact matching
* Duplicate detection
* Amount drift classification
* Subset-sum matching
* Tier 3 categorization
* LLM reasoning and deterministic fallback
* Metrics aggregation
* Dataset upload validation
* FastAPI endpoints

Current test status:

```text
82 tests passed
```

Run the test suite with:

```bash
pytest -q
```

---

## Evaluation

The project includes a separate evaluation harness using:

```text
data/ground_truth.csv
```

Run it with:

```bash
python -m backend.evaluate --data-dir data
```

This evaluation is separate from the automated unit test suite and is used to measure reconciliation performance against known ground-truth outcomes.

---

## Deployment

The application is deployed as two services:

| Layer    | Platform | URL                                           |
| -------- | -------- | --------------------------------------------- |
| Frontend | Vercel   | https://finance-controller-ebon.vercel.app/   |
| Backend  | Render   | https://finance-controller-58zn.onrender.com/ |

The frontend communicates with the backend through the `VITE_API_BASE_URL` environment variable.

---

## Deployment Limitations

This project is designed as a lightweight demonstration and does not currently provide:

* Database persistence
* Authentication
* Multi-user accounts
* Per-user dataset isolation
* Horizontal multi-instance state sharing

Uploaded datasets are stored on the backend filesystem under:

```text
data/uploads/<dataset-id>/
```

The deployed Render service uses an ephemeral filesystem, so uploaded datasets should not be considered permanent storage. The bundled datasets inside `data/` are part of the repository and persist across deployments.

The reconciliation result cache is held in process memory and is reset when the backend restarts.

The Render free-tier backend may also experience a cold start after a period of inactivity.

---

## Future Improvements

Potential production improvements include:

* Persistent database or object storage for uploaded datasets
* Authentication and role-based access control
* Per-user dataset isolation
* Background processing for large reconciliation jobs
* More scalable subset-sum matching for large settlement batches
* Persistent audit logs
* Production monitoring and observability
* Additional payment gateway integrations

---

## License

This project is available under the license included in the repository.
