import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Code2,
  Gauge,
  ShieldAlert,
  X,
  XCircle,
} from "lucide-react";
import { apiClient } from "../../api/client";
import type { ApprovalItem, QueryPilotRun } from "../../types/querypilot";

interface ApprovalQueueProps {
  onApprovalResolved: (resumedRun: QueryPilotRun) => void;
  onClose?: () => void;
  refreshTrigger?: number;
}

export const ApprovalQueue: React.FC<ApprovalQueueProps> = ({
  onApprovalResolved,
  onClose,
  refreshTrigger = 0,
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
  }, [refreshTrigger]);

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

  const pendingItems = items.filter((i) => i.approval_status === "pending");
  const recentResolved = items
    .filter((i) => i.approval_status !== "pending")
    .slice(0, 3);

  return (
    <div className="w-full max-w-xl rounded-2xl border border-[#00C8FF]/40 bg-[#081B36] shadow-[0_25px_70px_rgba(2,8,20,0.85)] overflow-hidden">
      {/* Dropdown Header */}
      <div className="flex items-center justify-between border-b border-[#163661] bg-[#0B2345] px-5 py-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#00C8FF]/30 bg-[#168BFF]/20 text-[#00C8FF]">
            <ShieldAlert className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-[#EAF3FF]">
              Query Approval Center ({pendingItems.length} Pending)
            </h3>
            <p className="text-[11px] text-[#91A9C5]">
              High-cost database queries require your confirmation before
              running
            </p>
          </div>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[#1B3F70] bg-[#06152B] p-1.5 text-[#91A9C5] hover:border-[#168BFF] hover:text-[#EAF3FF] transition"
            title="Close"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="max-h-[75vh] overflow-y-auto p-5 space-y-4">
        {errorMsg && (
          <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-3.5 text-xs text-rose-300">
            {errorMsg}
          </div>
        )}

        {pendingItems.length === 0 ? (
          <div className="rounded-xl border border-[#163661] bg-[#06152B]/70 p-6 text-center space-y-1">
            <div className="text-xs font-semibold text-[#EAF3FF]">
              No queries waiting for approval
            </div>
            <p className="text-[11px] text-[#91A9C5]">
              When a query scans a large volume of records or has high database
              cost, it will appear here for your confirmation.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {pendingItems.map((item) => (
              <div
                key={item.query_id}
                className="rounded-xl border border-[#00C8FF]/50 bg-[#0B2345]/95 p-4 space-y-3.5 shadow-md"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="space-y-1">
                    <span className="inline-flex items-center gap-1 rounded-full border border-[#00C8FF]/40 bg-[#00C8FF]/15 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[#00C8FF]">
                      Approval Needed
                    </span>
                    <div className="font-bold text-sm text-[#EAF3FF]">
                      {item.question}
                    </div>
                  </div>
                  <span className="inline-flex items-center gap-1 rounded-full border border-[#1B3F70] bg-[#06152B] px-2.5 py-1 text-[11px] font-semibold text-[#00C8FF]">
                    <Gauge className="h-3.5 w-3.5" />
                    DB Cost: {item.estimated_cost} ({item.risk_level})
                  </span>
                </div>

                {/* Need & Reason for Approval */}
                <div className="flex items-start gap-2.5 rounded-xl border border-amber-400/30 bg-amber-500/10 px-3.5 py-2.5 text-xs text-amber-200">
                  <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
                  <div>
                    <strong className="font-bold text-amber-300">
                      Why approval is needed:
                    </strong>{" "}
                    {item.approval_reason ||
                      "Estimated database cost exceeds the automatic execution threshold."}
                  </div>
                </div>

                {/* SQL Query Preview */}
                <div className="space-y-1">
                  <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[#91A9C5]">
                    <Code2 className="h-3.5 w-3.5 text-[#00C8FF]" />
                    SQL Query to Execute:
                  </div>
                  <pre className="max-h-36 overflow-auto rounded-xl border border-[#163661] bg-[#06152B] p-3 font-mono text-[11px] text-[#00C8FF]">
                    {item.generated_sql}
                  </pre>
                </div>

                {/* Note + Approve / Decline Buttons */}
                <div className="space-y-2.5 pt-1">
                  <input
                    type="text"
                    value={comments[item.query_id] || ""}
                    onChange={(e) =>
                      setComments({
                        ...comments,
                        [item.query_id]: e.target.value,
                      })
                    }
                    placeholder="Optional note before approving or declining..."
                    className="w-full rounded-xl border border-[#1B3F70] bg-[#06152B] px-3.5 py-2 text-xs text-[#EAF3FF] placeholder-[#91A9C5]/60 focus:border-[#168BFF] focus:outline-none"
                  />
                  <div className="flex items-center justify-end gap-2">
                    <button
                      type="button"
                      disabled={busyId === item.query_id}
                      onClick={() => handleDecision(item, "rejected")}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-rose-500/40 bg-rose-500/15 px-3.5 py-2 text-xs font-semibold text-rose-300 hover:bg-rose-500/25 disabled:opacity-50 transition"
                    >
                      <XCircle className="h-3.5 w-3.5" /> Decline
                    </button>
                    <button
                      type="button"
                      disabled={busyId === item.query_id}
                      onClick={() => handleDecision(item, "approved")}
                      className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-[#168BFF] to-[#00C8FF] px-4 py-2 text-xs font-bold text-[#06152B] shadow-md shadow-[#168BFF]/30 hover:opacity-95 disabled:opacity-50 transition"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      {busyId === item.query_id
                        ? "Running Query..."
                        : "Approve & Run Query"}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Recent Resolved History */}
        {recentResolved.length > 0 && (
          <div className="pt-2 border-t border-[#163661] space-y-2">
            <div className="text-[11px] font-bold uppercase tracking-wider text-[#91A9C5]">
              Recently Reviewed
            </div>
            {recentResolved.map((item) => (
              <div
                key={item.query_id}
                className="flex items-center justify-between gap-2 rounded-xl border border-[#163661] bg-[#06152B]/60 px-3.5 py-2 text-xs"
              >
                <span className="truncate text-[#91A9C5] max-w-xs">
                  {item.question}
                </span>
                <span
                  className={`rounded-full px-2.5 py-0.5 text-[10px] font-semibold capitalize ${
                    item.approval_status === "approved"
                      ? "bg-emerald-500/15 text-emerald-300"
                      : "bg-rose-500/15 text-rose-300"
                  }`}
                >
                  {item.approval_status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
