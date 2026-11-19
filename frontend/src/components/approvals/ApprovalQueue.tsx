import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
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
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#163661] bg-[#0A1F3D]/95 px-6 py-5 shadow-md">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#00C8FF]/30 bg-[#168BFF]/15 text-[#00C8FF]">
            <ShieldAlert className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-[#EAF3FF]">
              Pending Approvals ({pendingCount} waiting)
            </h2>
            <p className="text-xs text-[#91A9C5]">
              Large data queries pause here so you can confirm them before they
              run.
            </p>
          </div>
        </div>
      </div>

      {errorMsg && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-4 text-xs text-rose-300">
          {errorMsg}
        </div>
      )}

      {items.length === 0 ? (
        <div className="rounded-2xl border border-[#163661] bg-[#091D38]/60 p-12 text-center text-sm text-[#91A9C5]">
          No requests are waiting for your approval right now.
        </div>
      ) : (
        <div className="space-y-4">
          {items.map((item) => {
            const isPending = item.approval_status === "pending";
            return (
              <div
                key={item.query_id}
                className={`rounded-2xl border p-6 space-y-4 transition ${
                  isPending
                    ? "border-[#00C8FF]/50 bg-[#0A1F3D] shadow-lg shadow-[#168BFF]/10"
                    : "border-[#163661] bg-[#081A33]/80"
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <span className="font-bold text-base text-[#EAF3FF]">
                      {item.question}
                    </span>
                    <span
                      className={`rounded-full px-3 py-0.5 text-[11px] font-semibold ${
                        item.approval_status === "pending"
                          ? "bg-[#00C8FF]/15 text-[#00C8FF] border border-[#00C8FF]/40"
                          : item.approval_status === "approved"
                            ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                            : "bg-rose-500/15 text-rose-300 border border-rose-500/30"
                      }`}
                    >
                      {item.approval_status === "pending"
                        ? "Needs Your Approval"
                        : item.approval_status === "approved"
                          ? "Approved & Completed"
                          : "Declined"}
                    </span>
                  </div>
                </div>

                {item.approval_reason && (
                  <div className="flex items-start gap-2.5 rounded-xl border border-[#1B3F70] bg-[#06152B] px-4 py-3 text-xs text-[#91A9C5]">
                    <AlertTriangle className="h-4 w-4 text-[#00C8FF] shrink-0 mt-0.5" />
                    <span>
                      <strong className="text-[#EAF3FF]">
                        Why review is needed:
                      </strong>{" "}
                      {item.approval_reason}
                    </span>
                  </div>
                )}

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
                      placeholder="Add an optional note..."
                      className="flex-1 min-w-[240px] rounded-xl border border-[#1B3F70] bg-[#06152B] px-4 py-2 text-xs text-[#EAF3FF] placeholder-[#91A9C5]/60 focus:border-[#168BFF] focus:outline-none"
                    />
                    <div className="flex items-center gap-2.5">
                      <button
                        type="button"
                        disabled={busyId === item.query_id}
                        onClick={() => handleDecision(item, "rejected")}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-rose-500/40 bg-rose-500/15 px-4 py-2 text-xs font-semibold text-rose-300 hover:bg-rose-500/25 disabled:opacity-50 transition"
                      >
                        <XCircle className="h-3.5 w-3.5" /> Decline
                      </button>
                      <button
                        type="button"
                        disabled={busyId === item.query_id}
                        onClick={() => handleDecision(item, "approved")}
                        className="inline-flex items-center gap-1.5 rounded-xl bg-[#168BFF] px-5 py-2 text-xs font-semibold text-white shadow-md shadow-[#168BFF]/30 hover:bg-[#168BFF]/90 disabled:opacity-50 transition"
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        {busyId === item.query_id
                          ? "Running..."
                          : "Approve & Run"}
                      </button>
                    </div>
                  </div>
                ) : (
                  item.reviewer_comment && (
                    <div className="text-xs text-[#91A9C5]">
                      Note:{" "}
                      <span className="text-[#EAF3FF]">
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
