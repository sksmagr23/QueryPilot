import React, { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  BarChart3,
  Clock,
  Download,
  LineChart as LineChartIcon,
  PieChart as PieChartIcon,
  Search,
  Table as TableIcon,
} from "lucide-react";
import { apiClient } from "../../api/client";
import type { QueryPilotRun } from "../../types/querypilot";

interface ResultsExplorerProps {
  currentRun: QueryPilotRun | null;
}

const PIE_COLORS = [
  "#10b981",
  "#6366f1",
  "#f59e0b",
  "#06b6d4",
  "#ec4899",
  "#8b5cf6",
  "#14b8a6",
  "#f97316",
];

export const ResultsExplorer: React.FC<ResultsExplorerProps> = ({
  currentRun,
}) => {
  const execResult = currentRun?.execution_result;
  const viz = currentRun?.visualization;
  const analysis = currentRun?.analysis;

  const [chartTypeOverride, setChartTypeOverride] = useState<
    "bar" | "line" | "area" | "pie" | "composed" | null
  >(null);
  const [tableFilter, setTableFilter] = useState<string>("");
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDesc, setSortDesc] = useState<boolean>(true);

  const activeChartType =
    chartTypeOverride ||
    (viz?.chart_type && viz.chart_type !== "table_only"
      ? viz.chart_type
      : "bar");

  const rows = execResult?.rows || [];
  const columns = execResult?.columns || [];

  const filteredAndSortedRows = useMemo(() => {
    let list = [...rows];
    if (tableFilter.trim()) {
      const q = tableFilter.trim().toLowerCase();
      list = list.filter((r) =>
        Object.values(r).some((v) =>
          String(v ?? "")
            .toLowerCase()
            .includes(q)
        )
      );
    }
    if (sortCol) {
      list.sort((a, b) => {
        const va = a[sortCol];
        const vb = b[sortCol];
        if (typeof va === "number" && typeof vb === "number") {
          return sortDesc ? vb - va : va - vb;
        }
        return sortDesc
          ? String(vb ?? "").localeCompare(String(va ?? ""))
          : String(va ?? "").localeCompare(String(vb ?? ""));
      });
    }
    return list;
  }, [rows, tableFilter, sortCol, sortDesc]);

  if (!currentRun || !execResult) {
    return null;
  }

  const xKey = viz?.x_key || columns[0] || "";
  const yKeys =
    viz?.y_keys && viz.y_keys.length > 0
      ? viz.y_keys
      : columns.length > 1
        ? [columns[columns.length - 1]]
        : [];
  const chartData = viz?.data && viz.data.length > 0 ? viz.data : rows.slice(0, 25);

  const handleSort = (col: string) => {
    if (sortCol === col) {
      setSortDesc(!sortDesc);
    } else {
      setSortCol(col);
      setSortDesc(true);
    }
  };

  return (
    <div className="space-y-4">
      {/* KPI Summary Cards */}
      {analysis?.kpis && analysis.kpis.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {analysis.kpis.map((kpi, idx) => (
            <div
              key={idx}
              className="rounded-xl border border-slate-800 bg-slate-900/90 p-4 shadow-sm"
            >
              <div className="text-xs font-medium uppercase tracking-wider text-slate-400">
                {kpi.label}
              </div>
              <div className="mt-1.5 text-xl font-bold text-slate-100 font-mono">
                {kpi.value}
              </div>
              <div className="mt-1 text-xs text-slate-400">{kpi.subtext}</div>
            </div>
          ))}
        </div>
      )}

      {/* Visualization Card */}
      {rows.length > 0 && yKeys.length > 0 && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-semibold text-slate-100">
                {viz?.title || "Query Results Visualization"}
              </h3>
              <p className="text-xs text-slate-400">{viz?.subtitle}</p>
            </div>
            <div className="flex items-center gap-1 rounded-lg border border-slate-800 bg-slate-950 p-1">
              {(
                [
                  { id: "bar", label: "Bar", icon: BarChart3 },
                  { id: "line", label: "Line", icon: LineChartIcon },
                  { id: "area", label: "Area", icon: LineChartIcon },
                  { id: "composed", label: "Dual", icon: BarChart3 },
                  { id: "pie", label: "Pie", icon: PieChartIcon },
                ] as const
              ).map((item) => {
                const Icon = item.icon;
                const active = activeChartType === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setChartTypeOverride(item.id)}
                    className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition ${
                      active
                        ? "bg-emerald-600 text-white"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {item.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              {activeChartType === "line" ? (
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey={xKey} stroke="#94a3b8" fontSize={11} />
                  <YAxis stroke="#94a3b8" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0f172a",
                      borderColor: "#334155",
                      fontSize: "12px",
                    }}
                  />
                  <Legend />
                  {yKeys.map((yk, i) => (
                    <Line
                      key={yk}
                      type="monotone"
                      dataKey={yk}
                      stroke={PIE_COLORS[i % PIE_COLORS.length]}
                      strokeWidth={2.5}
                      dot={{ r: 4 }}
                    />
                  ))}
                </LineChart>
              ) : activeChartType === "area" ? (
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey={xKey} stroke="#94a3b8" fontSize={11} />
                  <YAxis stroke="#94a3b8" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0f172a",
                      borderColor: "#334155",
                      fontSize: "12px",
                    }}
                  />
                  <Legend />
                  {yKeys.map((yk, i) => (
                    <Area
                      key={yk}
                      type="monotone"
                      dataKey={yk}
                      stroke={PIE_COLORS[i % PIE_COLORS.length]}
                      fill={PIE_COLORS[i % PIE_COLORS.length]}
                      fillOpacity={0.22}
                    />
                  ))}
                </AreaChart>
              ) : activeChartType === "pie" ? (
                <PieChart>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0f172a",
                      borderColor: "#334155",
                      fontSize: "12px",
                    }}
                  />
                  <Legend />
                  <Pie
                    data={chartData}
                    dataKey={yKeys[0]}
                    nameKey={xKey}
                    cx="50%"
                    cy="50%"
                    outerRadius={95}
                    label
                  >
                    {chartData.map((_, idx) => (
                      <Cell
                        key={idx}
                        fill={PIE_COLORS[idx % PIE_COLORS.length]}
                      />
                    ))}
                  </Pie>
                </PieChart>
              ) : activeChartType === "composed" ? (
                <ComposedChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey={xKey} stroke="#94a3b8" fontSize={11} />
                  <YAxis stroke="#94a3b8" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0f172a",
                      borderColor: "#334155",
                      fontSize: "12px",
                    }}
                  />
                  <Legend />
                  <Bar
                    dataKey={yKeys[0]}
                    fill="#10b981"
                    radius={[4, 4, 0, 0]}
                  />
                  {yKeys[1] && (
                    <Line
                      type="monotone"
                      dataKey={yKeys[1]}
                      stroke="#6366f1"
                      strokeWidth={2.5}
                    />
                  )}
                </ComposedChart>
              ) : (
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey={xKey} stroke="#94a3b8" fontSize={11} />
                  <YAxis stroke="#94a3b8" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0f172a",
                      borderColor: "#334155",
                      fontSize: "12px",
                    }}
                  />
                  <Legend />
                  {yKeys.map((yk, i) => (
                    <Bar
                      key={yk}
                      dataKey={yk}
                      fill={PIE_COLORS[i % PIE_COLORS.length]}
                      radius={[4, 4, 0, 0]}
                    />
                  ))}
                </BarChart>
              )}
            </ResponsiveContainer>
          </div>
        </div>
      )}

      <div className="rounded-xl border border-slate-800 bg-slate-900/80 overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 bg-slate-900 px-4 py-3">
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-300">
              <TableIcon className="h-3.5 w-3.5 text-emerald-400" />
              Results Table ({filteredAndSortedRows.length} rows)
            </span>
            <span className="inline-flex items-center gap-1 rounded-full bg-slate-800 px-2.5 py-0.5 text-xs font-mono text-slate-300">
              <Clock className="h-3 w-3 text-emerald-400" />
              {execResult.execution_time_ms}ms
            </span>
            {execResult.truncated && (
              <span className="rounded-full border border-amber-500/40 bg-amber-500/15 px-2.5 py-0.5 text-xs text-amber-300">
                Row limit capped ({execResult.max_rows_enforced} max)
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-500" />
              <input
                type="text"
                value={tableFilter}
                onChange={(e) => setTableFilter(e.target.value)}
                placeholder="Filter rows..."
                className="rounded-lg border border-slate-700 bg-slate-950 pl-8 pr-3 py-1 text-xs text-slate-200 placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
              />
            </div>
            <a
              href={apiClient.getExportCsvUrl(currentRun.query_id)}
              download={`querypilot_${currentRun.query_id}.csv`}
              className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/40 bg-emerald-500/15 px-3 py-1.5 text-xs font-medium text-emerald-300 hover:bg-emerald-500/25"
            >
              <Download className="h-3.5 w-3.5" />
              Export CSV
            </a>
          </div>
        </div>

        {columns.length === 0 || rows.length === 0 ? (
          <div className="p-6 text-center text-xs text-slate-400">
            Query executed cleanly and returned 0 matching rows.
          </div>
        ) : (
          <div className="max-h-80 overflow-auto">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-slate-950 text-slate-300 border-b border-slate-800">
                <tr>
                  {columns.map((col) => (
                    <th
                      key={col}
                      onClick={() => handleSort(col)}
                      className="cursor-pointer whitespace-nowrap px-4 py-2.5 font-semibold hover:text-emerald-400"
                    >
                      {col}
                      {sortCol === col ? (sortDesc ? " ↓" : " ↑") : ""}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {filteredAndSortedRows.map((row, rIdx) => (
                  <tr
                    key={rIdx}
                    className="hover:bg-slate-800/40 transition-colors"
                  >
                    {columns.map((col) => {
                      const val = row[col];
                      const isNum = typeof val === "number";
                      return (
                        <td
                          key={col}
                          className={`whitespace-nowrap px-4 py-2 ${
                            isNum
                              ? "font-mono text-emerald-300"
                              : "text-slate-200"
                          }`}
                        >
                          {val === null || val === undefined
                            ? "NULL"
                            : isNum
                              ? val.toLocaleString(undefined, {
                                  maximumFractionDigits: 2,
                                })
                              : String(val)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
