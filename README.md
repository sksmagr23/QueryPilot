# QueryPilot

QueryPilot is an Agentic analytics platform that translates natural-language business questions into validated SQL queries, estimates database execution cost, runs queries safely on a read-only connection, and delivers interactive charts, queries, and data-backed insights.

---

## Core Tech Stack

- **Frontend:** React, TypeScript, Vite, Tailwind CSS, Recharts
- **Backend:** Python, FastAPI, LangGraph, Pydantic, SQLAlchemy
- **AI & Safety:** Google Gemini (`google-genai`), SQLGlot (AST SQL validation)
- **Database:** PostgreSQL (Docker)

---

## What It Solves

1. **Schema-Grounded Queries:** Inspects the live database tables, columns, and business metric definitions before generating SQL so the model does not invent tables or fields.
2. **Read-Only Database Safety:** Parses SQL into an Abstract Syntax Tree (SQLGlot) to block destructive queries, system catalog probes, and multi-statement queries, and executes everything through a read-only PostgreSQL role with statement timeouts and row limits.
3. **Self-Correction:** Uses separate bounded retry counters for SQL validation errors and database runtime errors to automatically fix query mistakes without infinite loops.
4. **Human-in-the-Loop Approvals:** Runs PostgreSQL `EXPLAIN` to estimate query cost before execution. Expensive queries are paused and sent to the **Approvals** tab for user review.
5. **Verified Numbers:** Calculates totals, averages, rankings, and percentage changes in Python from the actual database rows rather than letting the LLM guess numbers.

---

## Features

- **Analytics Workspace:** Ask questions in plain English, ask follow-up questions in the same thread, and explore KPI cards, charts, and data tables.
- **CSV Export & Saved Reports:** Download results as CSV or bookmark reports to revisit later.
- **Approval Queue:** Review and approve or decline high-cost queries before they run on the database.
- **Data Catalog:** Browse available store tables, fields, and metric definitions.

For the internal 12-node LangGraph workflow and system diagrams, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).  
For REST API endpoints, see [docs/API.md](docs/API.md).

---

## Benchmark Summary (105 Test Cases)

Measured comparison between a single-pass baseline text-to-SQL agent and QueryPilot on the seeded PostgreSQL warehouse ([docs/EVALUATION_REPORT.md](docs/EVALUATION_REPORT.md)):

| Metric | Baseline Agent | QueryPilot |
|---|---:|---:|
| SQL Execution Success Rate | 84.62% | **100.00%** |
| Overall Result Correctness | 51.43% | **99.05%** |
| Vague / Missing-Data Detection | 0.00% | **100.00%** |
| Unsafe Query Rejection Rate | 0.00% | **100.00%** |
| Broken SQL Recovery Rate | 0.00% | **100.00%** |
| Unnecessary Approval Rate | 29.09% | **0.00%** |

---

## Local Setup

### Prerequisites
- Docker Desktop
- Python 3.11+
- Node.js 20+

### 1. Environment Variables
Copy `.env.example` to `.env` and add your Gemini API key:
```bash
cp .env.example .env
```
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
GEMINI_FALLBACK_MODEL=gemini-2.5-flash-lite
```

### 2. Start PostgreSQL & Seed Data
```bash
docker compose up -d postgres
python -m venv .venv
pip install -r backend/requirements.txt
python backend/app/db/seed.py
```

### 3. Run Backend & Frontend
**Terminal 1 — Backend (`http://localhost:8000`):**
```bash
python backend/run.py
```

**Terminal 2 — Frontend (`http://localhost:5173`):**
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Running Tests

```bash
pytest.exe backend/tests -v
```

---

## Project Structure

```text
Querypilot/
├── backend/
│   ├── run.py              # server launcher
│   ├── app/
│   │   ├── api/            # FastAPI endpoints
│   │   ├── db/             # SQLAlchemy models, read-only engine, deterministic seed, persistence
│   │   ├── graph/          # 12-node LangGraph workflow, state, and conditional routing
│   │   ├── llm/            # Google Gemini provider configured
│   │   ├── safety/         # SQLGlot AST validator & PostgreSQL EXPLAIN cost estimator
│   │   ├── semantic/       # Live schema inspector & semantic metric catalog
│   │   └── services/       # Python statistical analyzer & chart builder
│   ├── eval/               # 105-question benchmark suite & baseline comparator
│   └── tests/              # 43 pytest suites
├── frontend/
│   └── src/components/     
└── docs/
    ├── ARCHITECTURE.md     # LangGraph workflow & system architecture
    ├── API.md              # API reference
    └── EVALUATION_REPORT.md# 105-question benchmark report
```

---