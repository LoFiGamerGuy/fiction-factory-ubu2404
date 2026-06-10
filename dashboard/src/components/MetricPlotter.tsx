import { useEffect, useState } from "react";
import { getMetricHistory } from "../api/client";
import type { MetricGranularity, MetricHistoryItem } from "../types";

interface MetricPlotterProps {
  bookId: string;
}

const metricOptions = [
  "interiority_pct",
  "sensory_density_per_1k",
  "heat_curve_position",
  "dialogue_ratio",
  "exposition_pct",
  "action_pct",
  "ai_tell_count",
  "word_count"
];

const granularityOptions: MetricGranularity[] = ["chapter", "scene", "beat"];

export function MetricPlotter({ bookId }: MetricPlotterProps) {
  const [metric, setMetric] = useState("interiority_pct");
  const [granularity, setGranularity] = useState<MetricGranularity>("chapter");
  const [items, setItems] = useState<MetricHistoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    async function loadHistory() {
      setIsLoading(true);
      setError(null);
      try {
        const response = await getMetricHistory(bookId, granularity, metric);
        if (!isCancelled) {
          setItems(response.items);
        }
      } catch (loadError) {
        if (!isCancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load metric history");
          setItems([]);
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadHistory();

    return () => {
      isCancelled = true;
    };
  }, [bookId, granularity, metric]);

  const points = items.map((item) => toNumber(item.metrics?.[metric]));

  return (
    <section className="panel historical-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Historical Metrics</p>
          <h2>Metric Plotter</h2>
        </div>
        <span className="status-pill">{isLoading ? "Loading" : `${items.length} points`}</span>
      </div>

      <div className="inline-controls">
        <label>
          Metric
          <select value={metric} onChange={(event) => setMetric(event.target.value)}>
            {metricOptions.map((option) => (
              <option key={option} value={option}>
                {formatLabel(option)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Granularity
          <select
            value={granularity}
            onChange={(event) => setGranularity(event.target.value as MetricGranularity)}
          >
            {granularityOptions.map((option) => (
              <option key={option} value={option}>
                {formatLabel(option)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error ? <p className="error">{error}</p> : null}

      <Sparkline values={points} />

      <ol className="compact-list">
        {items.length > 0 ? (
          items.slice(-8).map((item, index) => (
            <li key={`${item.chapter_id ?? "chapter"}-${item.scene_id ?? "scene"}-${item.beat_id ?? index}`}>
              <span>{labelForItem(item, granularity)}</span>
              <strong>{formatMetricValue(item.metrics?.[metric])}</strong>
            </li>
          ))
        ) : (
          <li className="muted">No {formatLabel(metric)} history loaded for {bookId}.</li>
        )}
      </ol>
    </section>
  );
}

function Sparkline({ values }: { values: number[] }) {
  const validValues = values.filter((value) => Number.isFinite(value));
  if (validValues.length === 0) {
    return <div className="chart-empty">No numeric points yet.</div>;
  }

  const min = Math.min(...validValues);
  const max = Math.max(...validValues);
  const spread = max - min || 1;
  const width = 640;
  const height = 180;
  const path = validValues
    .map((value, index) => {
      const x = validValues.length === 1 ? width / 2 : (index / (validValues.length - 1)) * width;
      const y = height - ((value - min) / spread) * height;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <div className="chart-shell">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Metric trajectory">
        <path className="chart-grid" d={`M0,${height} H${width} M0,${height / 2} H${width} M0,0 H${width}`} />
        <path className="chart-line" d={path} />
      </svg>
      <div className="chart-range">
        <span>min {formatMetricValue(min)}</span>
        <span>max {formatMetricValue(max)}</span>
      </div>
    </div>
  );
}

function labelForItem(item: MetricHistoryItem, granularity: MetricGranularity): string {
  if (granularity === "chapter") {
    return item.chapter_id ?? "chapter";
  }
  if (granularity === "beat") {
    return item.beat_id ?? item.scene_id ?? "beat";
  }
  return item.scene_id ?? "scene";
}

function toNumber(value: unknown): number {
  return typeof value === "number" ? value : Number.NaN;
}

function formatMetricValue(value: unknown): string {
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(3);
  }
  if (value === undefined || value === null) {
    return "n/a";
  }
  return String(value);
}

function formatLabel(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
