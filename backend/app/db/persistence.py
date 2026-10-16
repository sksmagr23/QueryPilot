"""Persistence layer for QueryPilot history, saved analyses, execution traces, and approval queue."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
META_DB_PATH = DATA_DIR / "querypilot_meta.sqlite3"

_DB_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(META_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_persistence_db() -> None:
    """Create metadata tables if they do not exist."""
    with _DB_LOCK:
        with _get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_runs (
                    query_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    generated_sql TEXT,
                    approval_status TEXT NOT NULL,
                    approval_fingerprint TEXT,
                    approval_executed INTEGER NOT NULL DEFAULT 0,
                    reviewer_comment TEXT,
                    estimated_cost REAL DEFAULT 0.0,
                    risk_level TEXT DEFAULT 'low',
                    row_count INTEGER DEFAULT 0,
                    total_latency_ms REAL DEFAULT 0.0,
                    bookmarked INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    state_json TEXT NOT NULL
                )
                """
            )
            conn.commit()


init_persistence_db()


def save_workflow_state(state: Dict[str, Any], bookmarked: Optional[bool] = None) -> Dict[str, Any]:
    """Insert or update a QueryPilot workflow state in persistent storage."""
    init_persistence_db()
    query_id = state["query_id"]
    thread_id = state.get("thread_id", "")
    question = state.get("question", "")
    headline = (state.get("response") or {}).get("headline") or question[:80]
    status = state.get("status", "completed")
    sql = state.get("generated_sql", "")
    app_status = state.get("approval_status", "not_required")
    app_fp = state.get("approval_fingerprint", "")
    app_exec = 1 if state.get("approval_executed", False) else 0
    rev_comment = state.get("reviewer_comment")
    cost_est = state.get("cost_estimate") or {}
    est_cost = float(cost_est.get("estimated_cost") or 0.0)
    risk_lvl = str(cost_est.get("risk_level") or "low")
    exec_res = state.get("execution_result") or {}
    row_cnt = int(exec_res.get("row_count") or 0)
    latency = float(state.get("total_latency_ms") or 0.0)
    now = _now_iso()

    # Keep a compact copy without massive explain_plan bloat if needed, but preserve full trace & rows
    serialized = json.dumps(state, default=str)

    with _DB_LOCK:
        with _get_conn() as conn:
            existing = conn.execute(
                "SELECT bookmarked, created_at, title FROM query_runs WHERE query_id = ?",
                (query_id,),
            ).fetchone()
            if existing:
                bm = int(bookmarked) if bookmarked is not None else int(existing["bookmarked"])
                created_at = existing["created_at"]
                title = headline if headline else existing["title"]
                conn.execute(
                    """
                    UPDATE query_runs
                    SET thread_id = ?,
                        question = ?,
                        title = ?,
                        status = ?,
                        generated_sql = ?,
                        approval_status = ?,
                        approval_fingerprint = ?,
                        approval_executed = ?,
                        reviewer_comment = ?,
                        estimated_cost = ?,
                        risk_level = ?,
                        row_count = ?,
                        total_latency_ms = ?,
                        bookmarked = ?,
                        updated_at = ?,
                        state_json = ?
                    WHERE query_id = ?
                    """,
                    (
                        thread_id,
                        question,
                        title,
                        status,
                        sql,
                        app_status,
                        app_fp,
                        app_exec,
                        rev_comment,
                        est_cost,
                        risk_lvl,
                        row_cnt,
                        latency,
                        bm,
                        now,
                        serialized,
                        query_id,
                    ),
                )
            else:
                bm = 1 if bookmarked else 0
                conn.execute(
                    """
                    INSERT INTO query_runs (
                        query_id, thread_id, question, title, status, generated_sql,
                        approval_status, approval_fingerprint, approval_executed, reviewer_comment,
                        estimated_cost, risk_level, row_count, total_latency_ms,
                        bookmarked, created_at, updated_at, state_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        query_id,
                        thread_id,
                        question,
                        headline,
                        status,
                        sql,
                        app_status,
                        app_fp,
                        app_exec,
                        rev_comment,
                        est_cost,
                        risk_lvl,
                        row_cnt,
                        latency,
                        bm,
                        now,
                        now,
                        serialized,
                    ),
                )
            conn.commit()
    return state


def get_persisted_state(query_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve full persisted workflow state by query_id."""
    init_persistence_db()
    with _DB_LOCK:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT state_json, bookmarked, created_at, updated_at, title FROM query_runs WHERE query_id = ?",
                (query_id,),
            ).fetchone()
            if not row:
                return None
            data = json.loads(row["state_json"])
            data["bookmarked"] = bool(row["bookmarked"])
            data["created_at"] = row["created_at"]
            data["updated_at"] = row["updated_at"]
            data["title"] = row["title"]
            return data


def list_query_history(
    bookmarked_only: bool = False,
    search: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List query history items ordered by most recent first."""
    init_persistence_db()
    clauses: List[str] = []
    params: List[Any] = []
    if bookmarked_only:
        clauses.append("bookmarked = 1")
    if search and search.strip():
        clauses.append("(LOWER(question) LIKE ? OR LOWER(title) LIKE ? OR LOWER(generated_sql) LIKE ?)")
        like_pat = f"%{search.strip().lower()}%"
        params.extend([like_pat, like_pat, like_pat])

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT query_id, thread_id, question, title, status, generated_sql,
               approval_status, estimated_cost, risk_level, row_count,
               total_latency_ms, bookmarked, created_at, updated_at
        FROM query_runs
        {where_sql}
        ORDER BY created_at DESC
        LIMIT ?
    """
    params.append(limit)
    with _DB_LOCK:
        with _get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [
                {
                    "query_id": r["query_id"],
                    "thread_id": r["thread_id"],
                    "question": r["question"],
                    "title": r["title"],
                    "status": r["status"],
                    "generated_sql": r["generated_sql"],
                    "approval_status": r["approval_status"],
                    "estimated_cost": r["estimated_cost"],
                    "risk_level": r["risk_level"],
                    "row_count": r["row_count"],
                    "total_latency_ms": r["total_latency_ms"],
                    "bookmarked": bool(r["bookmarked"]),
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                }
                for r in rows
            ]


def toggle_bookmark(
    query_id: str,
    bookmarked: Optional[bool] = None,
    title: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Toggle or set bookmark status and optional custom title on a saved analysis."""
    init_persistence_db()
    with _DB_LOCK:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT bookmarked, title FROM query_runs WHERE query_id = ?",
                (query_id,),
            ).fetchone()
            if not row:
                return None
            new_bm = int(bookmarked) if bookmarked is not None else (0 if row["bookmarked"] else 1)
            new_title = title.strip() if title and title.strip() else row["title"]
            conn.execute(
                "UPDATE query_runs SET bookmarked = ?, title = ?, updated_at = ? WHERE query_id = ?",
                (new_bm, new_title, _now_iso(), query_id),
            )
            conn.commit()
    return get_persisted_state(query_id)


def delete_history_item(query_id: str) -> bool:
    """Delete a query run from history."""
    init_persistence_db()
    with _DB_LOCK:
        with _get_conn() as conn:
            cur = conn.execute("DELETE FROM query_runs WHERE query_id = ?", (query_id,))
            conn.commit()
            return cur.rowcount > 0


def list_approvals(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """List approval queue items (pending, approved, rejected, invalidated)."""
    init_persistence_db()
    params: List[Any] = []
    if status_filter and status_filter != "all":
        where_clause = "WHERE approval_status = ?"
        params.append(status_filter)
    else:
        where_clause = "WHERE approval_status IN ('pending', 'approved', 'rejected', 'invalidated')"

    sql = f"""
        SELECT query_id, thread_id, question, title, status, generated_sql,
               approval_status, approval_fingerprint, approval_executed,
               reviewer_comment, estimated_cost, risk_level, created_at, updated_at, state_json
        FROM query_runs
        {where_clause}
        ORDER BY updated_at DESC
    """
    with _DB_LOCK:
        with _get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            items: List[Dict[str, Any]] = []
            for r in rows:
                st = json.loads(r["state_json"])
                cost_est = st.get("cost_estimate") or {}
                items.append(
                    {
                        "query_id": r["query_id"],
                        "thread_id": r["thread_id"],
                        "question": r["question"],
                        "title": r["title"],
                        "status": r["status"],
                        "generated_sql": r["generated_sql"],
                        "approval_status": r["approval_status"],
                        "approval_fingerprint": r["approval_fingerprint"],
                        "approval_executed": bool(r["approval_executed"]),
                        "reviewer_comment": r["reviewer_comment"],
                        "estimated_cost": r["estimated_cost"],
                        "risk_level": r["risk_level"],
                        "approval_reason": cost_est.get("approval_reason"),
                        "approval_reasons": cost_est.get("approval_reasons", []),
                        "created_at": r["created_at"],
                        "updated_at": r["updated_at"],
                    }
                )
            return items
