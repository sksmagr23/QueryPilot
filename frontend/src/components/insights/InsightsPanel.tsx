import React from "react";
import {
  AlertCircle,
  ArrowRight,
  Bookmark,
  CheckCircle2,
  Compass,
  Scale,
  Sparkles,
} from "lucide-react";
import type { QueryPilotRun } from "../../types/querypilot";

interface InsightsPanelProps {
  currentRun: QueryPilotRun | null;
  onSelectFollowUp: (question: string) => void;
  onToggleBookmark: () => void;
}

export const InsightsPanel: React.FC<InsightsPanelProps> = ({
  currentRun,
  onSelectFollowUp,
  onToggleBookmark,
}) => {
  if (!currentRun || !currentRun.response) {
    return null;
  }

  const resp = currentRun.response;
  const statusConfig =
    currentRun.status === "completed"
      ? {
          label: "Verified Insight",
          cls: "border-[#00C8FF]/30 bg-[#00C8FF]/10 text-[#00C8FF]",
        }
      : currentRun.status === "awaiting_approval"
        ? {
            label: "Pending Review",
            cls: "border-amber-400/30 bg-amber-400/10 text-amber-300",
          }
        : currentRun.status === "clarification_needed"
          ? {
              label: "Clarification Needed",
              cls: "border-[#168BFF]/40 bg-[#168BFF]/15 text-[#EAF3FF]",
            }
          : {
              label: "Outside Available Scope",
              cls: "border-rose-400/30 bg-rose-500/10 text-rose-300",
            };

  return (
    <section className="relative overflow-hidden rounded-2xl border border-[#163661] bg-gradient-to-b from-[#0A1F3D]/95 to-[#071830]/95 p-7 shadow-[0_20px_50px_rgba(3,10,24,0.6)]">
      {/* Subtle Top Ambient Glow */}
      <div className="pointer-events-none absolute -top-24 left-1/2 h-48 w-96 -translate-x-1/2 rounded-full bg-[#168BFF]/15 blur-3xl" />

      <div className="relative space-y-6">
        {/* Top Row: Status Badge + Headline + Save Button */}
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[#163661]/80 pb-6">
          <div className="space-y-2.5 max-w-3xl">
            <div className="flex items-center gap-2.5">
              <span
                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-semibold tracking-wide uppercase ${statusConfig.cls}`}
              >
                <Sparkles className="h-3 w-3" />
                {statusConfig.label}
              </span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-[#EAF3FF]">
              {resp.headline}
            </h2>
            <p className="text-sm sm:text-base text-[#91A9C5] leading-relaxed">
              {resp.summary}
            </p>
          </div>

          <button
            type="button"
            onClick={onToggleBookmark}
            className={`inline-flex items-center gap-2 rounded-xl border px-4 py-2 text-xs font-semibold transition ${
              currentRun.bookmarked
                ? "border-[#00C8FF]/50 bg-[#00C8FF]/15 text-[#00C8FF]"
                : "border-[#1B3F70] bg-[#0D2548] text-[#EAF3FF] hover:border-[#168BFF] hover:bg-[#12305C]"
            }`}
          >
            <Bookmark className="h-3.5 w-3.5" />
            {currentRun.bookmarked ? "Saved Report" : "Save Report"}
          </button>
        </div>

        {/* Three-Column Insight Cards */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          <div className="rounded-xl border border-[#163661] bg-[#06152B]/70 p-5">
            <div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#00C8FF]">
              <CheckCircle2 className="h-4 w-4" /> Key Takeaways
            </div>
            <ul className="space-y-2.5 text-xs sm:text-sm text-[#EAF3FF]/90 leading-relaxed">
              {resp.key_findings.map((finding, idx) => (
                <li key={idx} className="flex items-start gap-2.5">
                  <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-[#00C8FF] shrink-0" />
                  <span>{finding}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-xl border border-[#163661] bg-[#06152B]/70 p-5">
            <div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#168BFF]">
              <Scale className="h-4 w-4" /> Calculation Basis
            </div>
            <ul className="space-y-2 text-xs sm:text-sm text-[#91A9C5] leading-relaxed">
              {resp.assumptions.map((item, idx) => (
                <li key={idx} className="flex items-start gap-2.5">
                  <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-[#168BFF] shrink-0" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-xl border border-[#163661] bg-[#06152B]/70 p-5">
            <div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#91A9C5]">
              <AlertCircle className="h-4 w-4 text-[#00C8FF]" /> Scope & Notes
            </div>
            <ul className="space-y-2 text-xs sm:text-sm text-[#91A9C5] leading-relaxed">
              {resp.limitations.map((item, idx) => (
                <li key={idx} className="flex items-start gap-2.5">
                  <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-[#91A9C5] shrink-0" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Suggested Follow-Up Strip */}
        {resp.follow_up_suggestions && resp.follow_up_suggestions.length > 0 && (
          <div className="pt-1">
            <div className="mb-2.5 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#91A9C5]">
              <Compass className="h-3.5 w-3.5 text-[#00C8FF]" />
              Continue Exploring
            </div>
            <div className="flex flex-wrap gap-2.5">
              {resp.follow_up_suggestions.map((suggestion, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => onSelectFollowUp(suggestion)}
                  className="inline-flex items-center gap-2 rounded-full border border-[#1B3F70] bg-[#0C2242] px-4 py-1.5 text-xs font-medium text-[#EAF3FF] hover:border-[#00C8FF]/60 hover:bg-[#168BFF]/20 hover:text-white transition"
                >
                  <span>{suggestion}</span>
                  <ArrowRight className="h-3 w-3 text-[#00C8FF]" />
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
};
