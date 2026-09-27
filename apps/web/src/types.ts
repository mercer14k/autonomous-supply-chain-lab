export type Policy = "agents" | "heuristic" | "min_max" | "reorder_point";
export interface Config {
  seed: number;
  days: number;
  policy: Policy;
  mode: "autonomous" | "approval";
  runtime: "none" | "ollama" | "llamacpp" | "vllm";
  model: string;
  daily_budget_cents?: number;
}
export interface ModelCatalog {
  runtime: Exclude<Config["runtime"], "none">;
  available: boolean;
  models: {
    id: string;
    parameters: string | null;
    quantization: string | null;
  }[];
  message: string;
}
export interface KPI {
  day: number;
  service_level: number | null;
  total_cost: number;
  procurement_cost: number;
  transport_cost: number;
  holding_cost: number;
  shortage_cost: number;
  total_demand: number;
  total_filled: number;
  lost_units: number;
  stockout_frequency: number | null;
  on_hand_units: number;
  working_capital: number;
  inventory_value: number;
  pipeline_value: number;
  inventory_turns_annualized: number | null;
  expedite_usage: number;
  open_orders: number;
  daily_demand?: number;
  daily_filled?: number;
}
export interface Action {
  tool: string;
  sku_id: string;
  warehouse_id: string;
  supplier_id: string;
  quantity: number;
  evidence_ids: string[];
}
export interface Decision {
  id: string;
  agent: string;
  tool: string;
  kind: string;
  evidence_ids: string[];
  summary: Record<string, unknown>;
  status: string;
}
export interface Telemetry {
  runtime: string;
  model: string | null;
  latency_ms: number;
  tokens: number | null;
  fallback: boolean;
  validation_failures: string[];
  model_attempts: number;
  prompt_version: string;
}
export interface Plan {
  day: number;
  actions: Action[];
  decisions: Decision[];
  telemetry: Telemetry;
  missing_evidence: string[];
}
export interface Episode {
  id: string;
  dataset_id: string;
  created_at: string;
  config: Config;
  day: number;
  status: string;
  kpis: KPI;
  history: KPI[];
  pending: Plan | null;
  engine_version: string;
  version: number;
}
export interface Frame {
  day: number;
  decisions: Decision[];
  telemetry: Telemetry;
  outcomes: {
    action: Action;
    status: string;
    reason: string;
    accepted_quantity: number;
  }[];
  kpis: KPI;
  disruptions: Record<string, unknown>[];
  approval: string;
  ledger?: Record<string, unknown>[];
}
export interface Inventory {
  id: string;
  sku_id: string;
  warehouse_id: string;
  name: string;
  category: string;
  on_hand: number;
  pipeline: number;
  daily_forecast: number | null;
  days_cover: number | null;
  lead_days: number;
  supplier_id: string | null;
  forecast_basis: string;
  source_id: string;
}
export interface Page<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}
export interface Network {
  id: string;
  sku_count: number;
  suppliers: {
    id: string;
    name: string;
    lead_days: number;
    daily_capacity: number;
    reliability: number;
  }[];
  plants: { id: string; name: string; daily_capacity: number }[];
  warehouses: {
    id: string;
    name: string;
    capacity: number;
    transport_days: number;
  }[];
  markets: { id: string; name: string; warehouse_id: string }[];
  disruptions: {
    id: string;
    kind: string;
    target_id: string;
    start_day: number;
    duration: number;
    magnitude: number;
  }[];
  validation: ValidationReport;
}
export interface ValidationReport {
  id?: string;
  accepted: boolean;
  record_count: number;
  source_id: string;
  ingested_at: string;
  errors: { location: string; message: string }[];
  warnings: { record_id: string; message: string }[];
}
