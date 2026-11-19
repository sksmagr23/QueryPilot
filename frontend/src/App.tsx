import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  ChevronDown,
  Database,
  History,
  Lock,
  MessageSquarePlus,
  Send,
  ShieldAlert,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { apiClient } from "./api/client";
import { ApprovalQueue } from "./components/approvals/ApprovalQueue";
import { QueryHistory } from "./components/history/QueryHistory";
import { InsightsPanel } from "./components/insights/InsightsPanel";
import { ResultsExplorer } from "./components/results/ResultsExplorer";
import { SchemaExplorer } from "./components/schema/SchemaExplorer";
import { SqlInspector } from "./components/sql/SqlInspector";
import type {
  HealthStatus,
  QueryPilotRun,
  SchemaDiscoveryResponse,
} from "./types/querypilot";

const SAMPLE_QUESTIONS = [
  {
    label: "Top Revenue Categories",
    description: "Discover which product categories drive the highest sales",
    question: "Which product categories generate the most revenue?",
  },
  {
    label: "Monthly Sales Shift",
    description: "Compare recent monthly performance and identify key drivers",
    question: "Why did revenue decrease compared with the previous month?",
  },
  {
    label: "Order Value by Segment",
    description: "Compare average basket size across customer segments",
    question: "What is the average order value by customer segment?",
  },
  {
    label: "Declining Products",
    description: "Spot products whose sales decreased between Q2 and Q3",
    question: "Which products have declining sales?",
  },
  {
    label: "Regional Cancellations",
    description: "Identify regions with the highest order cancellation rates",
    question: "Which regions have the highest order cancellation rates?",
  },
  {
    label: "Full Cross-Dataset Scan (Triggers Approval)",
    description: "Preview how high-cost queries open the Approvals dropdown",
    question:
      "Run a cross join of every combination of customer and website event and order item",
  },
];

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<
    "playground" | "history" | "schema"
  >("playground");
  const [questionInput, setQuestionInput] = useState<string>("");
  const [currentRun, setCurrentRun] = useState<QueryPilotRun | null>(null);
  const [conversationHistory, setConversationHistory] = useState<
    Array<Record<string, string>>
  >([]);
  const [threadId, setThreadId] = useState<string>(
    () => `thread_${Math.random().toString(36).slice(2, 10)}`
  );
  const [loading, setLoading] = useState<boolean>(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [schema, setSchema] = useState<SchemaDiscoveryResponse | null>(null);
  const [pendingApprovalsCount, setPendingApprovalsCount] = useState<number>(0);

  // Approvals Overlay Dropdown state
  const [showApprovalsDropdown, setShowApprovalsDropdown] =
    useState<boolean>(false);
  const [approvalsRefreshTrigger, setApprovalsRefreshTrigger] =
    useState<number>(0);

  const refreshSystemStatus = async () => {
    try {
      const [h, s, app] = await Promise.all([
        apiClient.getHealth(),
        apiClient.getSchema(),
        apiClient.getApprovals("pending"),
      ]);
      setHealth(h);
      setSchema(s);
      setPendingApprovalsCount(app.pending_count);
      setApprovalsRefreshTrigger((n) => n + 1);
    } catch {
      // backend might still be booting
    }
  };

  useEffect(() => {
    refreshSystemStatus();
  }, []);

  const handleAskQuestion = async (overrideQuestion?: string) => {
    const q = (overrideQuestion ?? questionInput).trim();
    if (!q || loading) return;
    if (overrideQuestion) setQuestionInput(overrideQuestion);

    setLoading(true);
    setErrorBanner(null);
    try {
      const run = await apiClient.runQuery({
        question: q,
        thread_id: threadId,
        conversation_history: conversationHistory,
      });
      setCurrentRun(run);
      if (run.status === "completed" && run.response) {
        setConversationHistory((prev) => [
          ...prev,
          {
            question: q,
            sql: run.generated_sql || "",
            summary: run.response?.summary || "",
          },
        ]);
      }
      await refreshSystemStatus();
      // Automatically open the Approvals Overlay Dropdown when human approval is needed
      if (run.status === "awaiting_approval") {
        setShowApprovalsDropdown(true);
      }
    } catch (err) {
      setErrorBanner(
        err instanceof Error ? err.message : "Failed to run analytics question"
      );
    } finally {
      setLoading(false);
    }
  };

  const handleStartNewThread = () => {
    setThreadId(`thread_${Math.random().toString(36).slice(2, 10)}`);
    setConversationHistory([]);
    setCurrentRun(null);
    setQuestionInput("");
    setErrorBanner(null);
  };

  const handleToggleBookmarkCurrent = async () => {
    if (!currentRun) return;
    const updated = await apiClient.toggleBookmark(currentRun.query_id, {
      bookmarked: !currentRun.bookmarked,
    });
    setCurrentRun(updated);
  };

  const hasApprovalNeeded =
    currentRun?.status === "awaiting_approval" || pendingApprovalsCount > 0;

  const totalRecordsCount =
    schema?.tables.reduce((acc, t) => acc + (t.row_count || 0), 0) || 0;

  return (
    <div className="relative min-h-screen bg-[#06152B] text-[#EAF3FF] flex flex-col overflow-x-hidden">
      {/* Subtle Ambient Blue & Cyan Lighting */}
      <div className="pointer-events-none fixed -top-40 left-1/2 h-[420px] w-[780px] -translate-x-1/2 rounded-full bg-[#168BFF]/15 blur-[130px]" />
      <div className="pointer-events-none fixed top-40 right-10 h-72 w-72 rounded-full bg-[#00C8FF]/8 blur-[120px]" />

      {/* Top Navigation Header */}
      <header className="sticky top-0 z-40 border-b border-[#142F54]/80 bg-[#06152B]/90 backdrop-blur-xl px-6 py-4">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#168BFF] to-[#00C8FF] shadow-lg shadow-[#168BFF]/30">
              <BarChart3 className="h-5 w-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <span className="text-lg font-extrabold tracking-tight text-[#EAF3FF]">
                  QueryPilot
                </span>
                <span className="rounded-full border border-[#00C8FF]/30 bg-[#00C8FF]/10 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[#00C8FF]">
                  Business Intelligence
                </span>
              </div>
              <p className="text-xs text-[#91A9C5]">
                Instant data, interactive charts, SQL queries, and verified
                insights
              </p>
            </div>
          </div>

          {/* Centered Pill Navigation (No Separate Approvals Tab) */}
          <nav className="flex flex-wrap items-center gap-1 rounded-2xl border border-[#163661] bg-[#091D38]/90 p-1.5">
            {(
              [
                {
                  id: "playground",
                  label: "Analytics",
                  icon: Sparkles,
                },
                {
                  id: "history",
                  label: "Saved & History",
                  icon: History,
                },
                {
                  id: "schema",
                  label: "Data Catalog",
                  icon: Database,
                },
              ] as const
            ).map((tab) => {
              const Icon = tab.icon;
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold transition ${
                    active
                      ? "bg-[#168BFF] text-white shadow-md shadow-[#168BFF]/35"
                      : "text-[#91A9C5] hover:bg-[#0D274C] hover:text-[#EAF3FF]"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Right Side: Approvals Overlay Dropdown Button & Status Pill */}
          <div className="relative flex items-center gap-2.5">
            <span className="hidden xl:inline-flex items-center gap-2 rounded-full border border-[#163661] bg-[#0A1F3D] px-3.5 py-1.5 text-xs font-medium text-[#91A9C5]">
              <span
                className={`h-2 w-2 rounded-full ${
                  health?.database.connected ? "bg-[#00C8FF]" : "bg-amber-400"
                }`}
              />
              {health?.database.connected ? "Read-Only DB" : "Connecting..."}
            </span>

            {/* Approvals Overlay Dropdown Trigger Button */}
            <button
              type="button"
              onClick={() => setShowApprovalsDropdown((prev) => !prev)}
              className={`inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-bold transition ${
                hasApprovalNeeded
                  ? "border-[#00C8FF] bg-gradient-to-r from-[#168BFF]/30 to-[#00C8FF]/25 text-[#EAF3FF] shadow-lg shadow-[#00C8FF]/20"
                  : "border-[#163661] bg-[#0A1F3D] text-[#EAF3FF] hover:border-[#168BFF]"
              }`}
            >
              <ShieldAlert
                className={`h-4 w-4 ${
                  hasApprovalNeeded ? "text-[#00C8FF] animate-bounce" : "text-[#91A9C5]"
                }`}
              />
              <span>Approvals</span>
              {pendingApprovalsCount > 0 && (
                <span className="inline-flex items-center justify-center rounded-full bg-[#00C8FF] px-1.5 py-0.5 text-[10px] font-extrabold text-[#06152B]">
                  {pendingApprovalsCount}
                </span>
              )}
              <ChevronDown
                className={`h-3.5 w-3.5 text-[#91A9C5] transition-transform ${
                  showApprovalsDropdown ? "rotate-180" : ""
                }`}
              />
            </button>

            {/* Approvals Overlay Dropdown Panel */}
            {showApprovalsDropdown && (
              <>
                <div
                  className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]"
                  onClick={() => setShowApprovalsDropdown(false)}
                />
                <div className="fixed right-4 top-20 z-50 w-[92vw] max-w-xl">
                  <ApprovalQueue
                    refreshTrigger={approvalsRefreshTrigger}
                    onClose={() => setShowApprovalsDropdown(false)}
                    onApprovalResolved={(resumed) => {
                      setCurrentRun(resumed);
                      setShowApprovalsDropdown(false);
                      refreshSystemStatus();
                      setActiveTab("playground");
                    }}
                  />
                </div>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Top Notification Bar when Approval is Needed */}
      {hasApprovalNeeded && (
        <div className="relative z-20 border-b border-[#00C8FF]/40 bg-gradient-to-r from-[#0A2348] via-[#0E2F61] to-[#0A2348] px-6 py-3">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#00C8FF]/20 text-[#00C8FF]">
                <AlertTriangle className="h-4 w-4" />
              </span>
              <div className="text-xs sm:text-sm text-[#EAF3FF]">
                <strong className="font-bold text-[#00C8FF]">
                  Approval Needed:
                </strong>{" "}
                {currentRun?.status === "awaiting_approval"
                  ? currentRun.cost_estimate?.approval_reason ||
                    "This query has a high estimated database cost and requires your confirmation."
                  : `You have ${pendingApprovalsCount} high-cost query ${
                      pendingApprovalsCount === 1 ? "request" : "requests"
                    } waiting for review.`}
              </div>
            </div>
            <button
              type="button"
              onClick={() => setShowApprovalsDropdown(true)}
              className="inline-flex items-center gap-1.5 rounded-xl bg-[#00C8FF] px-4 py-1.5 text-xs font-bold text-[#06152B] shadow hover:bg-[#00C8FF]/90 transition"
            >
              <span>Review & Approve in Dropdown</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Main Content Container */}
      <main className="relative z-10 mx-auto w-full max-w-6xl flex-1 px-6 py-8 space-y-8">
        {activeTab === "playground" && (
          <div className="space-y-8">
            {/* Spacious Centered Hero & Question Bar */}
            <div className="mx-auto max-w-4xl text-center space-y-4 pt-2">
              <div className="inline-flex items-center gap-2 rounded-full border border-[#1B3F70] bg-[#0A1F3D]/80 px-4 py-1.5 text-xs font-semibold text-[#00C8FF]">
                <Sparkles className="h-3.5 w-3.5" />
                <span>AI-Powered Store Analytics</span>
              </div>
              <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[#EAF3FF]">
                Ask anything about your business performance
              </h1>
              <p className="mx-auto max-w-2xl text-sm sm:text-base text-[#91A9C5]">
                Explore revenue trends, customer segments, product performance,
                and regional orders in plain English.
              </p>
            </div>

            {/* Horizontal Statistics & Feature Strip */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="flex items-center gap-3.5 rounded-2xl border border-[#163661] bg-[#091D38]/80 px-5 py-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#168BFF]/15 text-[#00C8FF]">
                  <Database className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-xs font-medium text-[#91A9C5]">
                    Connected Datasets
                  </div>
                  <div className="text-sm font-bold text-[#EAF3FF]">
                    {schema
                      ? `${schema.tables.length} Store Tables`
                      : "7 Store Tables"}{" "}
                    {totalRecordsCount > 0 &&
                      `• ${totalRecordsCount.toLocaleString()} Records`}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3.5 rounded-2xl border border-[#163661] bg-[#091D38]/80 px-5 py-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#168BFF]/15 text-[#00C8FF]">
                  <CheckCircle2 className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-xs font-medium text-[#91A9C5]">
                    Output & Transparency
                  </div>
                  <div className="text-sm font-bold text-[#EAF3FF]">
                    Data Tables, Charts, SQL & DB Cost
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3.5 rounded-2xl border border-[#163661] bg-[#091D38]/80 px-5 py-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#168BFF]/15 text-[#00C8FF]">
                  <Lock className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-xs font-medium text-[#91A9C5]">
                    Data Protection
                  </div>
                  <div className="text-sm font-bold text-[#EAF3FF]">
                    Read-Only Access & Cost Approval
                  </div>
                </div>
              </div>
            </div>

            {/* Search Input Card */}
            <div className="rounded-2xl border border-[#1B3F70] bg-gradient-to-b from-[#0B2244] to-[#081A35] p-6 shadow-[0_20px_50px_rgba(3,10,24,0.55)] space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-xs font-medium text-[#91A9C5]">
                  {conversationHistory.length > 0 ? (
                    <span className="inline-flex items-center gap-1.5 text-[#00C8FF]">
                      <TrendingUp className="h-3.5 w-3.5" />
                      Follow-up mode active ({conversationHistory.length}{" "}
                      {conversationHistory.length === 1
                        ? "question"
                        : "questions"}{" "}
                      in this thread)
                    </span>
                  ) : (
                    <span>
                      Type a question below or pick a starter topic to begin
                    </span>
                  )}
                </div>
                {(conversationHistory.length > 0 || currentRun !== null) && (
                  <button
                    type="button"
                    onClick={handleStartNewThread}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-[#1B3F70] bg-[#0D2548] px-3.5 py-1.5 text-xs font-semibold text-[#EAF3FF] hover:border-[#168BFF] transition"
                  >
                    <MessageSquarePlus className="h-3.5 w-3.5 text-[#00C8FF]" />
                    New Topic
                  </button>
                )}
              </div>

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleAskQuestion();
                }}
                className="flex flex-col gap-3 sm:flex-row"
              >
                <input
                  type="text"
                  value={questionInput}
                  onChange={(e) => setQuestionInput(e.target.value)}
                  placeholder="e.g., Which product categories generate the most revenue?"
                  className="flex-1 rounded-xl border border-[#1B3F70] bg-[#06152B] px-5 py-3.5 text-sm text-[#EAF3FF] placeholder-[#91A9C5]/60 focus:border-[#168BFF] focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={loading || !questionInput.trim()}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#168BFF] to-[#00C8FF] px-7 py-3.5 text-sm font-bold text-[#06152B] shadow-lg shadow-[#168BFF]/30 hover:opacity-95 disabled:opacity-40 transition"
                >
                  <Send className="h-4 w-4" />
                  {loading
                    ? "Analyzing..."
                    : conversationHistory.length > 0
                      ? "Ask Follow-Up"
                      : "Get Answer"}
                </button>
              </form>
            </div>

            {errorBanner && (
              <div className="rounded-2xl border border-rose-500/40 bg-rose-500/10 p-4 text-xs text-rose-300">
                {errorBanner}
              </div>
            )}

            {/* Inline Callout when Current Run Pauses for Human Approval */}
            {currentRun?.status === "awaiting_approval" && (
              <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-[#00C8FF]/50 bg-[#0A2246] p-6 shadow-xl">
                <div className="flex items-start gap-4">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#00C8FF]/15 text-[#00C8FF] shrink-0">
                    <AlertTriangle className="h-6 w-6" />
                  </div>
                  <div className="space-y-1">
                    <div className="text-base font-bold text-[#EAF3FF]">
                      Approval Needed Before Running This Query
                    </div>
                    <p className="text-xs sm:text-sm text-[#91A9C5] max-w-2xl">
                      <strong className="text-[#00C8FF]">Reason:</strong>{" "}
                      {currentRun.cost_estimate?.approval_reason ||
                        "Estimated database cost exceeds threshold and requires human confirmation."}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setShowApprovalsDropdown(true)}
                  className="inline-flex items-center gap-2 rounded-xl bg-[#168BFF] px-5 py-2.5 text-xs sm:text-sm font-bold text-white shadow-md shadow-[#168BFF]/35 hover:bg-[#168BFF]/90 transition"
                >
                  <span>Open Approvals Dropdown</span>
                  <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            )}

            {/* Starter Topics Grid (Never auto-runs on page load) */}
            {!currentRun && !loading && (
              <div className="space-y-3.5">
                <div className="text-xs font-bold uppercase tracking-wider text-[#91A9C5] px-1">
                  Starter Questions
                </div>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {SAMPLE_QUESTIONS.map((item) => (
                    <button
                      key={item.label}
                      type="button"
                      onClick={() => handleAskQuestion(item.question)}
                      className="group flex flex-col justify-between rounded-2xl border border-[#163661] bg-[#091D38]/80 p-5 text-left hover:border-[#168BFF] hover:bg-[#0C2548] transition shadow-sm"
                    >
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-[#00C8FF]">
                            {item.label}
                          </span>
                          <ArrowRight className="h-3.5 w-3.5 text-[#91A9C5] group-hover:text-[#00C8FF] group-hover:translate-x-0.5 transition" />
                        </div>
                        <p className="text-sm font-semibold text-[#EAF3FF] leading-snug">
                          &ldquo;{item.question}&rdquo;
                        </p>
                      </div>
                      <p className="mt-4 text-xs text-[#91A9C5]">
                        {item.description}
                      </p>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Loading State */}
            {loading && (
              <div className="rounded-2xl border border-[#163661] bg-[#091D38]/80 p-12 text-center space-y-3">
                <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-[#168BFF]/20 text-[#00C8FF] animate-pulse">
                  <Sparkles className="h-6 w-6" />
                </div>
                <div className="text-base font-bold text-[#EAF3FF]">
                  Preparing your answer...
                </div>
                <p className="text-xs text-[#91A9C5]">
                  Generating SQL, estimating database cost, running query, and
                  building your chart.
                </p>
              </div>
            )}

            {/* Results First (Output Data, Graphs, SQL Query & DB Cost), Then Insights & Follow-Up Recommendations */}
            {!loading && currentRun && (
              <div className="space-y-6">
                {/* 1. Output Data, DB Cost/Time Strip, KPIs, Graphs & Table */}
                <ResultsExplorer currentRun={currentRun} />

                {/* 2. SQL Query & Database Cost Inspector */}
                <SqlInspector
                  currentRun={currentRun}
                  onRunUpdated={(updated) => {
                    setCurrentRun(updated);
                    refreshSystemStatus();
                    if (updated.status === "awaiting_approval") {
                      setShowApprovalsDropdown(true);
                    }
                  }}
                  onOpenApprovalsDropdown={() => setShowApprovalsDropdown(true)}
                />

                {/* 3. Insights & Follow-Up Recommendations */}
                <InsightsPanel
                  currentRun={currentRun}
                  onSelectFollowUp={(q) => handleAskQuestion(q)}
                  onToggleBookmark={handleToggleBookmarkCurrent}
                />
              </div>
            )}
          </div>
        )}

        {activeTab === "history" && (
          <QueryHistory
            onSelectQuery={(run) => {
              setCurrentRun(run);
              setQuestionInput(run.question);
              setActiveTab("playground");
            }}
          />
        )}

        {activeTab === "schema" && <SchemaExplorer schema={schema} />}
      </main>
    </div>
  );
};

export default App;
