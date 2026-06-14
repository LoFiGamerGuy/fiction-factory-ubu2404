import { useEffect, useMemo, useState } from "react";
import { getSeriesPromises } from "../api/client";
import type { LedgerEvent, PromiseGroups } from "../types";
import { eventTimestamp, fieldText, flattenPromiseGroups } from "./historyUtils";
import { JsonBlock } from "./JsonBlock";

interface SeriesTimelineProps {
  seriesId: string;
}

export function SeriesTimeline({ seriesId }: SeriesTimelineProps) {
  const [groups, setGroups] = useState<PromiseGroups>({});
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    async function loadSeriesPromises() {
      setIsLoading(true);
      setError(null);
      try {
        const response = await getSeriesPromises(seriesId);
        if (!isCancelled) {
          setGroups(response);
        }
      } catch (loadError) {
        if (!isCancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load series promises");
          setGroups({});
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadSeriesPromises();
  }, [seriesId]);

  const events = useMemo(() => sortSeriesEvents(flattenPromiseGroups(groups)), [groups]);

  return (
    <section className="panel historical-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Series Arc</p>
          <h2>Series Timeline</h2>
        </div>
        <span className="status-pill">{isLoading ? "Loading" : `${events.length} events`}</span>
      </div>

      {error ? <p className="error">{error}</p> : null}

      <ol className="event-list">
        {events.length > 0 ? (
          events.map((event, index) => <SeriesEventRow event={event} key={`${fieldText(event, "event_id", "event")}-${index}`} />)
        ) : (
          <li className="muted">No series promise events loaded for {seriesId}.</li>
        )}
      </ol>
    </section>
  );
}

function SeriesEventRow({ event }: { event: LedgerEvent }) {
  return (
    <li>
      <div className="event-row">
        <strong>{fieldText(event, "description", fieldText(event, "promise_id", "Series promise"))}</strong>
        <span>{fieldText(event, "status", fieldText(event, "event_type"))}</span>
      </div>
      <p className="muted">
        Book {fieldText(event, "book_number")} · {fieldText(event, "book_id")} · {fieldText(event, "scene_id")} · {eventTimestamp(event)}
      </p>
      <details>
        <summary>Payload</summary>
        <JsonBlock value={event} />
      </details>
    </li>
  );
}

function sortSeriesEvents(events: LedgerEvent[]): LedgerEvent[] {
  return [...events].sort((left, right) => {
    const leftBook = Number(left.book_number ?? 0);
    const rightBook = Number(right.book_number ?? 0);
    if (leftBook !== rightBook) {
      return leftBook - rightBook;
    }
    return fieldText(left, "timestamp").localeCompare(fieldText(right, "timestamp"));
  });
}
