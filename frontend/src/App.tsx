import React, { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Database,
  GitBranch,
  History,
  MessageSquarePlus,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { apiClient } from "./api/client";
import { ApprovalQueue } from "./components/approvals/ApprovalQueue";
import { QueryHistory } from "./components/history/QueryHistory";
import { InsightsPanel } from "./components/insights/InsightsPanel";
import { ResultsExplorer } from "./components/results/ResultsExplorer";
import { SchemaExplorer } from "./components/schema/SchemaExplorer";
import { SqlInspector } from "./components/sql/SqlInspector";
import { ExecutionTrace } from "./components/trace/ExecutionTrace";
import type {
  HealthStatus,
  QueryPilotRun,
  SchemaDiscoveryResponse,
} from "./types/querypilot";

const SAMPLE_QUESTIONS = [
  {
    label: "Top Revenue Categories",
    description: "See which product categories bring in the most sales",
    question: "Which product categories generate the most revenue?",
  },
  {
    label: "Monthly Sales Comparison",
    description: "Understand why revenue changed compared with last month",
    question: "Why did revenue decrease compared with the previous month?",
  },
  {
    label: "Order Value by Segment",
    description: "Compare average basket size across customer segments",
    question: "What is the average order value by customer segment?",
  },
  {
    label: "Declining Products",
    description: "Spot products whose sales dropped between Q2 and Q3",
    question: "Which products have declining sales?",
  },
  {
    label: "Cancellation Rates by Region",
    description: "Identify regions with the highest order cancellations",
    question: "Which regions have the highest order cancellation rates?",
  },
  {
    label: "Large Cross-Table Scan (Requires Approval)",
    description: "Test how heavy queries pause for your manual approval",
    question:
      "Run a cross join of every combination of customer and website event and order item",
  },
];

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<
    "playground" | "trace" | "schema" | "history" | "approvals"
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

  const sqlSectionRef = useRef<HTMLDivElement | null>(null);

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
    } catch {
    }
  };

  useEffect(() => {
    // Only load health, schema, and pending approval counts on mount — never auto-run queries
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
    } catch (err) {
      setErrorBanner(
        err instanceof Error ? err.message : "Failed to run analytics query"
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

  const showApprovalAlert =
    activeTab !== "approvals" &&
    (currentRun?.status === "awaiting_approval" || pendingApprovalsCount > 0);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <header className="sticky top-0 z-30 border-b border-slate-800/80 bg-slate-950/95 backdrop-blur px-6 py-3.5">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-indigo-600 shadow-lg shadow-emerald-500/20">
              <BarChart3 className="h-5 w-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-bold tracking-tight text-white">
                  QueryPilot
                </span>
                <span className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-400">
                  AI Business Analytics
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Ask questions in plain English • Get verified charts & insights
              </p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex flex-wrap items-center gap-1 rounded-xl border border-slate-800 bg-slate-900/90 p-1">
            {(
              [
                {
                  id: "playground",
                  label: "Workspace",
                  icon: Sparkles,
                },
                {
                  id: "approvals",
                  label: "Pending Approvals",
                  icon: ShieldAlert,
                  badge: pendingApprovalsCount,
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
                {
                  id: "trace",
                  label: "Workflow Steps",
                  icon: GitBranch,
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
                  className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-medium transition ${
                    active
                      ? "bg-emerald-600 text-white shadow"
                      : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  <span>{tab.label}</span>
                  {"badge" in tab && tab.badge > 0 && (
                    <span className="ml-1 inline-flex items-center justify-center rounded-full bg-amber-500 px-1.5 py-0.5 text-[10px] font-bold text-slate-950 animate-pulse">
                      {tab.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* Clean Read-Only Status Pill (Configured via .env) */}
          <div className="hidden lg:flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-300">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
              {health?.database.connected
                ? "Safe Read-Only Mode Active"
                : "Connecting to Database..."}
            </span>
          </div>
        </div>
      </header>

      {showApprovalAlert && (
        <div className="border-b border-amber-500/40 bg-amber-950/60 px-6 py-3">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-amber-500/20 text-amber-400">
                <AlertTriangle className="h-4 w-4 animate-bounce" />
              </span>
              <div className="text-xs sm:text-sm text-amber-100">
                <strong className="font-semibold text-amber-300">
                  Action Required:
                </strong>{" "}
                {currentRun?.status === "awaiting_approval"
                  ? "Your query scans a large volume of data and is paused waiting for your approval."
                  : `You have ${pendingApprovalsCount} pending query ${
                      pendingApprovalsCount === 1 ? "request" : "requests"
                    } waiting for review.`}
              </div>
            </div>
            <button
              type="button"
              onClick={() => setActiveTab("approvals")}
              className="inline-flex items-center gap-1.5 rounded-xl bg-amber-500 px-4 py-1.5 text-xs font-bold text-slate-950 shadow hover:bg-amber-400 transition"
            >
              <span>Go to Pending Approvals</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-6 space-y-6">
        {activeTab === "playground" && (
          <div className="space-y-6">
            <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 shadow-lg space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-xs font-medium text-slate-300">
                  {conversationHistory.length > 0 ? (
                    <span className="inline-flex items-center gap-1.5 text-emerald-400">
                      <Sparkles className="h-3.5 w-3.5" />
                      Follow-up mode active ({conversationHistory.length}{" "}
                      {conversationHistory.length === 1
                        ? "question"
                        : "questions"}{" "}
                      in this conversation)
                    </span>
                  ) : (
                    <span className="text-slate-400">
                      Ask any question about your store&apos;s revenue, orders,
                      products, customers, or regions
                    </span>
                  )}
                </div>
                {(conversationHistory.length > 0 || currentRun !== null) && (
                  <button
                    type="button"
                    onClick={handleStartNewThread}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700 transition"
                  >
                    <MessageSquarePlus className="h-3.5 w-3.5 text-emerald-400" />
                    Start New Topic
                  </button>
                )}
              </div>

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleAskQuestion();
                }}
                className="flex flex-col gap-2.5 sm:flex-row"
              >
                <input
                  type="text"
                  value={questionInput}
                  onChange={(e) => setQuestionInput(e.target.value)}
                  placeholder="e.g., Which product categories generate the most revenue?"
                  className="flex-1 rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={loading || !questionInput.trim()}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-6 py-3 text-sm font-semibold text-white shadow hover:bg-emerald-500 disabled:opacity-50 transition"
                >
                  <Send className="h-4 w-4" />
                  {loading
                    ? "Analyzing Data..."
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

            {/* Prominent Inline Callout when Current Run Pauses for Human Approval */}
            {currentRun?.status === "awaiting_approval" && (
              <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border-2 border-amber-500/60 bg-amber-950/40 p-5 shadow-lg">
                <div className="flex items-start gap-3.5">
                  <AlertTriangle className="h-6 w-6 text-amber-400 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <div className="text-base font-bold text-amber-200">
                      Approval Needed Before Running This Query
                    </div>
                    <p className="text-xs sm:text-sm text-amber-200/90 max-w-2xl">
                      {currentRun.cost_estimate?.approval_reason ||
                        "This query joins a large number of records. Please review and approve it in the Pending Approvals tab to continue."}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveTab("approvals")}
                  className="inline-flex items-center gap-2 rounded-xl bg-amber-500 px-5 py-2.5 text-xs sm:text-sm font-bold text-slate-950 shadow hover:bg-amber-400 transition"
                >
                  <span>Review in Pending Approvals</span>
                  <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            )}

            {!currentRun && !loading && (
              <div className="space-y-3">
                <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 px-1">
                  Popular Questions to Try (Click any card to run):
                </div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {SAMPLE_QUESTIONS.map((item) => (
                    <button
                      key={item.label}
                      type="button"
                      onClick={() => handleAskQuestion(item.question)}
                      className="group flex flex-col justify-between rounded-2xl border border-slate-800 bg-slate-900/70 p-4 text-left hover:border-emerald-500/50 hover:bg-slate-900 transition"
                    >
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-emerald-400 group-hover:text-emerald-300">
                            {item.label}
                          </span>
                          <ArrowRight className="h-3.5 w-3.5 text-slate-500 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition" />
                        </div>
                        <p className="text-sm font-medium text-slate-100">
                          &ldquo;{item.question}&rdquo;
                        </p>
                      </div>
                      <p className="mt-3 text-xs text-slate-400">
                        {item.description}
                      </p>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {loading && (
              <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-10 text-center space-y-2">
                <div className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-400 animate-pulse">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div className="text-sm font-semibold text-slate-200">
                  Analyzing your question with Gemini...
                </div>
                <p className="text-xs text-slate-400">
                  Checking available tables, verifying query safety, running on
                  read-only data, and building your chart.
                </p>
              </div>
            )}

            {!loading && currentRun && (
              <>
                <InsightsPanel
                  currentRun={currentRun}
                  onSelectFollowUp={(q) => handleAskQuestion(q)}
                  onJumpToSql={() =>
                    sqlSectionRef.current?.scrollIntoView({
                      behavior: "smooth",
                    })
                  }
                  onToggleBookmark={handleToggleBookmarkCurrent}
                />

                <ResultsExplorer currentRun={currentRun} />

                <div ref={sqlSectionRef}>
                  <SqlInspector
                    currentRun={currentRun}
                    onRunUpdated={(updated) => {
                      setCurrentRun(updated);
                      refreshSystemStatus();
                    }}
                    onOpenApprovals={() => setActiveTab("approvals")}
                  />
                </div>
              </>
            )}
          </div>
        )}

        {activeTab === "trace" && <ExecutionTrace currentRun={currentRun} />}

        {activeTab === "schema" && <SchemaExplorer schema={schema} />}

        {activeTab === "history" && (
          <QueryHistory
            onSelectQuery={(run) => {
              setCurrentRun(run);
              setQuestionInput(run.question);
              setActiveTab("playground");
            }}
          />
        )}

        {activeTab === "approvals" && (
          <ApprovalQueue
            onApprovalResolved={(resumed) => {
              setCurrentRun(resumed);
              refreshSystemStatus();
              setActiveTab("playground");
            }}
          />
        )}
      </main>
    </div>
  );
};

export default App;
