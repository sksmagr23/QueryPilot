# QueryPilot — REST API Documentation

Base URL: `http://localhost:8000/api`  
Interactive OpenAPI / Swagger UI: `http://localhost:8000/docs`

---

## 1. Health & System Status

### `GET /api/v1/health`
Returns database connectivity, read-only role verification, warehouse table counts, and `.env`-configured Gemini model status.

**Response `200 OK`:**
```json
{
  "status": "healthy",
  "database": {
    "connected": true,
    "dialect": "postgresql",
    "readonly_enforced": true,
    "statement_timeout_ms": 5000,
    "max_result_rows": 500
  },
  "llm": {
    "configured_provider": "gemini",
    "effective_provider": "gemini",
    "gemini_api_key_present": true,
    "gemini_model": "gemini-2.5-flash",
    "gemini_fallback_model": "gemini-2.5-flash-lite"
  }
}
```

---

## 2. Natural-Language Analytics Workflow

### `POST /api/query`
Runs the 12-node LangGraph workflow for a natural-language business question.

**Request Body:**
```json
{
  "question": "Which product categories generate the most revenue?",
  "thread_id": null,
  "conversation_history": [],
  "force_provider": null,
  "model_override": null
}
```

**Response `200 OK`:**
Returns the complete `QueryPilotState` payload including `thread_id`, `status` (`completed`, `awaiting_approval`, `clarification_needed`, `blocked`, `error`), `intent`, `query_plan`, `candidate_sql`, `sql_validation`, `cost_estimate`, `execution_result`, `analysis`, `chart_spec`, `final_response`, and `trace`.

### `POST /api/query/follow-up`
Executes a multi-turn follow-up question while automatically loading prior conversation context from `thread_id`.

---

## 3. Interactive SQL Inspector Endpoints

### `POST /api/sql/validate`
Validates arbitrary or user-edited SQL using the SQLGlot full-AST validator against the warehouse schema.

**Request Body:**
```json
{
  "sql": "SELECT name, department FROM categories ORDER BY name"
}
```

### `POST /api/sql/estimate-cost`
Validates the SQL and runs a non-executing `EXPLAIN (FORMAT JSON)` plan to estimate planner cost, row count, join count, and whether human approval is required.

### `POST /api/sql/execute`
Re-validates user-edited SQL, checks cost against the approval threshold, executes the query via the read-only database role with statement timeout and row limits, and returns rows, deterministic analysis, and chart specification.

---

## 4. Schema Discovery & Semantic Catalog

### `GET /api/schema`
Returns live warehouse table metadata, columns, primary/foreign keys, exact row counts, React Flow ER graph nodes/edges, and the business semantic catalog (`metrics`, `JoinRule` definitions, and verified status filters).

---

## 5. Human-in-the-Loop Approvals

### `GET /api/approvals`
Lists pending and historical approval gates (`?status=pending`).

### `POST /api/approvals/{thread_id}/approve`
Verifies the SHA-256 `context_fingerprint` (`normalized_sql | db_role | max_rows | timeout_ms`), ensures the approval has not already been executed (`409 Conflict` on mismatch or duplicate call), and resumes the LangGraph workflow from `Query Executor` through `Response Generator`.

### `POST /api/approvals/{thread_id}/reject`
Marks the approval request as rejected and terminates the paused workflow cleanly.

---

## 6. Query History, Traces & CSV Export

- `GET /api/history`: Lists saved query executions (`?saved_only=true&limit=50`).
- `GET /api/history/{thread_id}`: Loads the full saved state, SQL, results, insights, and execution trace for a historical run.
- `POST /api/history/{thread_id}/bookmark`: Toggles bookmark/saved status (`{"is_saved": true}`).
- `GET /api/traces/{thread_id}`: Returns the node-by-node LangGraph execution trace with per-node latency and status.
- `GET /api/export/{thread_id}/csv`: Streams the executed query result table as a downloadable RFC-4180 CSV file.
