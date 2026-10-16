"""Phase 4 tests: FastAPI endpoints for analytics queries, SQL validation, cost estimation, execution, approvals, history, traces, and CSV export."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "healthy"
    assert body["database"]["connected"] is True
    assert body["database"]["readonly_enforced"] is True
    assert body["llm"]["gemini_model"] == "gemini-2.5-flash"


def test_schema_and_semantic_endpoints():
    res_schema = client.get("/api/v1/schema")
    assert res_schema.status_code == 200
    s_body = res_schema.json()
    assert len(s_body["tables"]) == 7
    assert len(s_body["relationships"]) >= 6

    res_sem = client.get("/api/v1/schema/semantic")
    assert res_sem.status_code == 200
    sem_body = res_sem.json()
    assert len(sem_body["metrics"]) >= 6
    assert len(sem_body["valid_joins"]) >= 6


def test_query_trace_history_bookmark_and_csv_export():
    res = client.post(
        "/api/v1/query",
        json={"question": "Which product categories generate the most revenue?"},
    )
    assert res.status_code == 200
    data = res.json()
    qid = data["query_id"]
    assert data["status"] == "completed"
    assert len(data["execution_result"]["rows"]) == 8

    # Fetch stored query
    res_get = client.get(f"/api/v1/query/{qid}")
    assert res_get.status_code == 200
    assert res_get.json()["query_id"] == qid

    # Fetch execution trace
    res_trace = client.get(f"/api/v1/traces/{qid}")
    assert res_trace.status_code == 200
    trace_body = res_trace.json()
    assert len(trace_body["trace"]) >= 9
    assert len(trace_body["topology"]["nodes"]) == 12

    # Export CSV
    res_csv = client.get(f"/api/v1/query/{qid}/export")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "Electronics" in res_csv.text

    # Bookmark as Saved Analysis
    res_bm = client.post(
        f"/api/v1/history/{qid}/bookmark",
        json={"bookmarked": True, "title": "Category Revenue Benchmark"},
    )
    assert res_bm.status_code == 200
    assert res_bm.json()["bookmarked"] is True
    assert res_bm.json()["title"] == "Category Revenue Benchmark"

    # List bookmarked history
    res_hist = client.get("/api/v1/history?bookmarked_only=true")
    assert res_hist.status_code == 200
    assert any(item["query_id"] == qid for item in res_hist.json()["items"])


def test_sql_inspector_endpoints_and_revalidation():
    # 1. Validate safe SQL
    val_ok = client.post(
        "/api/v1/sql/validate",
        json={"sql": "SELECT region, COUNT(*) AS cnt FROM orders GROUP BY region"},
    )
    assert val_ok.status_code == 200
    assert val_ok.json()["is_valid"] is True

    # 2. Validate unsafe writable CTE -> rejected
    val_bad = client.post(
        "/api/v1/sql/validate",
        json={"sql": "WITH d AS (DELETE FROM orders RETURNING *) SELECT * FROM d"},
    )
    assert val_bad.status_code == 200
    assert val_bad.json()["is_valid"] is False
    assert val_bad.json()["is_safe"] is False

    # 3. Cost estimation
    cost_res = client.post(
        "/api/v1/sql/cost",
        json={"sql": "SELECT region, COUNT(*) AS cnt FROM orders GROUP BY region"},
    )
    assert cost_res.status_code == 200
    assert cost_res.json()["is_valid"] is True
    assert cost_res.json()["cost_estimate"]["estimated_cost"] > 0

    # 4. Execute edited SQL
    exec_res = client.post(
        "/api/v1/sql/execute",
        json={
            "sql": "SELECT region, COUNT(*) AS order_count FROM orders GROUP BY region ORDER BY order_count DESC",
            "question": "Orders by region",
        },
    )
    assert exec_res.status_code == 200
    assert exec_res.json()["status"] == "completed"
    assert len(exec_res.json()["execution_result"]["rows"]) == 4


def test_approval_queue_api_invalidation_and_duplicate_execution_prevention():
    # 1. Create a high-cost query that pauses at Approval Gate
    res = client.post(
        "/api/v1/query",
        json={
            "question": "What is the average order value by customer segment?",
            "cost_threshold_override": 1.0,
        },
    )
    assert res.status_code == 200
    paused = res.json()
    qid = paused["query_id"]
    assert paused["status"] == "awaiting_approval"

    # 2. Check /api/v1/approvals queue
    q_res = client.get("/api/v1/approvals?status=pending")
    assert q_res.status_code == 200
    assert any(item["query_id"] == qid for item in q_res.json()["items"])

    # 3. Attempting to approve with mismatched expected_sql returns 409 Conflict (invalidated)
    mismatch_res = client.post(
        f"/api/v1/approvals/{qid}/decision",
        json={
            "decision": "approved",
            "expected_sql": "SELECT * FROM customers LIMIT 1",
        },
    )
    assert mismatch_res.status_code == 409

    # 4. Create a fresh paused query and approve it properly
    res2 = client.post(
        "/api/v1/query",
        json={
            "question": "What is the average order value by customer segment?",
            "cost_threshold_override": 1.0,
        },
    )
    qid2 = res2.json()["query_id"]
    approve_res = client.post(
        f"/api/v1/approvals/{qid2}/decision",
        json={"decision": "approved", "reviewer_comment": "LGTM"},
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "completed"
    assert approve_res.json()["approval_executed"] is True

    # 5. Attempting to approve/execute again returns 409 Conflict (duplicate execution prevented)
    dup_res = client.post(
        f"/api/v1/approvals/{qid2}/decision",
        json={"decision": "approved"},
    )
    assert dup_res.status_code == 409
