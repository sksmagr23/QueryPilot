"""Phase 3 tests: 12-node LangGraph workflow, golden test set, separate retry counters, approval invalidation, and idempotency."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.graph.workflow import (
    invalidate_workflow_approval,
    resume_querypilot_approval,
    run_querypilot_workflow,
)

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "eval" / "golden_questions.json"


def test_golden_questions_suite():
    """Run all 16 golden test cases through the 12-node LangGraph workflow and verify actual outputs."""
    cases = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert len(cases) == 16

    for case in cases:
        state = run_querypilot_workflow(question=case["question"], force_provider="mock")
        assert state["status"] == case["expected_status"], (
            f"Case {case['id']} ({case['question']}) expected status "
            f"{case['expected_status']} but got {state['status']}"
        )

        if case["expected_status"] == "completed":
            rows = state["execution_result"]["rows"]
            assert len(rows) >= case.get("min_rows", 0)
            if "max_rows" in case:
                assert len(rows) <= case["max_rows"]
            if "expected_top_dimension" in case:
                primary_dim = state["analysis"]["primary_dimension"]
                first_dim = rows[0][primary_dim]
                assert first_dim == case["expected_top_dimension"]
            assert state["visualization"]["chart_type"] in (
                "bar",
                "line",
                "area",
                "pie",
                "composed",
                "table_only",
            )
            assert state["response"]["headline"]


def test_configured_default_provider_flagship_execution():
    """Verify the default configured provider (Gemini when GEMINI_API_KEY is present) executes end-to-end and selects human-readable primary_dimension."""
    state = run_querypilot_workflow(question="Which product categories generate the most revenue?")
    assert state["status"] == "completed"
    rows = state["execution_result"]["rows"]
    assert len(rows) == 8
    primary_dim = state["analysis"]["primary_dimension"]
    assert rows[0][primary_dim] == "Electronics"


def test_separate_bounded_retry_counter_for_sql_validation_recovery():
    """Verify invalid SQL triggers sql_retry_count without incrementing exec_retry_count, and recovers on retry."""
    state = run_querypilot_workflow(
        question="Which product categories generate the most revenue?",
        seed_invalid_sql="SELECT c.name, o.nonexistent_revenue_col FROM categories c JOIN orders o ON 1=1",
    )
    assert state["status"] == "completed"
    assert state["sql_retry_count"] == 1
    assert state["exec_retry_count"] == 0
    assert state["result_retry_count"] == 0
    assert state["generation_attempts"] == 2
    assert len(state["execution_result"]["rows"]) == 8


def test_separate_bounded_retry_counter_for_db_execution_error_recovery():
    """Verify runtime DB error (division by zero) increments exec_retry_count and recovers on retry."""
    state = run_querypilot_workflow(
        question="What is the average order value by customer segment?",
        seed_db_error_sql="SELECT segment, 1 / 0 AS broken_ratio FROM customers",
    )
    assert state["status"] == "completed"
    assert state["exec_retry_count"] == 1
    assert state["sql_retry_count"] == 0
    assert state["generation_attempts"] == 2
    assert len(state["execution_result"]["rows"]) == 4


def test_approval_interrupt_resumption_invalidation_and_duplicate_prevention():
    """
    Verify:
    1. Expensive query pauses at Approval Gate with status='awaiting_approval'.
    2. Modifying SQL invalidates the approval and blocks resumption.
    3. Valid approval resumes checkpoint to completion.
    4. Attempting to execute the same approved query a second time is rejected (prevents duplicate execution).
    """
    # 1. Trigger approval interrupt via low cost_threshold_override
    paused = run_querypilot_workflow(
        question="Which product categories generate the most revenue?",
        cost_threshold_override=1.0,
    )
    qid = paused["query_id"]
    assert paused["status"] == "awaiting_approval"
    assert paused["approval_status"] == "pending"
    assert len(paused["approval_fingerprint"]) == 64
    assert paused.get("execution_result") is None

    # 2. Attempt resumption with altered SQL -> raises ValueError and invalidates approval
    with pytest.raises(ValueError, match="invalidated"):
        resume_querypilot_approval(
            query_id=qid,
            decision="approved",
            expected_sql="SELECT * FROM categories LIMIT 5",
        )

    # 3. Re-run fresh pause, approve with matching SQL, and verify completion
    paused2 = run_querypilot_workflow(
        question="Which product categories generate the most revenue?",
        cost_threshold_override=1.0,
    )
    qid2 = paused2["query_id"]
    completed = resume_querypilot_approval(
        query_id=qid2,
        decision="approved",
        reviewer_comment="Approved for monthly executive report",
    )
    assert completed["status"] == "completed"
    assert completed["approval_status"] == "approved"
    assert completed["approval_executed"] is True
    assert len(completed["execution_result"]["rows"]) == 8

    # 4. Attempt duplicate execution on already-completed query -> raises RuntimeError
    with pytest.raises(RuntimeError, match="Duplicate execution prevented"):
        resume_querypilot_approval(query_id=qid2, decision="approved")

    # 5. Also verify invalidate_workflow_approval helper marks approval invalidated on SQL change
    paused3 = run_querypilot_workflow(
        question="What is the average order value by customer segment?",
        cost_threshold_override=1.0,
    )
    qid3 = paused3["query_id"]
    inv_state = invalidate_workflow_approval(qid3, new_sql="SELECT segment FROM customers")
    assert inv_state["approval_status"] == "invalidated"


def test_followup_question_context_preservation():
    """Verify follow-up questions preserve conversation context across turns."""
    turn1 = run_querypilot_workflow(
        question="Which product categories generate the most revenue?",
        thread_id="thread_ctx_test",
    )
    assert turn1["status"] == "completed"

    turn2 = run_querypilot_workflow(
        question="What about only for Enterprise customers?",
        thread_id="thread_ctx_test",
        conversation_history=[
            {
                "question": turn1["question"],
                "sql": turn1["generated_sql"],
                "summary": turn1["response"]["summary"],
            }
        ],
    )
    assert turn2["status"] == "completed"
    assert "enterprise" in turn2["generated_sql"].lower()
    assert len(turn2["execution_result"]["rows"]) > 0
