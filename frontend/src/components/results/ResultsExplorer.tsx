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

const CHART_PALETTE = [
  "#168BFF",
  "#00C8FF",
  "#38BDF8",
  "#60A5FA",
  "#818CF8",
  "#2DD4BF",
  "#F59E0B",
  "#F43F5E",
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
  const chartData =
    viz?.data && viz.data.length > 0 ? viz.data : rows.slice(0, 25);

  const handleSort = (col: string) => {
    if (sortCol === col) {
      setSortDesc(!sortDesc);
    } else {
      setSortCol(col);
      setSortDesc(true);
    }
  };

  return (
    <div className="space-y-6">
      {/* Horizontal Statistics Strip */}
      {analysis?.kpis && analysis.kpis.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {analysis.kpis.map((kpi, idx) => (
            <div
              key={idx}
              className="relative overflow-hidden rounded-2xl border border-[#163661] bg-gradient-to-b from-[#0A1F3D] to-[#071830] p-5 shadow-md"
            >
              <div className="text-[11px] font-bold uppercase tracking-wider text-[#91A9C5]">
                {kpi.label}
              </div>
              <div className="mt-2 text-2xl font-extrabold tracking-tight text-[#EAF3FF]">
                {kpi.value}
              </div>
              <div className="mt-1 text-xs text-[#00C8FF]">{kpi.subtext}</div>
            </div>
          ))}
        </div>
      )}

      {/* Interactive Chart Card */}
      {rows.length > 0 && yKeys.length > 0 && (
        <div className="rounded-2xl border border-[#163661] bg-[#091D38]/90 p-6 shadow-lg">
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-bold text-[#EAF3FF]">
                {viz?.title || "Visual Breakdown"}
              </h3>
              <p className="text-xs text-[#91A9C5]">{viz?.subtitle}</p>
            </div>
            <div className="flex items-center gap-1 rounded-xl border border-[#163661] bg-[#06152B] p-1">
              {(
                [
                  { id: "bar", label: "Bar", icon: BarChart3 },
                  { id: "line", label: "Line", icon: LineChartIcon },
                  { id: "area", label: "Area", icon: LineChartIcon },
                  { id: "composed", label: "Combo", icon: BarChart3 },
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
                    className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                      active
                        ? "bg-[#168BFF] text-white shadow-sm shadow-[#168BFF]/40"
                        : "text-[#91A9C5] hover:text-[#EAF3FF]"
                    }`}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {item.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              {activeChartType === "line" ? (
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#142F54" />
                  <XAxis dataKey={xKey} stroke="#91A9C5" fontSize={11} />
                  <YAxis stroke="#91A9C5" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#06152B",
                      borderColor: "#168BFF",
                      borderRadius: "12px",
                      color: "#EAF3FF",
                      fontSize: "12px",
                    }}
                  />
                  <Legend />
                  {yKeys.map((yk, i) => (
                    <Line
                      key={yk}
                      type="monotone"
                      dataKey={yk}
                      stroke={CHART_PALETTE[i % CHART_PALETTE.length]}
                      strokeWidth={2.5}
                      dot={{ r: 4 }}
                    />
                  ))}
                </LineChart>
              ) : activeChartType === "area" ? (
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#142F54" />
                  <XAxis dataKey={xKey} stroke="#91A9C5" fontSize={11} />
                  <YAxis stroke="#91A9C5" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#06152B",
                      borderColor: "#168BFF",
                      borderRadius: "12px",
                      color: "#EAF3FF",
                      fontSize: "12px",
                    }}
                  />
                  <Legend />
                  {yKeys.map((yk, i) => (
                    <Area
                      key={yk}
                      type="monotone"
                      dataKey={yk}
                      stroke={CHART_PALETTE[i % CHART_PALETTE.length]}
                      fill={CHART_PALETTE[i % CHART_PALETTE.length]}
                      fillOpacity={0.22}
                    />
                  ))}
                </AreaChart>
              ) : activeChartType === "pie" ? (
                <PieChart>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#06152B",
                      borderColor: "#168BFF",
                      borderRadius: "12px",
                      color: "#EAF3FF",
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
                    outerRadius={105}
                    label
                  >
                    {chartData.map((_, idx) => (
                      <Cell
                        key={idx}
                        fill={CHART_PALETTE[idx % CHART_PALETTE.length]}
                      />
                    ))}
                  </Pie>
                </PieChart>
              ) : activeChartType === "composed" ? (
                <ComposedChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#142F54" />
                  <XAxis dataKey={xKey} stroke="#91A9C5" fontSize={11} />
                  <YAxis stroke="#91A9C5" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#06152B",
                      borderColor: "#168BFF",
                      borderRadius: "12px",
                      color: "#EAF3FF",
                      fontSize: "12px",
                    }}
                  />
                  <Legend />
                  <Bar
                    dataKey={yKeys[0]}
                    fill="#168BFF"
                    radius={[6, 6, 0, 0]}
                  />
                  {yKeys[1] && (
                    <Line
                      type="monotone"
                      dataKey={yKeys[1]}
                      stroke="#00C8FF"
                      strokeWidth={2.5}
                    />
                  )}
                </ComposedChart>
              ) : (
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#142F54" />
                  <XAxis dataKey={xKey} stroke="#91A9C5" fontSize={11} />
                  <YAxis stroke="#91A9C5" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#06152B",
                      borderColor: "#168BFF",
                      borderRadius: "12px",
                      color: "#EAF3FF",
                      fontSize: "12px",
                    }}
                  />
                  <Legend />
                  {yKeys.map((yk, i) => (
                    <Bar
                      key={yk}
                      dataKey={yk}
                      fill={CHART_PALETTE[i % CHART_PALETTE.length]}
                      radius={[6, 6, 0, 0]}
                    />
                  ))}
                </BarChart>
              )}
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Data Breakdown Table + CSV Export */}
      <div className="rounded-2xl border border-[#163661] bg-[#091D38]/90 overflow-hidden shadow-lg">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#163661] bg-[#0A2140] px-6 py-4">
          <div className="flex items-center gap-2.5">
            <TableIcon className="h-4 w-4 text-[#00C8FF]" />
            <span className="text-xs font-bold uppercase tracking-wider text-[#EAF3FF]">
              Detailed Records ({filteredAndSortedRows.length})
            </span>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-3.5 w-3.5 text-[#91A9C5]" />
              <input
                type="text"
                value={tableFilter}
                onChange={(e) => setTableFilter(e.target.value)}
                placeholder="Filter records..."
                className="rounded-xl border border-[#1B3F70] bg-[#06152B] pl-9 pr-3 py-1.5 text-xs text-[#EAF3FF] placeholder-[#91A9C5]/70 focus:border-[#168BFF] focus:outline-none"
              />
            </div>
            <a
              href={apiClient.getExportCsvUrl(currentRun.query_id)}
              download={`querypilot_${currentRun.query_id}.csv`}
              className="inline-flex items-center gap-1.5 rounded-xl border border-[#00C8FF]/40 bg-[#168BFF]/20 px-3.5 py-1.5 text-xs font-semibold text-[#EAF3FF] hover:bg-[#168BFF] hover:text-white transition"
            >
              <Download className="h-3.5 w-3.5 text-[#00C8FF]" />
              Download CSV
            </a>
          </div>
        </div>

        {columns.length === 0 || rows.length === 0 ? (
          <div className="p-8 text-center text-xs text-[#91A9C5]">
            No matching records found for this query.
          </div>
        ) : (
          <div className="max-h-80 overflow-auto">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-[#06152B] text-[#91A9C5] border-b border-[#163661]">
                <tr>
                  {columns.map((col) => (
                    <th
                      key={col}
                      onClick={() => handleSort(col)}
                      className="cursor-pointer whitespace-nowrap px-5 py-3 font-semibold uppercase tracking-wider hover:text-[#00C8FF]"
                    >
                      {col.replace(/_/g, " ")}
                      {sortCol === col ? (sortDesc ? " ↓" : " ↑") : ""}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#142F54]/70">
                {filteredAndSortedRows.map((row, rIdx) => (
                  <tr
                    key={rIdx}
                    className="hover:bg-[#168BFF]/10 transition-colors"
                  >
                    {columns.map((col) => {
                      const val = row[col];
                      const isNum = typeof val === "number";
                      return (
                        <td
                          key={col}
                          className={`whitespace-nowrap px-5 py-2.5 ${
                            isNum
                              ? "font-semibold text-[#00C8FF]"
                              : "text-[#EAF3FF]"
                          }`}
                        >
                          {val === null || val === undefined
                            ? "—"
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
