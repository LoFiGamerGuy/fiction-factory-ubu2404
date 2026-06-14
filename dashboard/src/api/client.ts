import type {
  BookIntimacyResponse,
  BookPromisesResponse,
  BookRunSummary,
  CharacterMetricsResponse,
  EvoSkillEntry,
  LedgerSnapshot,
  MetricGranularity,
  MetricHistoryResponse,
  PromiseGroups,
  QualityGateEvent,
  QualityGateHistory,
  RunStatus,
  VoiceCalibrationResponse
} from "../types";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";

function apiUrl(path: string): string {
  return `${configuredBaseUrl}${path}`;
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    headers: {
      Accept: "application/json",
      ...init?.headers
    },
    ...init
  });

  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }

  return (await response.json()) as T;
}

export function getRunStatus(runId: string): Promise<RunStatus> {
  return fetchJson<RunStatus>(`/runs/${encodeURIComponent(runId)}/status`);
}

export function getLedgers(bookId: string): Promise<LedgerSnapshot> {
  return fetchJson<LedgerSnapshot>(`/books/${encodeURIComponent(bookId)}/ledgers`);
}

export function getBookRunSummary(bookId: string): Promise<BookRunSummary> {
  return fetchJson<BookRunSummary>(`/books/${encodeURIComponent(bookId)}/summary`);
}

export function getBookPromises(bookId: string): Promise<BookPromisesResponse> {
  return fetchJson<BookPromisesResponse>(`/books/${encodeURIComponent(bookId)}/promises`);
}

export function getBookIntimacy(bookId: string): Promise<BookIntimacyResponse> {
  return fetchJson<BookIntimacyResponse>(`/books/${encodeURIComponent(bookId)}/intimacy`);
}

export function getQualityGates(bookId: string): Promise<QualityGateHistory> {
  return fetchJson<QualityGateHistory>(`/books/${encodeURIComponent(bookId)}/quality_gates`);
}

export function getMetricHistory(
  bookId: string,
  granularity: MetricGranularity,
  metric: string
): Promise<MetricHistoryResponse> {
  const params = new URLSearchParams({ granularity, metric });
  return fetchJson<MetricHistoryResponse>(`/books/${encodeURIComponent(bookId)}/metrics/history?${params}`);
}

export function getCharacterMetrics(
  bookId: string,
  characterId: string
): Promise<CharacterMetricsResponse> {
  return fetchJson<CharacterMetricsResponse>(
    `/books/${encodeURIComponent(bookId)}/characters/${encodeURIComponent(characterId)}/metrics`
  );
}

export function getSeriesPromises(seriesId: string): Promise<PromiseGroups> {
  return fetchJson<PromiseGroups>(`/series/${encodeURIComponent(seriesId)}/promises`);
}

export function getEvoSkill(seriesId: string): Promise<EvoSkillEntry[]> {
  return fetchJson<EvoSkillEntry[]>(`/series/${encodeURIComponent(seriesId)}/evoskill`);
}

export function getVoiceCalibration(seriesId: string): Promise<VoiceCalibrationResponse> {
  return fetchJson<VoiceCalibrationResponse>(`/series/${encodeURIComponent(seriesId)}/voice_calibration`);
}

export function openRunEventStream(
  runId: string,
  onEvent: (event: QualityGateEvent) => void,
  onError?: () => void
): EventSource {
  const source = new EventSource(apiUrl(`/runs/${encodeURIComponent(runId)}/stream`));
  const handleMessage = (message: MessageEvent) => {
    onEvent(parseEventData(String(message.data)));
  };

  source.onmessage = (message) => {
    handleMessage(message);
  };

  for (const eventName of ["update", "quality_gate", "routing_decision", "agent", "heartbeat"]) {
    source.addEventListener(eventName, handleMessage);
  }

  source.onerror = () => {
    onError?.();
  };
  return source;
}

function parseEventData(data: string): QualityGateEvent {
  try {
    return JSON.parse(data) as QualityGateEvent;
  } catch {
    return { event: "message", message: data };
  }
}
