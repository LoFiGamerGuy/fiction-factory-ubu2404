import { useEffect, useState } from "react";
import { getCharacterMetrics } from "../api/client";
import type { CharacterMetricsResponse } from "../types";

interface CharacterVoiceChartProps {
  bookId: string;
  characterIdsText: string;
}

const displayedMetrics = ["mtld", "question_rate", "sentiment_mean", "fk_grade"];

export function CharacterVoiceChart({ bookId, characterIdsText }: CharacterVoiceChartProps) {
  const [responses, setResponses] = useState<CharacterMetricsResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    async function loadCharacters() {
      const ids = characterIdsText
        .split(",")
        .map((id) => id.trim())
        .filter(Boolean);
      if (ids.length === 0) {
        setResponses([]);
        return;
      }

      setIsLoading(true);
      setError(null);
      try {
        const nextResponses = await Promise.all(ids.map((id) => getCharacterMetrics(bookId, id)));
        if (!isCancelled) {
          setResponses(nextResponses);
        }
      } catch (loadError) {
        if (!isCancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load character metrics");
          setResponses([]);
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadCharacters();

    return () => {
      isCancelled = true;
    };
  }, [bookId, characterIdsText]);

  return (
    <section className="panel historical-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Character Voice</p>
          <h2>Voice Comparison</h2>
        </div>
        <span className="status-pill">{isLoading ? "Loading" : `${responses.length} characters`}</span>
      </div>

      {error ? <p className="error">{error}</p> : null}

      <div className="voice-grid">
        {responses.length > 0 ? (
          responses.map((response) => (
            <article className="voice-card" key={response.character_id}>
              <h3>{response.character_id}</h3>
              <p className="muted">{response.items.length} scene sample(s)</p>
              {displayedMetrics.map((metric) => (
                <VoiceMetricRow key={metric} metric={metric} response={response} />
              ))}
            </article>
          ))
        ) : (
          <p className="muted">Enter character IDs to compare dialogue metrics.</p>
        )}
      </div>
    </section>
  );
}

function VoiceMetricRow({ metric, response }: { metric: string; response: CharacterMetricsResponse }) {
  const values = response.items
    .map((item) => item.metrics?.[metric])
    .filter((value): value is number => typeof value === "number");
  const average = values.length > 0 ? values.reduce((sum, value) => sum + value, 0) / values.length : null;

  return (
    <div className="voice-metric-row">
      <span>{formatLabel(metric)}</span>
      <strong>{average === null ? "n/a" : average.toFixed(3)}</strong>
      <MiniBars values={values} />
    </div>
  );
}

function MiniBars({ values }: { values: number[] }) {
  if (values.length === 0) {
    return <div className="mini-bars empty" />;
  }

  const max = Math.max(...values.map((value) => Math.abs(value))) || 1;
  return (
    <div className="mini-bars" aria-hidden="true">
      {values.slice(-12).map((value, index) => (
        <span key={`${value}-${index}`} style={{ height: `${Math.max(8, (Math.abs(value) / max) * 40)}px` }} />
      ))}
    </div>
  );
}

function formatLabel(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
