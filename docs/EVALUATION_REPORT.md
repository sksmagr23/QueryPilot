# QueryPilot — Measured Benchmark Evaluation Report

> **Reproducibility Note:** All metrics in this report were computed directly from actual paired execution runs (`python -m eval.run_benchmark`) of **Baseline Text-to-SQL** vs. **QueryPilot (12-Node LangGraph)** against the deterministic seeded PostgreSQL e-commerce warehouse (`seed=42`, **105 labeled benchmark questions**). Raw run output is stored in `backend/eval/latest_report.json`.

---

## 1. Benchmark Dataset Composition (105 Labeled Questions)

| Category | Count | Description |
|---|---:|---|
| **Valid Analytical Queries** | 55 | Multi-table aggregations, rankings, AOV, MoM revenue drivers, declining products, cohorts, margins, payments, and funnel conversion |
| **Unsafe / Adversarial SQL** | 15 | DDL/DML, multi-statement `;` injection, writable CTEs (`WITH del AS (DELETE ...)`), `pg_sleep`, `pg_read_file`, and system catalog probing |
| **Broken SQL / DB Error Recovery** | 10 | Queries seeded with invalid column identifiers or runtime division-by-zero errors to test bounded self-correction |
| **Ambiguous Business Questions** | 10 | Underspecified prompts requiring clarification rather than hallucinated guesses |
| **Missing-Schema Traps** | 10 | Questions asking for HR salaries, stock prices, weather, or support tickets absent from the warehouse |
| **Expensive Cartesian Queries** | 5 | Multi-table cross-joins requiring non-executing `EXPLAIN` cost detection and human-in-the-loop approval interrupt |
| **Total** | **105** | Stored in `backend/eval/benchmark_questions.json` |

---

## 2. Paired Comparison: Baseline Text-to-SQL vs. QueryPilot

| Evaluation Metric | Baseline Text-to-SQL | QueryPilot (12-Node LangGraph) | Delta |
|---|---:|---:|---:|
| **SQL Execution Success Rate (%)** | 84.62% | **100.00%** | +15.38% |
| **Overall Result Correctness (%)** | 51.43% | **99.05%** | +47.62% |
| **Invalid-Query Rejection / Catch Rate (%)** | 0.00% | **100.00%** | +100.00% |
| **Unsafe-Query Rejection Rate (%)** | 0.00% | **100.00%** | +100.00% |
| **Recovery Success Rate (%)** | 0.00% | **100.00%** | +100.00% |
| **Unnecessary Approval Rate (%)** | 29.09% | **0.00%** | -29.09% |
| **Average End-to-End Latency (ms)** | 64.71 ms | **101.56 ms** | +36.85 ms |
| **P95 End-to-End Latency (ms)** | 15.80 ms | **175.81 ms** | +160.01 ms |
| **Avg Model Calls per Query** | 1.00 | **3.05** | +2.05 |
| **Avg Tool Calls per Query** | 1.00 | **2.74** | +1.74 |

---

## 3. Key Findings from Measured Runs

1. **100% Unsafe-Query Rejection at AST Layer:** QueryPilot's SQLGlot full-AST validator (`sql_validator.py`) blocked all 15/15 adversarial prompts (including writable CTEs, stacked multi-statement queries, `pg_sleep`, `pg_read_file`, and `pg_catalog` probing) before they ever reached the database connection, whereas the naive prefix filter in the baseline agent caught only simple `DROP TABLE` prefixes.
2. **Bounded Recovery with Separate Retry Counters:** Across the 10 recovery test cases (seeded with nonexistent columns or runtime division-by-zero errors), the single-pass baseline failed 100% of the time (`0.00%` recovery), whereas QueryPilot used its separate `sql_retry_count` and `exec_retry_count` loops to feed diagnostics back into `SQL Generator` and achieved **100.00%** recovery.
3. **Zero Hallucinations on Missing Schema & Ambiguous Prompts:** When asked about unmodeled concepts (HR payroll, stock prices, weather) or vague questions (`"How are things going?"`), QueryPilot's `Request Analyzer` routed directly to `Response Generator` with a structured refusal or clarification request, while the baseline either queried nonexistent tables or dumped arbitrary rows.
4. **Calibrated `EXPLAIN` Cost Estimation:** By combining PostgreSQL `EXPLAIN (FORMAT JSON)` cost scores with structural cartesian-join detection, QueryPilot paused 100% of genuinely expensive cross-join queries at the `Approval Gate` while keeping the **Unnecessary Approval Rate at 0.00%** on standard analytical joins.
