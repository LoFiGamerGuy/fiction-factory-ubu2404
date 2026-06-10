import { useEffect, useMemo, useState } from "react";
import { getLedgers } from "../api/client";
import type { JsonValue, LedgerSnapshot } from "../types";
import { JsonBlock } from "./JsonBlock";

interface LedgerDashboardProps {
  bookId: string;
}

const preferredLedgerOrder = [
  "book_metrics",
  "promise_ledger",
  "bible_tracker",
  "character_arc",
  "intimacy_escalation",
  "reader_information_state",
  "scene_rhythm",
  "subplot_ledger",
  "trope_commitment",
  "series_promise"
];

export function LedgerDashboard({ bookId }: LedgerDashboardProps) {
  const [snapshot, setSnapshot] = useState<LedgerSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    async function loadLedgers() {
      setIsLoading(true);
      setError(null);
      try {
        const nextSnapshot = await getLedgers(bookId);
        if (!isCancelled) {
          setSnapshot(nextSnapshot);
        }
      } catch (loadError) {
        if (!isCancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load ledgers");
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadLedgers();
    const interval = window.setInterval(() => void loadLedgers(), 10_000);

    return () => {
      isCancelled = true;
      window.clearInterval(interval);
    };
  }, [bookId]);

  const ledgerEntries = useMemo(() => getLedgerEntries(snapshot), [snapshot]);

  return (
    <section className="panel ledger-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Book State</p>
          <h2>Ledger Dashboard</h2>
        </div>
        <span className="status-pill">{isLoading ? "Refreshing" : `${ledgerEntries.length} ledgers`}</span>
      </div>

      {error ? <p className="error">{error}</p> : null}

      <div className="ledger-grid">
        {ledgerEntries.length > 0 ? (
          ledgerEntries.map(([key, value]) => (
            <article className="ledger-card" key={key}>
              <h3>{formatTitle(key)}</h3>
              <JsonBlock value={value} />
            </article>
          ))
        ) : (
          <p className="muted">No ledger snapshot loaded for {bookId}.</p>
        )}
      </div>
    </section>
  );
}

function getLedgerEntries(snapshot: LedgerSnapshot | null): [string, JsonValue | undefined][] {
  if (!snapshot) {
    return [];
  }

  const known = preferredLedgerOrder
    .filter((key) => key in snapshot)
    .map((key): [string, JsonValue | undefined] => [key, snapshot[key]]);
  const knownKeys = new Set(preferredLedgerOrder);
  const extra = Object.entries(snapshot).filter(([key]) => !knownKeys.has(key) && key !== "book_id" && key !== "scene_id");

  return [...known, ...extra];
}

function formatTitle(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
