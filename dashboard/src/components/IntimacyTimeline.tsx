import { useEffect, useState } from "react";
import { getBookIntimacy } from "../api/client";
import type { LedgerEvent } from "../types";
import { eventTimestamp, fieldText } from "./historyUtils";
import { JsonBlock } from "./JsonBlock";

interface IntimacyTimelineProps {
  bookId: string;
}

export function IntimacyTimeline({ bookId }: IntimacyTimelineProps) {
  const [events, setEvents] = useState<LedgerEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    async function loadTimeline() {
      setIsLoading(true);
      setError(null);
      try {
        const response = await getBookIntimacy(bookId);
        if (!isCancelled) {
          setEvents(response.events);
        }
      } catch (loadError) {
        if (!isCancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load intimacy timeline");
          setEvents([]);
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadTimeline();
  }, [bookId]);

  return (
    <section className="panel historical-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Heat Arc</p>
          <h2>Intimacy Timeline</h2>
        </div>
        <span className="status-pill">{isLoading ? "Loading" : `${events.length} events`}</span>
      </div>

      {error ? <p className="error">{error}</p> : null}

      <ol className="event-list">
        {events.length > 0 ? (
          events.map((event, index) => <IntimacyRow event={event} key={`${fieldText(event, "event_id", "event")}-${index}`} />)
        ) : (
          <li className="muted">No intimacy escalation events loaded for {bookId}.</li>
        )}
      </ol>
    </section>
  );
}

function IntimacyRow({ event }: { event: LedgerEvent }) {
  return (
    <li>
      <div className="event-row">
        <strong>{fieldText(event, "event_type", "event")}</strong>
        <span>{fieldText(event, "pair_id")}</span>
      </div>
      <p>{fieldText(event, "description", "No description recorded.")}</p>
      <p className="muted">
        {fieldText(event, "heat_level")} · chapter {fieldText(event, "chapter_number")} · {fieldText(event, "scene_id")} · {eventTimestamp(event)}
      </p>
      <details>
        <summary>Payload</summary>
        <JsonBlock value={event} />
      </details>
    </li>
  );
}
