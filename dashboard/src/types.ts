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

export interface WordBudgetSceneTrace {
  scene_index?: number;
  scene_id?: string;
  status?: string;
  planned_word_count_target?: number;
  adjusted_word_count_target?: number;
  actual_word_count?: number;
  actual_words_so_far_before?: number;
  actual_words_so_far_after?: number;
  remaining_scenes_before?: number;
  remaining_scenes_after?: number;
  projected_final_count_before?: number;
  projected_final_count_after?: number;
  minimum_target_applied?: boolean;
}

export interface WordBudgetStatus {
  enabled: boolean;
  book_word_count_target?: number;
  planned_word_count_target?: number;
  actual_word_count?: number;
  remaining_word_budget?: number;
  surplus_words?: number;
  surplus_pct?: number;
  projected_final_count?: number;
  min_scene_target?: number;
  scene_count?: number;
  completed_scene_count?: number;
  scenes?: WordBudgetSceneTrace[];
}

export interface BookRunSummary {
  book_id?: string;
  run_id?: string;
  summary_found?: boolean;
  summary_path?: string;
  word_budget_status?: WordBudgetStatus;
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

export type LedgerEvent = Record<string, JsonValue | undefined>;

export type PromiseGroups = Record<string, LedgerEvent[]>;

export interface BookPromisesResponse {
  book_id: string;
  promises: PromiseGroups;
}

export interface BookIntimacyResponse {
  book_id: string;
  events: LedgerEvent[];
}

export interface EvoSkillEntry {
  skill_id: string;
  content: string;
}

export interface VoiceCalibrationResponse {
  series_id: string;
  profile_found: boolean;
  profile_path?: string;
  profile_id?: string;
  version?: string;
  display_name?: string;
  calibration_history: LedgerEvent[];
}
