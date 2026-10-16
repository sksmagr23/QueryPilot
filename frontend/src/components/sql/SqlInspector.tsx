import React, { useEffect, useState } from "react";
import Editor from "@monaco-editor/react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Gauge,
  Play,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { apiClient } from "../../api/client";
import type {
  CostEstimate,
  QueryPilotRun,
  ValidationResult,
} from "../../types/querypilot";

interface SqlInspectorProps {
  currentRun: QueryPilotRun | null;
  onRunUpdated: (updated: QueryPilotRun) => void;
  onOpenApprovals?: () => void;
}

export const SqlInspector: React.FC<SqlInspectorProps> = ({
  currentRun,
  onRunUpdated,
  onOpenApprovals,
}) => {
  const [sqlText, setSqlText] = useState<string>(
    currentRun?.generated_sql || ""
  );
  const [validation, setValidation] = useState<ValidationResult | null>(
    currentRun?.validation_result || null
  );
  const [costEstimate, setCostEstimate] = useState<CostEstimate | null>(
    currentRun?.cost_estimate || null
  );
  const [busyAction, setBusyAction] = useState<
    "validate" | "cost" | "execute" | null
  >(null);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [sqlModified, setSqlModified] = useState<boolean>(false);

  useEffect(() => {
    if (currentRun) {
      setSqlText(currentRun.generated_sql || "");
      setValidation(currentRun.validation_result || null);
      setCostEstimate(currentRun.cost_estimate || null);
      setSqlModified(false);
      setErrorBanner(null);
    }
  }, [currentRun?.query_id, currentRun?.generated_sql]);

  if (!currentRun) {
    return null;
  }

  const handleEditorChange = (val: string | undefined) => {
    const next = val ?? "";
    setSqlText(next);
    if (
      currentRun?.generated_sql &&
      next.trim() !== currentRun.generated_sql.trim()
    ) {
      setSqlModified(true);
    } else {
      setSqlModified(false);
    }
  };

  const handleValidate = async () => {
    if (!sqlText.trim()) return;
    setBusyAction("validate");
    setErrorBanner(null);
    try {
      const res = await apiClient.validateSql(sqlText);
      setValidation(res);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Safety check failed");
    } finally {
      setBusyAction(null);
    }
  };

  const handleEstimateCost = async () => {
    if (!sqlText.trim()) return;
    setBusyAction("cost");
    setErrorBanner(null);
    try {
      const res = await apiClient.estimateSqlCost(
        sqlText,
        currentRun?.thread_id || ""
      );
      setValidation(res.validation);
      setCostEstimate(res.cost_estimate);
    } catch (err) {
      setErrorBanner(
        err instanceof Error ? err.message : "Impact check failed"
      );
    } finally {
      setBusyAction(null);
    }
  };

  const handleExecute = async () => {
    if (!sqlText.trim()) return;
    setBusyAction("execute");
    setErrorBanner(null);
    try {
      const updated = await apiClient.executeSql({
        sql: sqlText,
        query_id: currentRun?.query_id,
        question: currentRun?.question || "Custom Query Execution",
        thread_id: currentRun?.thread_id,
      });
      setValidation(updated.validation_result || null);
      setCostEstimate(updated.cost_estimate || null);
      setSqlModified(false);
      onRunUpdated(updated);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Execution failed");
    } finally {
      setBusyAction(null);
    }
  };

  const riskBadgeColor =
    costEstimate?.risk_level === "high"
      ? "bg-rose-500/15 text-rose-300 border-rose-500/40"
      : costEstimate?.risk_level === "medium"
        ? "bg-amber-500/15 text-amber-300 border-amber-500/40"
        : "bg-emerald-500/15 text-emerald-300 border-emerald-500/40";

  return (
    <div className="flex flex-col rounded-2xl border border-slate-800 bg-slate-900/80 overflow-hidden shadow-sm">
      {/* Header Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 bg-slate-900 px-5 py-3.5">
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
            SQL Query Editor
          </span>
          {validation && (
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                validation.is_valid
                  ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-300"
                  : "border-rose-500/40 bg-rose-500/15 text-rose-300"
              }`}
            >
              {validation.is_valid ? (
                <>
                  <ShieldCheck className="h-3.5 w-3.5" /> Safe & Verified
                </>
              ) : (
                <>
                  <ShieldAlert className="h-3.5 w-3.5" />{" "}
                  {validation.is_safe ? "Needs Correction" : "Blocked for Safety"}
                </>
              )}
            </span>
          )}
          {costEstimate && (
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize ${riskBadgeColor}`}
            >
              <Gauge className="h-3.5 w-3.5" />
              Impact: {costEstimate.risk_level}
            </span>
          )}
          {sqlModified && (
            <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/40 bg-amber-500/15 px-2.5 py-0.5 text-xs text-amber-300">
              <AlertTriangle className="h-3.5 w-3.5" /> Unsaved Edits
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleValidate}
            disabled={busyAction !== null}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700 disabled:opacity-50 transition"
          >
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
            {busyAction === "validate" ? "Checking..." : "Check Safety"}
          </button>
          <button
            type="button"
            onClick={handleEstimateCost}
            disabled={busyAction !== null}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700 disabled:opacity-50 transition"
          >
            <Gauge className="h-3.5 w-3.5 text-indigo-400" />
            {busyAction === "cost" ? "Checking..." : "Estimate Impact"}
          </button>
          <button
            type="button"
            onClick={handleExecute}
            disabled={busyAction !== null}
            className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-1.5 text-xs font-semibold text-white shadow hover:bg-emerald-500 disabled:opacity-50 transition"
          >
            <Play className="h-3.5 w-3.5" />
            {busyAction === "execute" ? "Running..." : "Run Query"}
          </button>
        </div>
      </div>

      {/* Monaco SQL Editor */}
      <div className="h-52 w-full border-b border-slate-800">
        <Editor
          height="100%"
          defaultLanguage="sql"
          theme="vs-dark"
          value={sqlText}
          onChange={handleEditorChange}
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            fontFamily: "JetBrains Mono, Fira Code, Consolas, monospace",
            lineNumbers: "on",
            scrollBeyondLastLine: false,
            wordWrap: "on",
            padding: { top: 12, bottom: 12 },
          }}
        />
      </div>

      {/* Diagnostics & Metadata Footer */}
      <div className="space-y-2.5 bg-slate-950/60 px-5 py-3.5 text-xs">
        {errorBanner && (
          <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-3.5 py-2.5 text-rose-300">
            {errorBanner}
          </div>
        )}

        {costEstimate?.requires_approval && onOpenApprovals && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-500/40 bg-amber-950/30 px-4 py-2.5 text-amber-200">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
              <span>
                This query scans a large volume of data and requires approval
                before running.
              </span>
            </div>
            <button
              type="button"
              onClick={onOpenApprovals}
              className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500 px-3 py-1 font-semibold text-slate-950 hover:bg-amber-400 transition"
            >
              <span>Go to Pending Approvals</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {validation && validation.errors.length > 0 && (
          <div className="rounded-xl border border-rose-500/40 bg-rose-950/40 p-3.5 text-rose-200">
            <div className="mb-1 flex items-center gap-1.5 font-semibold text-rose-300">
              <ShieldAlert className="h-4 w-4" /> Safety & Query Check Issues:
            </div>
            <ul className="list-disc space-y-1 pl-5">
              {validation.errors.map((err, i) => (
                <li key={i}>{err}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-2 text-slate-400">
          <div className="flex flex-wrap items-center gap-4">
            {validation?.referenced_tables &&
              validation.referenced_tables.length > 0 && (
                <span>
                  <strong className="text-slate-300">Data Tables Used:</strong>{" "}
                  {validation.referenced_tables.join(", ")}
                </span>
              )}
            {costEstimate && (
              <span>
                <strong className="text-slate-300">Estimated Rows Scanned:</strong>{" "}
                {costEstimate.estimated_rows.toLocaleString()}
              </span>
            )}
          </div>
          {currentRun?.sql_rationale && (
            <div className="flex items-center gap-1.5 text-slate-400">
              <Sparkles className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
              <span>{currentRun.sql_rationale}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
