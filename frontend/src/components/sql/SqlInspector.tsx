import React, { useEffect, useState } from "react";
import Editor from "@monaco-editor/react";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Clock,
  Code2,
  Copy,
  Database,
  Gauge,
  Play,
  ShieldAlert,
  ShieldCheck,
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
  onOpenApprovalsDropdown?: () => void;
}

export const SqlInspector: React.FC<SqlInspectorProps> = ({
  currentRun,
  onRunUpdated,
  onOpenApprovalsDropdown,
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
  const [copied, setCopied] = useState<boolean>(false);

  useEffect(() => {
    if (currentRun) {
      setSqlText(currentRun.generated_sql || "");
      setValidation(currentRun.validation_result || null);
      setCostEstimate(currentRun.cost_estimate || null);
      setErrorBanner(null);
    }
  }, [currentRun?.query_id, currentRun?.generated_sql]);

  if (!currentRun || !currentRun.generated_sql) {
    return null;
  }

  const handleCopySql = async () => {
    try {
      await navigator.clipboard.writeText(sqlText);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // ignore clipboard errors
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
        err instanceof Error ? err.message : "Database cost check failed"
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
        question: currentRun?.question || "Custom SQL Query",
        thread_id: currentRun?.thread_id,
      });
      setValidation(updated.validation_result || null);
      setCostEstimate(updated.cost_estimate || null);
      onRunUpdated(updated);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Execution failed");
    } finally {
      setBusyAction(null);
    }
  };

  const execTimeMs = currentRun.execution_result?.execution_time_ms;

  return (
    <div className="flex flex-col rounded-2xl border border-[#163661] bg-[#091D38]/90 overflow-hidden shadow-lg">
      {/* Header Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#163661] bg-[#0A2140] px-6 py-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Code2 className="h-4 w-4 text-[#00C8FF]" />
            <span className="text-xs font-bold uppercase tracking-wider text-[#EAF3FF]">
              SQL Query & Database Cost
            </span>
          </div>

          {validation && (
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-0.5 text-xs font-semibold ${
                validation.is_valid
                  ? "border-[#00C8FF]/40 bg-[#00C8FF]/10 text-[#00C8FF]"
                  : "border-rose-500/40 bg-rose-500/15 text-rose-300"
              }`}
            >
              {validation.is_valid ? (
                <>
                  <ShieldCheck className="h-3.5 w-3.5" /> Verified Safe
                </>
              ) : (
                <>
                  <ShieldAlert className="h-3.5 w-3.5" />{" "}
                  {validation.is_safe ? "Query Issue" : "Blocked for Safety"}
                </>
              )}
            </span>
          )}

          {costEstimate && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-[#1B3F70] bg-[#06152B] px-3 py-0.5 text-xs font-semibold text-[#EAF3FF]">
              <Gauge className="h-3.5 w-3.5 text-[#00C8FF]" />
              DB Cost: {costEstimate.estimated_cost} (
              <span className="capitalize text-[#00C8FF]">
                {costEstimate.risk_level}
              </span>
              )
            </span>
          )}

          {execTimeMs !== undefined && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-[#1B3F70] bg-[#06152B] px-3 py-0.5 text-xs font-semibold text-[#EAF3FF]">
              <Clock className="h-3.5 w-3.5 text-[#00C8FF]" />
              DB Time: {execTimeMs} ms
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handleCopySql}
            className="inline-flex items-center gap-1.5 rounded-xl border border-[#1B3F70] bg-[#06152B] px-3 py-1.5 text-xs font-semibold text-[#91A9C5] hover:border-[#168BFF] hover:text-[#EAF3FF] transition"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 text-[#00C8FF]" /> Copied
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" /> Copy SQL
              </>
            )}
          </button>
          <button
            type="button"
            onClick={handleValidate}
            disabled={busyAction !== null}
            className="inline-flex items-center gap-1.5 rounded-xl border border-[#1B3F70] bg-[#0D2548] px-3 py-1.5 text-xs font-semibold text-[#EAF3FF] hover:border-[#168BFF] disabled:opacity-50 transition"
          >
            <CheckCircle2 className="h-3.5 w-3.5 text-[#00C8FF]" />
            {busyAction === "validate" ? "Checking..." : "Check Safety"}
          </button>
          <button
            type="button"
            onClick={handleEstimateCost}
            disabled={busyAction !== null}
            className="inline-flex items-center gap-1.5 rounded-xl border border-[#1B3F70] bg-[#0D2548] px-3 py-1.5 text-xs font-semibold text-[#EAF3FF] hover:border-[#168BFF] disabled:opacity-50 transition"
          >
            <Gauge className="h-3.5 w-3.5 text-[#00C8FF]" />
            {busyAction === "cost" ? "Checking..." : "Check Cost"}
          </button>
          <button
            type="button"
            onClick={handleExecute}
            disabled={busyAction !== null}
            className="inline-flex items-center gap-1.5 rounded-xl bg-[#168BFF] px-4 py-1.5 text-xs font-bold text-white shadow-sm shadow-[#168BFF]/30 hover:bg-[#168BFF]/90 disabled:opacity-50 transition"
          >
            <Play className="h-3.5 w-3.5" />
            {busyAction === "execute" ? "Running..." : "Run SQL"}
          </button>
        </div>
      </div>

      {/* SQL Code Editor */}
      <div className="h-48 w-full border-b border-[#163661]">
        <Editor
          height="100%"
          defaultLanguage="sql"
          theme="vs-dark"
          value={sqlText}
          onChange={(val) => setSqlText(val ?? "")}
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

      {/* Database Cost & Table Metadata Footer */}
      <div className="space-y-2.5 bg-[#06152B]/80 px-6 py-3.5 text-xs">
        {errorBanner && (
          <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-3.5 py-2.5 text-rose-300">
            {errorBanner}
          </div>
        )}

        {costEstimate?.requires_approval && onOpenApprovalsDropdown && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#00C8FF]/40 bg-[#0A2246] px-4 py-2.5 text-[#EAF3FF]">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-[#00C8FF] shrink-0" />
              <span>
                <strong>Approval Needed:</strong>{" "}
                {costEstimate.approval_reason ||
                  "This query has a high estimated database cost and requires approval."}
              </span>
            </div>
            <button
              type="button"
              onClick={onOpenApprovalsDropdown}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[#00C8FF] px-3 py-1 font-bold text-[#06152B] hover:bg-[#00C8FF]/90 transition"
            >
              Review & Approve
            </button>
          </div>
        )}

        {validation && validation.errors.length > 0 && (
          <div className="rounded-xl border border-rose-500/40 bg-rose-950/40 p-3.5 text-rose-200">
            <div className="mb-1 flex items-center gap-1.5 font-semibold text-rose-300">
              <ShieldAlert className="h-4 w-4" /> Query Check Issues:
            </div>
            <ul className="list-disc space-y-1 pl-5">
              {validation.errors.map((err, i) => (
                <li key={i}>{err}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3 text-[#91A9C5]">
          <div className="flex flex-wrap items-center gap-5">
            {validation?.referenced_tables &&
              validation.referenced_tables.length > 0 && (
                <span className="inline-flex items-center gap-1.5">
                  <Database className="h-3.5 w-3.5 text-[#00C8FF]" />
                  <strong className="text-[#EAF3FF]">Tables:</strong>{" "}
                  {validation.referenced_tables.join(", ")}
                </span>
              )}
            {costEstimate && (
              <span>
                <strong className="text-[#EAF3FF]">Estimated Cost:</strong>{" "}
                {costEstimate.estimated_cost} •{" "}
                <strong className="text-[#EAF3FF]">Est. Rows Scanned:</strong>{" "}
                {costEstimate.estimated_rows.toLocaleString()}
              </span>
            )}
            {execTimeMs !== undefined && (
              <span>
                <strong className="text-[#EAF3FF]">Database Execution:</strong>{" "}
                {execTimeMs} ms
              </span>
            )}
          </div>
          {currentRun.sql_rationale && (
            <span className="text-[#91A9C5]">{currentRun.sql_rationale}</span>
          )}
        </div>
      </div>
    </div>
  );
};
