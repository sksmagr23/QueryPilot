# QueryPilot — System & LangGraph Architecture

## 1. High-Level System Architecture

```mermaid
flowchart TB
    subgraph Frontend ["Frontend Workspace (React + Vite + TypeScript + Tailwind)"]
        UI_Play["Analytics Playground"]
        UI_SQL["SQL Inspector (Monaco)"]
        UI_Res["Results Explorer (Recharts + KPIs)"]
        UI_Ins["Insights Panel (Evidence + Limitations)"]
        UI_Trace["Execution Trace (React Flow)"]
        UI_Schema["Schema Explorer (ER Graph + Semantic Catalog)"]
        UI_Hist["Query History & Saved Analyses"]
        UI_Appr["Human-in-the-Loop Approval Queue"]
    end

    subgraph API ["FastAPI Backend Layer (/api/*)"]
        R_Query["/api/query & /api/query/follow-up"]
        R_SQL["/api/sql/validate, /estimate-cost, /execute"]
        R_Appr["/api/approvals & /approve & /reject"]
        R_Schema["/api/schema & /api/history & /api/traces"]
    end

    subgraph LangGraph ["12-Node LangGraph StateGraph (QueryPilotState)"]
        N1["1. Request Analyzer"]
        N2["2. Schema Discovery"]
        N3["3. Query Planner"]
        N4["4. SQL Generator"]
        N5["5. SQL Validator (SQLGlot AST)"]
        N6["6. Cost Estimator (EXPLAIN JSON)"]
        N7["7. Approval Gate (SHA-256 Fingerprint)"]
        N8["8. Query Executor (Read-Only + Timeout)"]
        N9["9. Result Validator"]
        N10["10. Analysis Agent (Deterministic Stats)"]
        N11["11. Visualization Builder"]
        N12["12. Response Generator"]
    end

    subgraph Storage ["PostgreSQL 16 Warehouse & Metadata"]
        PG_RO[("Warehouse Read-Only Role (querypilot_ro)")]
        PG_Meta[("Persistence Store (History, Traces, Approvals)")]
    end

    subgraph LLM ["Google Gemini Provider (.env Configured)"]
        Gemini["Google GenAI SDK (gemini-2.5-flash / gemini-2.5-flash-lite)"]
    end

    Frontend --> API
    API --> LangGraph
    LangGraph --> LLM
    N2 --> PG_RO
    N6 --> PG_RO
    N8 --> PG_RO
    API --> PG_Meta
```

---

## 2. 12-Node LangGraph Workflow & Conditional Routing

QueryPilot implements a strongly typed `QueryPilotState` orchestrated by a LangGraph `StateGraph` with **three independent bounded retry counters** (`sql_retry_count`, `exec_retry_count`, `result_retry_count`) to prevent infinite loops:

```mermaid
flowchart TD
    START([User Question]) --> N1["1. Request Analyzer"]

    N1 -- "in_scope" --> N2["2. Schema Discovery"]
    N1 -- "ambiguous / missing_schema / unsafe" --> N12["12. Response Generator"]

    N2 --> N3["3. Query Planner"]
    N3 --> N4["4. SQL Generator"]
    N4 --> N5["5. SQL Validator (SQLGlot AST)"]

    N5 -- "is_valid = true" --> N6["6. Cost Estimator (EXPLAIN JSON)"]
    N5 -- "invalid & sql_retry_count < 2" --> N4
    N5 -- "invalid & retries exhausted / unsafe AST" --> N12

    N6 -- "requires_approval = true" --> N7["7. Approval Gate"]
    N6 -- "requires_approval = false" --> N8["8. Query Executor"]

    N7 -- "approved & fingerprint valid" --> N8
    N7 -- "pending / rejected" --> END_INT([Pause / End Turn])

    N8 -- "execution_ok" --> N9["9. Result Validator"]
    N8 -- "db_error & exec_retry_count < 1" --> N4
    N8 -- "db_error & retries exhausted" --> N12

    N9 -- "valid / empty_result" --> N10["10. Analysis Agent"]
    N9 -- "retry_needed & result_retry_count < 1" --> N4

    N10 --> N11["11. Visualization Builder"]
    N11 --> N12
    N12 --> END_DONE([Evidence-Grounded Response])
```

---

## 3. E-Commerce Data Warehouse Schema (`seed=42`)

```mermaid
erDiagram
    CATEGORIES ||--o{ PRODUCTS : "category_id"
    CUSTOMERS ||--o{ ORDERS : "customer_id"
    ORDERS ||--|{ ORDER_ITEMS : "order_id"
    PRODUCTS ||--o{ ORDER_ITEMS : "product_id"
    ORDERS ||--o{ PAYMENTS : "order_id"
    CUSTOMERS ||--o{ WEBSITE_EVENTS : "customer_id"
```

---

## 4. Defense-in-Depth Safety & Approval Architecture

1. **Full-AST Structural SQL Validation (`sql_validator.py`):**
   - Uses `sqlglot.parse()` to reject multi-statement queries (`len(statements) != 1`).
   - Traverses the entire AST via `ast.walk()` so destructive operations hidden inside CTEs (`WITH del AS (DELETE FROM customers RETURNING *) SELECT * FROM del`), subqueries, `SELECT ... INTO`, or locking clauses (`FOR UPDATE`) are deterministically blocked.
   - Rejects dangerous PostgreSQL functions (`pg_sleep`, `pg_read_file`, `pg_terminate_backend`, `dblink`, `lo_import`) and system schemas (`pg_catalog`, `information_schema`, `pg_shadow`).
   - Verifies all referenced tables and qualified columns against the discovered warehouse schema.
2. **Database-Level Read-Only Enforcement (`engine.py` & `init_ro_role.sql`):**
   - Queries execute via `querypilot_ro`, a dedicated PostgreSQL role configured with `ALTER ROLE querypilot_ro SET default_transaction_read_only = on`.
   - Every query execution opens a read-only transaction (`SET LOCAL TRANSACTION READ ONLY`) with `SET LOCAL statement_timeout = '5000ms'` and fetches at most `max_rows + 1` rows at the cursor level.
3. **Context-Bound Approval Gate (`routes_approval.py` & `persistence.py`):**
   - Computes a SHA-256 `context_fingerprint` over `(normalized_sql, database_role, max_rows, timeout_ms)`.
   - If the SQL or execution context changes after an approval request is created, the approval is invalidated (`409 Conflict`).
   - Atomic `approval_executed` locking prevents duplicate execution on repeated approval requests.
