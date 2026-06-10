import { useEffect, useState } from "react";
import { getQualityGates, openRunEventStream } from "../api/client";
import type { QualityGateEvent } from "../types";
import { JsonBlock } from "./JsonBlock";

interface QualityFeedProps {
  bookId: string;
  runId: string;
}

export function QualityFeed({ bookId, runId }: QualityFeedProps) {
  const [events, setEvents] = useState<QualityGateEvent[]>([]);
  const [connectionState, setConnectionState] = useState("Connecting");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isCancelled = false;

    async function loadHistory() {
      try {
        const history = await getQualityGates(bookId);
        if (!isCancelled) {
          setEvents(history.slice(-20).reverse());
        }
      } catch (loadError) {
        if (!isCancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load quality gate history");
        }
      }
    }

    void loadHistory();

    return () => {
      isCancelled = true;
    };
  }, [bookId]);

  useEffect(() => {
    setConnectionState("Connecting");
    const source = openRunEventStream(
      runId,
      (event) => {
        setConnectionState("Live");
        setEvents((current) => [event, ...current].slice(0, 20));
      },
      () => setConnectionState("Disconnected")
    );

    source.onopen = () => setConnectionState("Live");

    return () => {
      source.close();
      setConnectionState("Closed");
    };
  }, [runId]);

  return (
    <section className="panel feed-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Quality Gate</p>
          <h2>Quality Feed</h2>
        </div>
        <span className="status-pill">{connectionState}</span>
      </div>

      {error ? <p className="error">{error}</p> : null}

      <ol className="event-list">
        {events.length > 0 ? (
          events.map((event, index) => (
            <li key={`${event.created_at ?? "event"}-${event.scene_id ?? index}-${index}`}>
              <div className="event-row">
                <strong>{event.decision ?? event.routing_decision ?? event.event ?? "update"}</strong>
                <span>{event.scene_id ?? event.agent ?? "pipeline"}</span>
              </div>
              {event.message ? <p>{event.message}</p> : null}
              <details>
                <summary>Payload</summary>
                <JsonBlock value={event} />
              </details>
            </li>
          ))
        ) : (
          <li className="muted">Waiting for quality gate events.</li>
        )}
      </ol>
    </section>
  );
}
