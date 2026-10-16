import React, { useEffect, useState } from "react";
import {
  Bookmark,
  ExternalLink,
  History,
  Search,
  Trash2,
} from "lucide-react";
import { apiClient } from "../../api/client";
import type { HistoryItem, QueryPilotRun } from "../../types/querypilot";

interface QueryHistoryProps {
  onSelectQuery: (run: QueryPilotRun) => void;
}

export const QueryHistory: React.FC<QueryHistoryProps> = ({
  onSelectQuery,
}) => {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [bookmarkedOnly, setBookmarkedOnly] = useState<boolean>(false);
  const [search, setSearch] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);

  const loadHistory = async () => {
    setLoading(true);
    try {
      const res = await apiClient.getHistory({
        bookmarkedOnly,
        search: search.trim() || undefined,
      });
      setItems(res.items);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, [bookmarkedOnly]);

  const handleOpen = async (queryId: string) => {
    const full = await apiClient.getQuery(queryId);
    onSelectQuery(full);
  };

  const handleToggleBookmark = async (item: HistoryItem) => {
    await apiClient.toggleBookmark(item.query_id, {
      bookmarked: !item.bookmarked,
    });
    loadHistory();
  };

  const handleDelete = async (queryId: string) => {
    await apiClient.deleteHistory(queryId);
    loadHistory();
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-800 bg-slate-900/90 px-5 py-4">
        <div className="flex items-center gap-2.5">
          <History className="h-5 w-5 text-emerald-400" />
          <div>
            <h2 className="text-sm font-bold text-slate-100">
              Saved & Past Questions ({items.length})
            </h2>
            <p className="text-xs text-slate-400">
              Reopen any previous question to view its charts, summary, and
              data table.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-xl border border-slate-800 bg-slate-950 p-1">
            <button
              type="button"
              onClick={() => setBookmarkedOnly(false)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                !bookmarkedOnly
                  ? "bg-emerald-600 text-white"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              All Questions
            </button>
            <button
              type="button"
              onClick={() => setBookmarkedOnly(true)}
              className={`inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                bookmarkedOnly
                  ? "bg-amber-600 text-white"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Bookmark className="h-3 w-3" /> Saved Reports
            </button>
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              loadHistory();
            }}
            className="flex items-center gap-1.5"
          >
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-500" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search past questions..."
                className="rounded-xl border border-slate-700 bg-slate-950 pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
              />
            </div>
            <button
              type="submit"
              className="rounded-xl bg-slate-800 px-3.5 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700 transition"
            >
              Search
            </button>
          </form>
        </div>
      </div>

      {loading ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-10 text-center text-xs text-slate-400">
          Loading past questions...
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-10 text-center text-xs text-slate-400">
          No past questions found yet.
        </div>
      ) : (
        <div className="space-y-2.5">
          {items.map((item) => (
            <div
              key={item.query_id}
              className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-800 bg-slate-900/80 p-4 hover:border-slate-700 transition"
            >
              <div className="space-y-1 max-w-3xl">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold text-sm text-slate-100">
                    {item.question}
                  </span>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-[10px] font-semibold capitalize ${
                      item.status === "completed"
                        ? "bg-emerald-500/15 text-emerald-300"
                        : item.status === "awaiting_approval"
                          ? "bg-amber-500/15 text-amber-300"
                          : "bg-rose-500/15 text-rose-300"
                    }`}
                  >
                    {item.status === "awaiting_approval"
                      ? "Needs Review"
                      : item.status.replace("_", " ")}
                  </span>
                  <span className="text-xs text-slate-400">
                    {item.row_count} rows
                  </span>
                </div>
                <p className="text-xs text-slate-400">{item.title}</p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleToggleBookmark(item)}
                  className={`inline-flex items-center gap-1 rounded-xl border px-3 py-1.5 text-xs font-medium transition ${
                    item.bookmarked
                      ? "border-amber-500/50 bg-amber-500/20 text-amber-300"
                      : "border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700"
                  }`}
                >
                  <Bookmark className="h-3.5 w-3.5" />
                  {item.bookmarked ? "Saved" : "Save"}
                </button>
                <button
                  type="button"
                  onClick={() => handleOpen(item.query_id)}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 transition"
                >
                  <ExternalLink className="h-3.5 w-3.5" /> Open Report
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(item.query_id)}
                  className="inline-flex items-center rounded-xl border border-slate-700 bg-slate-800 p-2 text-slate-400 hover:text-rose-400 transition"
                  title="Remove from history"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
