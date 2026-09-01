# Finance Controller Agent

Reconciliation pipeline for matching ledger, settlement, and bank statement data.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
pytest -q
python -m backend.run_reconciliation --data-dir data
python -m backend.evaluate --data-dir data
```

## Layout

- `data/` — CSV inputs and synthetic data generator
- `backend/` — pipeline, categorizer, evaluator, and matcher algorithms
- `tests/` — unit tests
