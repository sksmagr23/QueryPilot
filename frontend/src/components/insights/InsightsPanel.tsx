import React from "react";
import {
  AlertCircle,
  ArrowRight,
  Bookmark,
  CheckCircle2,
  Code2,
  FileCheck2,
  HelpCircle,
  Lightbulb,
  Scale,
} from "lucide-react";
import type { QueryPilotRun } from "../../types/querypilot";

interface InsightsPanelProps {
  currentRun: QueryPilotRun | null;
  onSelectFollowUp: (question: string) => void;
  onJumpToSql: () => void;
  onToggleBookmark: () => void;
}

export const InsightsPanel: React.FC<InsightsPanelProps> = ({
  currentRun,
  onSelectFollowUp,
  onJumpToSql,
  onToggleBookmark,
}) => {
  if (!currentRun || !currentRun.response) {
    return null;
  }

  const resp = currentRun.response;
  const statusConfig =
    currentRun.status === "completed"
      ? {
          label: "Verified Answer",
          cls: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
        }
      : currentRun.status === "awaiting_approval"
        ? {
            label: "Waiting for Approval",
            cls: "border-amber-500/40 bg-amber-500/10 text-amber-300",
          }
        : currentRun.status === "clarification_needed"
          ? {
              label: "Needs Clarification",
              cls: "border-indigo-500/40 bg-indigo-500/10 text-indigo-300",
            }
          : {
              label: "Request Declined",
              cls: "border-rose-500/40 bg-rose-500/10 text-rose-300",
            };

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-6 shadow-md space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-800 pb-4">
        <div className="space-y-1.5 max-w-3xl">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-0.5 text-xs font-semibold ${statusConfig.cls}`}
            >
              {statusConfig.label}
            </span>
          </div>
          <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2 pt-1">
            <Lightbulb className="h-5 w-5 text-emerald-400 shrink-0" />
            {resp.headline}
          </h2>
          <p className="text-sm text-slate-300 leading-relaxed">
            {resp.summary}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onToggleBookmark}
            className={`inline-flex items-center gap-1.5 rounded-xl border px-3.5 py-2 text-xs font-medium transition ${
              currentRun.bookmarked
                ? "border-amber-500/50 bg-amber-500/20 text-amber-300"
                : "border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700"
            }`}
          >
            <Bookmark className="h-3.5 w-3.5" />
            {currentRun.bookmarked ? "Saved Report" : "Save Report"}
          </button>
          {resp.sql_reference && (
            <button
              type="button"
              onClick={onJumpToSql}
              className="inline-flex items-center gap-1.5 rounded-xl border border-indigo-500/40 bg-indigo-500/15 px-3.5 py-2 text-xs font-medium text-indigo-300 hover:bg-indigo-500/25 transition"
            >
              <Code2 className="h-3.5 w-3.5" />
              View Query
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
          <div className="mb-2.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-emerald-400">
            <FileCheck2 className="h-4 w-4" /> Key Takeaways
          </div>
          <ul className="space-y-2 text-xs text-slate-200 leading-relaxed">
            {resp.key_findings.map((finding, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0 mt-0.5" />
                <span>{finding}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
          <div className="mb-2.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-indigo-400">
            <Scale className="h-4 w-4" /> How This Was Calculated
          </div>
          <ul className="space-y-2 text-xs text-slate-300 list-disc pl-4 leading-relaxed">
            {resp.assumptions.map((item, idx) => (
              <li key={idx}>{item}</li>
            ))}
          </ul>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
          <div className="mb-2.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-amber-400">
            <AlertCircle className="h-4 w-4" /> Things to Keep in Mind
          </div>
          <ul className="space-y-2 text-xs text-slate-300 list-disc pl-4 leading-relaxed">
            {resp.limitations.map((item, idx) => (
              <li key={idx}>{item}</li>
            ))}
          </ul>
        </div>
      </div>

      {resp.follow_up_suggestions && resp.follow_up_suggestions.length > 0 && (
        <div className="pt-1">
          <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-slate-400">
            <HelpCircle className="h-3.5 w-3.5 text-indigo-400" />
            Explore further with a follow-up question:
          </div>
          <div className="flex flex-wrap gap-2">
            {resp.follow_up_suggestions.map((suggestion, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => onSelectFollowUp(suggestion)}
                className="inline-flex items-center gap-1.5 rounded-full border border-slate-700 bg-slate-800/80 px-3.5 py-1.5 text-xs text-slate-200 hover:border-emerald-500/50 hover:bg-emerald-500/10 hover:text-emerald-300 transition"
              >
                <span>{suggestion}</span>
                <ArrowRight className="h-3 w-3" />
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
