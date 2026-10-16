import type {
  ApprovalItem,
  CostEstimate,
  HealthStatus,
  HistoryItem,
  QueryPilotRun,
  SchemaDiscoveryResponse,
  ValidationResult,
} from "../types/querypilot";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

async function requestJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    let errText = `HTTP ${response.status}`;
    try {
      const errBody = await response.json();
      errText = errBody.detail || errBody.message || errText;
    } catch {
      // ignore json parse error
    }
    throw new Error(errText);
  }
  return response.json() as Promise<T>;
}

export const apiClient = {
  getHealth: () => requestJson<HealthStatus>("/api/v1/health"),

  updateLLMSettings: (payload: {
    gemini_api_key?: string;
    gemini_model?: string;
    llm_provider?: string;
  }) =>
    requestJson<HealthStatus["llm"]>("/api/v1/settings/llm", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  runQuery: (payload: {
    question: string;
    thread_id?: string;
    conversation_history?: Array<Record<string, string>>;
    cost_threshold_override?: number;
  }) =>
    requestJson<QueryPilotRun>("/api/v1/query", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getQuery: (queryId: string) =>
    requestJson<QueryPilotRun>(`/api/v1/query/${encodeURIComponent(queryId)}`),

  getExportCsvUrl: (queryId: string) =>
    `${API_BASE}/api/v1/query/${encodeURIComponent(queryId)}/export`,

  validateSql: (sql: string) =>
    requestJson<ValidationResult>("/api/v1/sql/validate", {
      method: "POST",
      body: JSON.stringify({ sql, dialect: "postgresql" }),
    }),

  estimateSqlCost: (sql: string, threadId = "", costThresholdOverride?: number) =>
    requestJson<{
      is_valid: boolean;
      validation: ValidationResult;
      cost_estimate: CostEstimate | null;
    }>("/api/v1/sql/cost", {
      method: "POST",
      body: JSON.stringify({
        sql,
        thread_id: threadId,
        cost_threshold_override: costThresholdOverride,
      }),
    }),

  executeSql: (payload: {
    sql: string;
    query_id?: string;
    question?: string;
    thread_id?: string;
    cost_threshold_override?: number;
  }) =>
    requestJson<QueryPilotRun>("/api/v1/sql/execute", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getSchema: () => requestJson<SchemaDiscoveryResponse>("/api/v1/schema"),

  getApprovals: (status?: string) =>
    requestJson<{ pending_count: number; items: ApprovalItem[] }>(
      `/api/v1/approvals${status ? `?status=${encodeURIComponent(status)}` : ""}`
    ),

  decideApproval: (
    queryId: string,
    payload: {
      decision: "approved" | "rejected";
      reviewer_comment?: string;
      expected_sql?: string;
    }
  ) =>
    requestJson<QueryPilotRun>(
      `/api/v1/approvals/${encodeURIComponent(queryId)}/decision`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    ),

  getHistory: (params?: { bookmarkedOnly?: boolean; search?: string }) => {
    const q = new URLSearchParams();
    if (params?.bookmarkedOnly) q.set("bookmarked_only", "true");
    if (params?.search) q.set("search", params.search);
    const qs = q.toString();
    return requestJson<{ count: number; items: HistoryItem[] }>(
      `/api/v1/history${qs ? `?${qs}` : ""}`
    );
  },

  toggleBookmark: (
    queryId: string,
    payload: { bookmarked?: boolean; title?: string }
  ) =>
    requestJson<QueryPilotRun>(
      `/api/v1/history/${encodeURIComponent(queryId)}/bookmark`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    ),

  deleteHistory: (queryId: string) =>
    requestJson<{ deleted: boolean; query_id: string }>(
      `/api/v1/history/${encodeURIComponent(queryId)}`,
      { method: "DELETE" }
    ),
};
