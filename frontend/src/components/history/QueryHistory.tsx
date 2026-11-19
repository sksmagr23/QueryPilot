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
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-[#163661] bg-[#0A1F3D]/95 px-6 py-5 shadow-md">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#00C8FF]/30 bg-[#168BFF]/15 text-[#00C8FF]">
            <History className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-[#EAF3FF]">
              Saved & Past Questions ({items.length})
            </h2>
            <p className="text-xs text-[#91A9C5]">
              Reopen any previous question to view its charts, summary, and
              records.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex rounded-xl border border-[#163661] bg-[#06152B] p-1">
            <button
              type="button"
              onClick={() => setBookmarkedOnly(false)}
              className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
                !bookmarkedOnly
                  ? "bg-[#168BFF] text-white"
                  : "text-[#91A9C5] hover:text-[#EAF3FF]"
              }`}
            >
              All Questions
            </button>
            <button
              type="button"
              onClick={() => setBookmarkedOnly(true)}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
                bookmarkedOnly
                  ? "bg-[#168BFF] text-white"
                  : "text-[#91A9C5] hover:text-[#EAF3FF]"
              }`}
            >
              <Bookmark className="h-3.5 w-3.5 text-[#00C8FF]" /> Saved Reports
            </button>
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              loadHistory();
            }}
            className="flex items-center gap-2"
          >
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-3.5 w-3.5 text-[#91A9C5]" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search questions..."
                className="rounded-xl border border-[#1B3F70] bg-[#06152B] pl-9 pr-3 py-1.5 text-xs text-[#EAF3FF] placeholder-[#91A9C5]/60 focus:border-[#168BFF] focus:outline-none"
              />
            </div>
            <button
              type="submit"
              className="rounded-xl border border-[#1B3F70] bg-[#0D2548] px-3.5 py-1.5 text-xs font-semibold text-[#EAF3FF] hover:border-[#168BFF] transition"
            >
              Search
            </button>
          </form>
        </div>
      </div>

      {loading ? (
        <div className="rounded-2xl border border-[#163661] bg-[#091D38]/60 p-12 text-center text-xs text-[#91A9C5]">
          Loading past questions...
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-2xl border border-[#163661] bg-[#091D38]/60 p-12 text-center text-xs text-[#91A9C5]">
          No past questions found yet.
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div
              key={item.query_id}
              className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-[#163661] bg-[#091D38]/90 p-5 hover:border-[#168BFF]/50 transition"
            >
              <div className="space-y-1 max-w-3xl">
                <div className="flex flex-wrap items-center gap-2.5">
                  <span className="font-bold text-sm text-[#EAF3FF]">
                    {item.question}
                  </span>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-[10px] font-semibold capitalize ${
                      item.status === "completed"
                        ? "bg-[#00C8FF]/15 text-[#00C8FF]"
                        : item.status === "awaiting_approval"
                          ? "bg-amber-400/15 text-amber-300"
                          : "bg-rose-500/15 text-rose-300"
                    }`}
                  >
                    {item.status === "awaiting_approval"
                      ? "Pending Review"
                      : item.status.replace("_", " ")}
                  </span>
                  <span className="text-xs text-[#91A9C5]">
                    {item.row_count} records
                  </span>
                </div>
                <p className="text-xs text-[#91A9C5]">{item.title}</p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleToggleBookmark(item)}
                  className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold transition ${
                    item.bookmarked
                      ? "border-[#00C8FF]/50 bg-[#00C8FF]/15 text-[#00C8FF]"
                      : "border-[#1B3F70] bg-[#0D2548] text-[#EAF3FF] hover:border-[#168BFF]"
                  }`}
                >
                  <Bookmark className="h-3.5 w-3.5" />
                  {item.bookmarked ? "Saved" : "Save"}
                </button>
                <button
                  type="button"
                  onClick={() => handleOpen(item.query_id)}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-[#168BFF] px-4 py-1.5 text-xs font-semibold text-white shadow-sm shadow-[#168BFF]/30 hover:bg-[#168BFF]/90 transition"
                >
                  <ExternalLink className="h-3.5 w-3.5" /> Open Report
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(item.query_id)}
                  className="inline-flex items-center rounded-xl border border-[#1B3F70] bg-[#06152B] p-2 text-[#91A9C5] hover:text-rose-400 transition"
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
