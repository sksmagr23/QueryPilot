import React, { useMemo, useState } from "react";
import {
  Background,
  Controls,
  Edge,
  MarkerType,
  Node,
  ReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { CheckCircle2, Clock, GitBranch } from "lucide-react";
import type { QueryPilotRun, TraceStep } from "../../types/querypilot";

interface ExecutionTraceProps {
  currentRun: QueryPilotRun | null;
}

const CANONICAL_NODES = [
  { id: "request_analyzer", label: "1. Understand Question", x: 50, y: 40 },
  { id: "schema_discovery", label: "2. Check Available Data", x: 300, y: 40 },
  { id: "query_planner", label: "3. Plan Calculation", x: 550, y: 40 },
  { id: "sql_generator", label: "4. Write SQL Query", x: 800, y: 40 },
  { id: "sql_validator", label: "5. Safety Check", x: 800, y: 170 },
  { id: "cost_estimator", label: "6. Impact Check", x: 550, y: 170 },
  { id: "approval_gate", label: "7. Approval Check", x: 300, y: 170 },
  { id: "query_executor", label: "8. Run Query", x: 300, y: 300 },
  { id: "result_validator", label: "9. Verify Results", x: 550, y: 300 },
  { id: "analysis_agent", label: "10. Calculate Numbers", x: 800, y: 300 },
  { id: "visualization_builder", label: "11. Build Chart", x: 550, y: 420 },
  { id: "response_generator", label: "12. Write Summary", x: 200, y: 420 },
];

const CANONICAL_EDGES = [
  { source: "request_analyzer", target: "schema_discovery", label: "clear" },
  { source: "request_analyzer", target: "response_generator", label: "needs clarification" },
  { source: "schema_discovery", target: "query_planner", label: "" },
  { source: "query_planner", target: "sql_generator", label: "" },
  { source: "sql_generator", target: "sql_validator", label: "" },
  { source: "sql_validator", target: "cost_estimator", label: "safe" },
  { source: "sql_validator", target: "sql_generator", label: "auto-fix" },
  { source: "sql_validator", target: "response_generator", label: "blocked" },
  { source: "cost_estimator", target: "approval_gate", label: "large query" },
  { source: "cost_estimator", target: "query_executor", label: "fast query" },
  { source: "approval_gate", target: "query_executor", label: "approved" },
  { source: "approval_gate", target: "response_generator", label: "declined" },
  { source: "query_executor", target: "result_validator", label: "completed" },
  { source: "query_executor", target: "sql_generator", label: "auto-fix" },
  { source: "result_validator", target: "analysis_agent", label: "verified" },
  { source: "result_validator", target: "sql_generator", label: "auto-fix" },
  { source: "analysis_agent", target: "visualization_builder", label: "" },
  { source: "visualization_builder", target: "response_generator", label: "" },
];

export const ExecutionTrace: React.FC<ExecutionTraceProps> = ({
  currentRun,
}) => {
  const trace = currentRun?.trace || [];
  const [selectedStep, setSelectedStep] = useState<TraceStep | null>(
    trace[trace.length - 1] || null
  );

  const stepByNodeId = useMemo(() => {
    const map: Record<string, { latest: TraceStep; count: number }> = {};
    for (const step of trace) {
      map[step.node_id] = {
        latest: step,
        count: (map[step.node_id]?.count || 0) + 1,
      };
    }
    return map;
  }, [trace]);

  const traversedSet = useMemo(() => {
    const s = new Set<string>();
    for (const e of currentRun?.edges_traversed || []) {
      s.add(`${e.source}->${e.target}`);
    }
    return s;
  }, [currentRun?.edges_traversed]);

  const rfNodes: Node[] = useMemo(() => {
    return CANONICAL_NODES.map((n) => {
      const info = stepByNodeId[n.id];
      const st = info?.latest.status || "idle";
      let border = "#334155";
      let bg = "#0f172a";
      let textColor = "#94a3b8";
      let statusLabel = "Skipped";

      if (st === "completed") {
        border = "#10b981";
        bg = "#064e3b";
        textColor = "#ecfdf5";
        statusLabel = "Done";
      } else if (st === "retry") {
        border = "#f59e0b";
        bg = "#451a03";
        textColor = "#fef3c7";
        statusLabel = "Auto-Fixed";
      } else if (st === "awaiting_approval") {
        border = "#f59e0b";
        bg = "#78350f";
        textColor = "#fef3c7";
        statusLabel = "Needs Review";
      } else if (st === "blocked" || st === "rejected") {
        border = "#f43f5e";
        bg = "#4c0519";
        textColor = "#ffe4e6";
        statusLabel = "Stopped";
      }

      return {
        id: n.id,
        position: { x: n.x, y: n.y },
        data: {
          label: (
            <div className="text-left">
              <div className="font-semibold text-[11px]">{n.label}</div>
              <div className="mt-1 flex items-center justify-between text-[10px] opacity-85">
                <span>{statusLabel}</span>
                {info && <span>{info.latest.latency_ms}ms</span>}
              </div>
            </div>
          ),
        },
        style: {
          background: bg,
          color: textColor,
          border: `1.5px solid ${border}`,
          borderRadius: "10px",
          padding: "8px 10px",
          width: 205,
          cursor: "pointer",
        },
      };
    });
  }, [stepByNodeId]);

  const rfEdges: Edge[] = useMemo(() => {
    return CANONICAL_EDGES.map((e, idx) => {
      const key = `${e.source}->${e.target}`;
      const active = traversedSet.has(key);
      return {
        id: `e_${idx}_${key}`,
        source: e.source,
        target: e.target,
        label: e.label,
        animated: active,
        style: {
          stroke: active ? "#10b981" : "#334155",
          strokeWidth: active ? 2.4 : 1.2,
        },
        labelStyle: {
          fill: active ? "#34d399" : "#64748b",
          fontSize: 10,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: active ? "#10b981" : "#334155",
        },
      };
    });
  }, [traversedSet]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-800 bg-slate-900/90 px-5 py-4">
        <div className="flex items-center gap-2.5">
          <GitBranch className="h-5 w-5 text-emerald-400" />
          <div>
            <h2 className="text-sm font-bold text-slate-100">
              How Your Answer Was Built (Step-by-Step Workflow)
            </h2>
            <p className="text-xs text-slate-400">
              Green steps ran successfully. Click any step to see what happened
              at that stage.
            </p>
          </div>
        </div>

        {currentRun && (
          <div className="flex items-center gap-2 text-xs text-slate-300">
            <span className="inline-flex items-center gap-1.5 rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5">
              <Clock className="h-3.5 w-3.5 text-emerald-400" />
              Total Time: {(currentRun.total_latency_ms / 1000).toFixed(2)}s
            </span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 h-[520px] rounded-2xl border border-slate-800 bg-slate-950 overflow-hidden">
          <ReactFlow
            nodes={rfNodes}
            edges={rfEdges}
            fitView
            onNodeClick={(_, node) => {
              const found = stepByNodeId[node.id]?.latest;
              if (found) setSelectedStep(found);
            }}
          >
            <Background color="#1e293b" gap={18} />
            <Controls />
          </ReactFlow>
        </div>

        <div className="flex flex-col h-[520px] rounded-2xl border border-slate-800 bg-slate-900/90 overflow-hidden">
          <div className="border-b border-slate-800 px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
            Completed Steps ({trace.length})
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-slate-800/70">
            {trace.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">
                Ask a business question in the workspace to see the step-by-step
                workflow here.
              </div>
            ) : (
              trace.map((step, idx) => {
                const isSelected = selectedStep === step;
                return (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setSelectedStep(step)}
                    className={`w-full text-left px-4 py-3 text-xs transition ${
                      isSelected
                        ? "bg-emerald-500/15 border-l-2 border-emerald-400"
                        : "hover:bg-slate-800/50"
                    }`}
                  >
                    <div className="flex items-center justify-between font-medium text-slate-200">
                      <span>
                        Step {idx + 1}: {step.label}
                      </span>
                      <span className="text-[11px] text-emerald-400">
                        {step.latency_ms}ms
                      </span>
                    </div>
                    <div className="mt-1 text-[11px] text-slate-400 leading-relaxed">
                      {step.summary}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
