import { useEffect, useMemo, useState } from "react";
import { getBookPromises } from "../api/client";
import type { LedgerEvent, PromiseGroups } from "../types";
import { eventTimestamp, fieldText, latestByGroup } from "./historyUtils";
import { JsonBlock } from "./JsonBlock";

interface PromiseLedgerProps {
  bookId: string;
}

export function PromiseLedger({ bookId }: PromiseLedgerProps) {
  const [groups, setGroups] = useState<PromiseGroups>({});
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    async function loadPromises() {
      setIsLoading(true);
      setError(null);
      try {
        const response = await getBookPromises(bookId);
        if (!isCancelled) {
          setGroups(response.promises);
        }
      } catch (loadError) {
        if (!isCancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load promises");
          setGroups({});
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadPromises();
  }, [bookId]);

  const latestEvents = useMemo(() => latestByGroup(groups), [groups]);
  const openCount = latestEvents.filter((event) => !["resolved", "force_resolved"].includes(fieldText(event, "event_type"))).length;

  return (
    <section className="panel historical-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Narrative Promises</p>
          <h2>Promise Ledger</h2>
        </div>
        <span className="status-pill">{isLoading ? "Loading" : `${openCount} open`}</span>
      </div>

      {error ? <p className="error">{error}</p> : null}

      <ol className="event-list">
        {latestEvents.length > 0 ? (
          latestEvents.map((event, index) => <PromiseRow event={event} key={`${fieldText(event, "promise_id")}-${index}`} />)
        ) : (
          <li className="muted">No book-level promise events loaded for {bookId}.</li>
        )}
      </ol>
    </section>
  );
}

function PromiseRow({ event }: { event: LedgerEvent }) {
  return (
    <li>
      <div className="event-row">
        <strong>{fieldText(event, "description", fieldText(event, "promise_id", "Promise"))}</strong>
        <span>{fieldText(event, "event_type")}</span>
      </div>
      <p className="muted">
        {fieldText(event, "promise_type")} · {fieldText(event, "priority")} · {fieldText(event, "scene_id")} · {eventTimestamp(event)}
      </p>
      <details>
        <summary>Payload</summary>
        <JsonBlock value={event} />
      </details>
    </li>
  );
}
