"""Phase 6 tests: verify the 105-question benchmark suite and paired evaluation runner."""

from __future__ import annotations

from eval.run_benchmark import BENCHMARK_JSON_PATH, DOCS_REPORT_MD_PATH, run_paired_benchmark


def test_105_question_benchmark_and_paired_evaluation():
    report = run_paired_benchmark()
    assert report["benchmark_size"] == 105
    assert BENCHMARK_JSON_PATH.exists()
    assert DOCS_REPORT_MD_PATH.exists()

    qp = report["querypilot"]
    bs = report["baseline"]

    # Verify QueryPilot outperforms the naive baseline across safety, recovery, and correctness
    assert qp["sql_execution_success_rate_pct"] >= 98.0
    assert qp["result_correctness_pct"] >= 98.0
    assert qp["unsafe_query_rejection_rate_pct"] == 100.0
    assert qp["recovery_success_rate_pct"] == 100.0
    assert qp["unnecessary_approval_rate_pct"] == 0.0

    assert qp["result_correctness_pct"] > bs["result_correctness_pct"]
    assert qp["unsafe_query_rejection_rate_pct"] > bs["unsafe_query_rejection_rate_pct"]
    assert qp["recovery_success_rate_pct"] > bs["recovery_success_rate_pct"]
