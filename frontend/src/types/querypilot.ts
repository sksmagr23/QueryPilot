export interface TraceStep {
  node_id: string;
  label: string;
  status: string;
  started_at: string;
  completed_at: string;
  latency_ms: number;
  attempt: number;
  summary: string;
  input_snapshot: Record<string, unknown>;
  output_snapshot: Record<string, unknown>;
}

export interface ValidationResult {
  is_valid: boolean;
  is_safe: boolean;
  statement_type: string;
  errors: string[];
  referenced_tables: string[];
  referenced_columns: string[];
  normalized_sql: string;
}

export interface CostEstimate {
  estimated_cost: number;
  estimated_rows: number;
  cost_threshold: number;
  risk_level: "low" | "medium" | "high";
  has_cross_join: boolean;
  seq_scan_tables: string[];
  join_count: number;
  requires_approval: boolean;
  approval_reasons: string[];
  approval_reason: string | null;
  context_fingerprint: string;
  explain_plan?: unknown;
}

export interface ExecutionResult {
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  truncated: boolean;
  max_rows_enforced?: number;
  timeout_ms_enforced?: number;
  execution_time_ms: number;
  error: string | null;
}

export interface KPICard {
  label: string;
  value: string;
  subtext: string;
}

export interface AnalysisSummary {
  row_count: number;
  primary_dimension: string | null;
  primary_metric: string | null;
  numeric_columns: string[];
  dimension_columns: string[];
  metric_total: number | null;
  metric_mean: number | null;
  metric_min: number | null;
  metric_max: number | null;
  top_performer: { dimension: unknown; value: number } | null;
  bottom_performer: { dimension: unknown; value: number } | null;
  top_share_pct: number | null;
  period_over_period_change_pct: number | null;
  rankings: Array<{
    rank: number;
    dimension: string;
    metric_value: number;
    share_pct: number | null;
  }>;
  kpis: KPICard[];
}

export interface VisualizationSpec {
  chart_type: "bar" | "line" | "area" | "pie" | "composed" | "table_only";
  title: string;
  subtitle: string;
  x_key: string;
  y_keys: string[];
  series: Array<{
    key: string;
    label: string;
    color: string;
    type: string;
  }>;
  data: Record<string, unknown>[];
}

export interface BusinessResponse {
  headline: string;
  summary: string;
  key_findings: string[];
  assumptions: string[];
  limitations: string[];
  follow_up_suggestions: string[];
  sql_reference: string | null;
}

export interface QueryPilotRun {
  query_id: string;
  thread_id: string;
  question: string;
  title?: string;
  bookmarked?: boolean;
  created_at?: string;
  updated_at?: string;
  status:
    | "completed"
    | "awaiting_approval"
    | "clarification_needed"
    | "rejected"
    | "blocked"
    | "error"
    | "running";
  error_message?: string | null;
  sql_retry_count: number;
  exec_retry_count: number;
  result_retry_count: number;
  generation_attempts: number;
  llm_provider_used?: string;
  llm_model_used?: string;
  intent?: Record<string, unknown>;
  query_plan?: Record<string, unknown>;
  generated_sql: string;
  sql_rationale?: string;
  validation_result?: ValidationResult;
  cost_estimate?: CostEstimate;
  approval_status: "not_required" | "pending" | "approved" | "rejected" | "invalidated";
  approval_fingerprint: string;
  approval_executed: boolean;
  reviewer_comment?: string | null;
  execution_result?: ExecutionResult | null;
  result_validation?: Record<string, unknown>;
  analysis?: AnalysisSummary;
  visualization?: VisualizationSpec;
  response?: BusinessResponse;
  trace: TraceStep[];
  edges_traversed: Array<{ source: string; target: string }>;
  model_calls: number;
  tool_calls: number;
  total_latency_ms: number;
}

export interface SchemaTable {
  name: string;
  description: string;
  row_count: number;
  primary_keys: string[];
  columns: Array<{
    name: string;
    type: string;
    nullable: boolean;
    is_primary_key: boolean;
    foreign_key?: string | null;
  }>;
}

export interface SchemaDiscoveryResponse {
  dialect: string;
  schema_version: string;
  tables: SchemaTable[];
  table_columns: Record<string, string[]>;
  relationships: Array<{
    source_table: string;
    source_column: string;
    target_table: string;
    target_column: string;
    join_sql: string;
  }>;
  semantic_metrics: Array<{
    id: string;
    name: string;
    description: string;
    sql_formula: string;
    tables: string[];
    unit: string;
    synonyms: string[];
  }>;
  valid_joins: Array<{
    left_table: string;
    right_table: string;
    join_condition: string;
    cardinality: string;
    description: string;
  }>;
}

export interface HistoryItem {
  query_id: string;
  thread_id: string;
  question: string;
  title: string;
  status: string;
  generated_sql: string;
  approval_status: string;
  estimated_cost: number;
  risk_level: string;
  row_count: number;
  total_latency_ms: number;
  bookmarked: boolean;
  created_at: string;
  updated_at: string;
}

export interface ApprovalItem {
  query_id: string;
  thread_id: string;
  question: string;
  title: string;
  status: string;
  generated_sql: string;
  approval_status: string;
  approval_fingerprint: string;
  approval_executed: boolean;
  reviewer_comment: string | null;
  estimated_cost: number;
  risk_level: string;
  approval_reason: string | null;
  approval_reasons: string[];
  created_at: string;
  updated_at: string;
}

export interface HealthStatus {
  status: string;
  database: {
    connected: boolean;
    dialect: string;
    readonly_enforced: boolean;
    statement_timeout_ms: number;
    max_result_rows: number;
    table_counts: Record<string, number>;
  };
  llm: {
    configured_provider: string;
    effective_provider: string;
    gemini_api_key_present: boolean;
    gemini_model: string;
    gemini_fallback_model: string;
  };
  safety: {
    cost_approval_threshold: number;
    max_sql_retries: number;
    max_exec_retries: number;
    max_result_retries: number;
  };
}
