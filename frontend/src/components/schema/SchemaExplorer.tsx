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
import {
  BookOpen,
  Database,
  Key,
  Link2,
  Search,
  Table2,
} from "lucide-react";
import type { SchemaDiscoveryResponse } from "../../types/querypilot";

interface SchemaExplorerProps {
  schema: SchemaDiscoveryResponse | null;
}

const TABLE_POSITIONS: Record<string, { x: number; y: number }> = {
  categories: { x: 40, y: 40 },
  products: { x: 330, y: 40 },
  order_items: { x: 640, y: 40 },
  orders: { x: 640, y: 260 },
  customers: { x: 330, y: 260 },
  payments: { x: 930, y: 260 },
  website_events: { x: 40, y: 260 },
};

export const SchemaExplorer: React.FC<SchemaExplorerProps> = ({ schema }) => {
  const [search, setSearch] = useState("");
  const [selectedTable, setSelectedTable] = useState<string>("orders");
  const [activeSubTab, setActiveSubTab] = useState<
    "tables" | "er_graph" | "semantic"
  >("tables");

  const tables = schema?.tables || [];
  const filteredTables = useMemo(() => {
    if (!search.trim()) return tables;
    const q = search.trim().toLowerCase();
    return tables.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        t.columns.some((c) => c.name.toLowerCase().includes(q))
    );
  }, [tables, search]);

  const currentTableObj =
    tables.find((t) => t.name === selectedTable) || tables[0] || null;

  const erNodes: Node[] = useMemo(() => {
    return tables.map((t) => {
      const pos = TABLE_POSITIONS[t.name] || { x: 100, y: 100 };
      return {
        id: t.name,
        position: pos,
        data: {
          label: (
            <div className="text-left">
              <div className="flex items-center justify-between border-b border-slate-700 pb-1 mb-1">
                <span className="font-bold text-xs text-emerald-400">
                  {t.name}
                </span>
                <span className="text-[10px] text-slate-400">
                  {t.row_count.toLocaleString()} records
                </span>
              </div>
              <div className="space-y-0.5 text-[10px] text-slate-300">
                {t.columns.slice(0, 6).map((c) => (
                  <div key={c.name} className="flex justify-between gap-2">
                    <span>
                      {c.is_primary_key ? "🔑 " : c.foreign_key ? "🔗 " : ""}
                      {c.name}
                    </span>
                    <span className="text-slate-500">{c.type}</span>
                  </div>
                ))}
                {t.columns.length > 6 && (
                  <div className="text-slate-500">
                    +{t.columns.length - 6} more fields
                  </div>
                )}
              </div>
            </div>
          ),
        },
        style: {
          background: "#0f172a",
          color: "#f8fafc",
          border:
            t.name === selectedTable
              ? "2px solid #10b981"
              : "1px solid #334155",
          borderRadius: "10px",
          padding: "8px 10px",
          width: 230,
        },
      };
    });
  }, [tables, selectedTable]);

  const erEdges: Edge[] = useMemo(() => {
    return (schema?.relationships || []).map((rel, i) => ({
      id: `fk_${i}`,
      source: rel.source_table,
      target: rel.target_table,
      label: `${rel.source_column} → ${rel.target_column}`,
      animated: true,
      style: { stroke: "#6366f1", strokeWidth: 1.8 },
      labelStyle: { fill: "#a5b4fc", fontSize: 10 },
      markerEnd: { type: MarkerType.ArrowClosed, color: "#6366f1" },
    }));
  }, [schema?.relationships]);

  if (!schema) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-10 text-center text-sm text-slate-400">
        Loading store data catalog...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-800 bg-slate-900/90 px-5 py-4">
        <div className="flex items-center gap-2.5">
          <Database className="h-5 w-5 text-emerald-400" />
          <div>
            <h2 className="text-sm font-bold text-slate-100">
              Available Store Data & Business Metrics ({schema.tables.length}{" "}
              Data Tables)
            </h2>
            <p className="text-xs text-slate-400">
              Explore what information is stored in the database and the
              official formulas used to calculate metrics.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1 rounded-xl border border-slate-800 bg-slate-950 p-1">
          <button
            type="button"
            onClick={() => setActiveSubTab("tables")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              activeSubTab === "tables"
                ? "bg-emerald-600 text-white"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Table2 className="h-3.5 w-3.5" /> Data Tables
          </button>
          <button
            type="button"
            onClick={() => setActiveSubTab("er_graph")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              activeSubTab === "er_graph"
                ? "bg-emerald-600 text-white"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Link2 className="h-3.5 w-3.5" /> Table Connections
          </button>
          <button
            type="button"
            onClick={() => setActiveSubTab("semantic")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              activeSubTab === "semantic"
                ? "bg-emerald-600 text-white"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <BookOpen className="h-3.5 w-3.5" /> Business Formulas
          </button>
        </div>
      </div>

      {activeSubTab === "tables" && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {/* Left: Table List */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-3.5 space-y-3">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-500" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search tables or fields..."
                className="w-full rounded-xl border border-slate-700 bg-slate-950 pl-8 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
              />
            </div>
            <div className="space-y-1.5">
              {filteredTables.map((t) => (
                <button
                  key={t.name}
                  type="button"
                  onClick={() => setSelectedTable(t.name)}
                  className={`w-full rounded-xl border p-3 text-left transition ${
                    currentTableObj?.name === t.name
                      ? "border-emerald-500/50 bg-emerald-500/10"
                      : "border-slate-800 bg-slate-950/50 hover:bg-slate-800/50"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-emerald-400">
                      {t.name}
                    </span>
                    <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-[10px] text-slate-300">
                      {t.row_count.toLocaleString()} records
                    </span>
                  </div>
                  <p className="mt-1 text-[11px] text-slate-400 line-clamp-2">
                    {t.description}
                  </p>
                </button>
              ))}
            </div>
          </div>

          {currentTableObj && (
            <div className="lg:col-span-2 rounded-2xl border border-slate-800 bg-slate-900/90 overflow-hidden">
              <div className="border-b border-slate-800 bg-slate-900 px-5 py-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-emerald-400">
                    {currentTableObj.name}
                  </h3>
                  <span className="text-xs text-slate-400">
                    {currentTableObj.columns.length} fields •{" "}
                    {currentTableObj.row_count.toLocaleString()} records
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-300">
                  {currentTableObj.description}
                </p>
              </div>
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950 text-slate-400 border-b border-slate-800">
                  <tr>
                    <th className="px-5 py-3">Field Name</th>
                    <th className="px-5 py-3">Type</th>
                    <th className="px-5 py-3">Relationship</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/70">
                  {currentTableObj.columns.map((col) => (
                    <tr key={col.name} className="hover:bg-slate-800/30">
                      <td className="px-5 py-2.5 font-medium text-slate-100">
                        {col.name}
                      </td>
                      <td className="px-5 py-2.5 text-indigo-300">
                        {col.type}
                      </td>
                      <td className="px-5 py-2.5">
                        {col.is_primary_key && (
                          <span className="inline-flex items-center gap-1 rounded-md bg-amber-500/15 px-2 py-0.5 text-[11px] text-amber-300 mr-1.5">
                            <Key className="h-3 w-3" /> Unique ID
                          </span>
                        )}
                        {col.foreign_key && (
                          <span className="inline-flex items-center gap-1 rounded-md bg-indigo-500/15 px-2 py-0.5 text-[11px] text-indigo-300">
                            <Link2 className="h-3 w-3" /> Links to{" "}
                            {col.foreign_key}
                          </span>
                        )}
                        {!col.is_primary_key && !col.foreign_key && (
                          <span className="text-slate-500">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeSubTab === "er_graph" && (
        <div className="h-[520px] rounded-2xl border border-slate-800 bg-slate-950 overflow-hidden">
          <ReactFlow
            nodes={erNodes}
            edges={erEdges}
            fitView
            onNodeClick={(_, n) => setSelectedTable(n.id)}
          >
            <Background color="#1e293b" gap={18} />
            <Controls />
          </ReactFlow>
        </div>
      )}

      {activeSubTab === "semantic" && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 space-y-3">
            <h3 className="text-sm font-semibold text-emerald-400">
              Official Business Metrics ({schema.semantic_metrics.length})
            </h3>
            <div className="space-y-2.5">
              {schema.semantic_metrics.map((m) => (
                <div
                  key={m.id}
                  className="rounded-xl border border-slate-800 bg-slate-950/60 p-3.5 space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-xs text-slate-100">
                      {m.name}
                    </span>
                    <span className="rounded-md bg-slate-800 px-2 py-0.5 text-[10px] text-emerald-300">
                      {m.unit}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">{m.description}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 space-y-3">
            <h3 className="text-sm font-semibold text-indigo-400">
              How Tables Connect ({schema.valid_joins.length})
            </h3>
            <div className="space-y-2.5">
              {schema.valid_joins.map((j, idx) => (
                <div
                  key={idx}
                  className="rounded-xl border border-slate-800 bg-slate-950/60 p-3.5 space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-emerald-300">
                      {j.left_table} ⟷ {j.right_table}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">{j.description}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
