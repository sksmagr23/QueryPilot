import React, { useMemo, useState } from "react";
import { BookOpen, Database, Search, Table2 } from "lucide-react";
import type { SchemaDiscoveryResponse } from "../../types/querypilot";

interface SchemaExplorerProps {
  schema: SchemaDiscoveryResponse | null;
}

export const SchemaExplorer: React.FC<SchemaExplorerProps> = ({ schema }) => {
  const [search, setSearch] = useState("");
  const [selectedTable, setSelectedTable] = useState<string>("orders");
  const [activeSubTab, setActiveSubTab] = useState<"tables" | "metrics">(
    "tables"
  );

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

  if (!schema) {
    return (
      <div className="rounded-2xl border border-[#163661] bg-[#091D38]/60 p-12 text-center text-sm text-[#91A9C5]">
        Loading store data catalog...
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header & Sub-tab Switcher */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-[#163661] bg-[#0A1F3D]/95 px-6 py-5 shadow-md">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#00C8FF]/30 bg-[#168BFF]/15 text-[#00C8FF]">
            <Database className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-[#EAF3FF]">
              Store Data Catalog ({schema.tables.length} Datasets)
            </h2>
            <p className="text-xs text-[#91A9C5]">
              Browse available business datasets and official metric definitions
              you can ask about.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1 rounded-xl border border-[#163661] bg-[#06152B] p-1">
          <button
            type="button"
            onClick={() => setActiveSubTab("tables")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-4 py-1.5 text-xs font-semibold transition ${
              activeSubTab === "tables"
                ? "bg-[#168BFF] text-white"
                : "text-[#91A9C5] hover:text-[#EAF3FF]"
            }`}
          >
            <Table2 className="h-3.5 w-3.5" /> Datasets & Fields
          </button>
          <button
            type="button"
            onClick={() => setActiveSubTab("metrics")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-4 py-1.5 text-xs font-semibold transition ${
              activeSubTab === "metrics"
                ? "bg-[#168BFF] text-white"
                : "text-[#91A9C5] hover:text-[#EAF3FF]"
            }`}
          >
            <BookOpen className="h-3.5 w-3.5" /> Business Metrics
          </button>
        </div>
      </div>

      {activeSubTab === "tables" && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          {/* Left: Dataset List */}
          <div className="rounded-2xl border border-[#163661] bg-[#091D38]/90 p-4 space-y-3">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-3.5 w-3.5 text-[#91A9C5]" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search datasets or fields..."
                className="w-full rounded-xl border border-[#1B3F70] bg-[#06152B] pl-9 pr-3 py-2 text-xs text-[#EAF3FF] placeholder-[#91A9C5]/60 focus:border-[#168BFF] focus:outline-none"
              />
            </div>
            <div className="space-y-2">
              {filteredTables.map((t) => (
                <button
                  key={t.name}
                  type="button"
                  onClick={() => setSelectedTable(t.name)}
                  className={`w-full rounded-xl border p-3.5 text-left transition ${
                    currentTableObj?.name === t.name
                      ? "border-[#00C8FF]/60 bg-[#168BFF]/15"
                      : "border-[#163661] bg-[#06152B]/60 hover:border-[#168BFF]/40"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold capitalize text-[#EAF3FF]">
                      {t.name.replace(/_/g, " ")}
                    </span>
                    <span className="rounded-full bg-[#0D2548] px-2.5 py-0.5 text-[10px] font-semibold text-[#00C8FF]">
                      {t.row_count.toLocaleString()} records
                    </span>
                  </div>
                  <p className="mt-1 text-[11px] text-[#91A9C5] line-clamp-2">
                    {t.description}
                  </p>
                </button>
              ))}
            </div>
          </div>

          {/* Right: Fields List */}
          {currentTableObj && (
            <div className="lg:col-span-2 rounded-2xl border border-[#163661] bg-[#091D38]/90 overflow-hidden">
              <div className="border-b border-[#163661] bg-[#0A2140] px-6 py-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold capitalize text-[#EAF3FF]">
                    {currentTableObj.name.replace(/_/g, " ")}
                  </h3>
                  <span className="text-xs text-[#00C8FF] font-medium">
                    {currentTableObj.columns.length} fields •{" "}
                    {currentTableObj.row_count.toLocaleString()} records
                  </span>
                </div>
                <p className="mt-1 text-xs text-[#91A9C5]">
                  {currentTableObj.description}
                </p>
              </div>
              <div className="p-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
                {currentTableObj.columns.map((col) => (
                  <div
                    key={col.name}
                    className="rounded-xl border border-[#163661] bg-[#06152B]/70 px-4 py-3 flex items-center justify-between"
                  >
                    <span className="text-xs font-semibold text-[#EAF3FF]">
                      {col.name.replace(/_/g, " ")}
                    </span>
                    <span className="text-[11px] text-[#91A9C5]">
                      {col.name}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {activeSubTab === "metrics" && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {schema.semantic_metrics.map((m) => (
            <div
              key={m.id}
              className="rounded-2xl border border-[#163661] bg-[#091D38]/90 p-5 space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-sm text-[#EAF3FF]">
                  {m.name}
                </span>
                <span className="rounded-full border border-[#00C8FF]/30 bg-[#00C8FF]/10 px-2.5 py-0.5 text-[10px] font-semibold text-[#00C8FF]">
                  {m.unit}
                </span>
              </div>
              <p className="text-xs text-[#91A9C5] leading-relaxed">
                {m.description}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
