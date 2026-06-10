export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };

export type JsonRecord = Record<string, JsonValue | undefined>;

export interface RunStatus extends JsonRecord {
  run_id?: string;
  status?: string;
  active_scene?: string;
  current_agent?: string;
  routing_decision?: string;
  cost_usd?: number;
  budget_usd?: number;
}

export interface LedgerSnapshot extends JsonRecord {
  book_id?: string;
  scene_id?: string;
  book_metrics?: JsonValue;
  promise_ledger?: JsonValue;
  bible_tracker?: JsonValue;
  character_arc?: JsonValue;
  intimacy_escalation?: JsonValue;
  reader_information_state?: JsonValue;
  scene_rhythm?: JsonValue;
  subplot_ledger?: JsonValue;
  trope_commitment?: JsonValue;
  series_promise?: JsonValue;
}

export interface QualityGateEvent extends JsonRecord {
  event?: string;
  run_id?: string;
  book_id?: string;
  scene_id?: string;
  agent?: string;
  decision?: string;
  routing_decision?: string;
  score?: number;
  message?: string;
  created_at?: string;
}

export type QualityGateHistory = QualityGateEvent[];

export type MetricGranularity = "chapter" | "scene" | "beat";

export interface MetricHistoryItem {
  book_id?: string;
  chapter_id?: string;
  scene_id?: string;
  beat_id?: string;
  scene_count?: number;
  word_count?: number;
  timestamp?: string;
  metrics?: Record<string, number | string | boolean | null | undefined>;
}

export interface MetricHistoryResponse {
  book_id: string;
  granularity: MetricGranularity;
  metric?: string | null;
  items: MetricHistoryItem[];
}

export interface CharacterMetricsResponse {
  book_id: string;
  character_id: string;
  items: MetricHistoryItem[];
}
