import { useState } from "react";
import { CharacterVoiceChart } from "./components/CharacterVoiceChart";
import { LedgerDashboard } from "./components/LedgerDashboard";
import { MetricPlotter } from "./components/MetricPlotter";
import { QualityFeed } from "./components/QualityFeed";
import { RunMonitor } from "./components/RunMonitor";

export default function App() {
  const [runId, setRunId] = useState("default");
  const [bookId, setBookId] = useState("default");
  const [characterIdsText, setCharacterIdsText] = useState("sarah,miles");

  return (
    <main>
      <header className="hero">
        <div>
          <p className="eyebrow">Phase 13 Bootstrap</p>
          <h1>Fiction-Factory Author Dashboard</h1>
          <p>
            Minimal live view for run status, ledger snapshots, and quality gate events from the FastAPI backend.
          </p>
        </div>
      </header>

      <section className="controls" aria-label="Dashboard selectors">
        <label>
          Run ID
          <input value={runId} onChange={(event) => setRunId(event.target.value)} />
        </label>
        <label>
          Book ID
          <input value={bookId} onChange={(event) => setBookId(event.target.value)} />
        </label>
        <label>
          Character IDs
          <input value={characterIdsText} onChange={(event) => setCharacterIdsText(event.target.value)} />
        </label>
      </section>

      <section className="dashboard-grid">
        <RunMonitor runId={runId} />
        <QualityFeed bookId={bookId} runId={runId} />
        <LedgerDashboard bookId={bookId} />
        <MetricPlotter bookId={bookId} />
        <CharacterVoiceChart bookId={bookId} characterIdsText={characterIdsText} />
      </section>
    </main>
  );
}
