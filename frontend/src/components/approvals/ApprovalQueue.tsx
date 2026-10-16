import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Gauge,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import { apiClient } from "../../api/client";
import type { ApprovalItem, QueryPilotRun } from "../../types/querypilot";

interface ApprovalQueueProps {
  onApprovalResolved: (resumedRun: QueryPilotRun) => void;
}

export const ApprovalQueue: React.FC<ApprovalQueueProps> = ({
  onApprovalResolved,
}) => {
  const [items, setItems] = useState<ApprovalItem[]>([]);
  const [comments, setComments] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadApprovals = async () => {
    const res = await apiClient.getApprovals();
    setItems(res.items);
  };

  useEffect(() => {
    loadApprovals();
  }, []);

  const handleDecision = async (
    item: ApprovalItem,
    decision: "approved" | "rejected"
  ) => {
    setBusyId(item.query_id);
    setErrorMsg(null);
    try {
      const updated = await apiClient.decideApproval(item.query_id, {
        decision,
        reviewer_comment: comments[item.query_id] || undefined,
        expected_sql: item.generated_sql,
      });
      await loadApprovals();
      onApprovalResolved(updated);
    } catch (err) {
      setErrorMsg(
        err instanceof Error ? err.message : "Failed to process approval"
      );
      await loadApprovals();
    } finally {
      setBusyId(null);
    }
  };

  const pendingCount = items.filter((i) => i.approval_status === "pending").length;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-800 bg-slate-900/90 px-5 py-4">
        <div className="flex items-center gap-2.5">
          <ShieldAlert className="h-5 w-5 text-amber-400" />
          <div>
            <h2 className="text-sm font-bold text-slate-100">
              Pending Query Approvals ({pendingCount} waiting)
            </h2>
            <p className="text-xs text-slate-400">
              Queries that scan large amounts of data pause here so you can
              review and approve them before they run.
            </p>
          </div>
        </div>
      </div>

      {errorMsg && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-3.5 text-xs text-rose-300">
          {errorMsg}
        </div>
      )}

      {items.length === 0 ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-10 text-center text-sm text-slate-400">
          No queries are waiting for your review right now.
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => {
            const isPending = item.approval_status === "pending";
            return (
              <div
                key={item.query_id}
                className={`rounded-2xl border p-5 space-y-3.5 transition ${
                  isPending
                    ? "border-amber-500/50 bg-slate-900/95 shadow-lg shadow-amber-950/20"
                    : "border-slate-800 bg-slate-900/70"
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <span className="font-semibold text-sm text-slate-100">
                      {item.question}
                    </span>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold capitalize ${
                        item.approval_status === "pending"
                          ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                          : item.approval_status === "approved"
                            ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                            : "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                      }`}
                    >
                      {item.approval_status === "pending"
                        ? "Needs Your Review"
                        : item.approval_status === "approved"
                          ? "Approved & Completed"
                          : "Declined"}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 text-xs text-slate-300">
                    <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 capitalize text-amber-300">
                      <Gauge className="h-3.5 w-3.5" />
                      Impact: {item.risk_level}
                    </span>
                  </div>
                </div>

                {item.approval_reason && (
                  <div className="flex items-start gap-2.5 rounded-xl border border-amber-500/30 bg-amber-950/30 px-3.5 py-2.5 text-xs text-amber-200">
                    <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
                    <span>
                      <strong>Why approval is needed:</strong>{" "}
                      {item.approval_reason}
                    </span>
                  </div>
                )}

                <div>
                  <div className="mb-1 text-[11px] font-medium text-slate-400">
                    SQL Query to Run:
                  </div>
                  <pre className="rounded-xl border border-slate-800 bg-slate-950 p-3.5 font-mono text-xs text-emerald-300 overflow-x-auto">
                    {item.generated_sql}
                  </pre>
                </div>

                {isPending ? (
                  <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                    <input
                      type="text"
                      value={comments[item.query_id] || ""}
                      onChange={(e) =>
                        setComments({
                          ...comments,
                          [item.query_id]: e.target.value,
                        })
                      }
                      placeholder="Add an optional note before approving or declining..."
                      className="flex-1 min-w-[240px] rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-xs text-slate-200 placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
                    />
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        disabled={busyId === item.query_id}
                        onClick={() => handleDecision(item, "rejected")}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-rose-500/40 bg-rose-500/15 px-4 py-2 text-xs font-semibold text-rose-300 hover:bg-rose-500/25 disabled:opacity-50 transition"
                      >
                        <XCircle className="h-3.5 w-3.5" /> Decline Query
                      </button>
                      <button
                        type="button"
                        disabled={busyId === item.query_id}
                        onClick={() => handleDecision(item, "approved")}
                        className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow hover:bg-emerald-500 disabled:opacity-50 transition"
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        {busyId === item.query_id
                          ? "Running Query..."
                          : "Approve & Run Query"}
                      </button>
                    </div>
                  </div>
                ) : (
                  item.reviewer_comment && (
                    <div className="text-xs text-slate-400">
                      Reviewer Note:{" "}
                      <span className="text-slate-200">
                        {item.reviewer_comment}
                      </span>
                    </div>
                  )
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
