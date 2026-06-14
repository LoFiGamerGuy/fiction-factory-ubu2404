import { useState } from "react";
import { CharacterVoiceChart } from "./components/CharacterVoiceChart";
import { IntimacyTimeline } from "./components/IntimacyTimeline";
import { LedgerDashboard } from "./components/LedgerDashboard";
import { MetricPlotter } from "./components/MetricPlotter";
import { PromiseLedger } from "./components/PromiseLedger";
import { QualityFeed } from "./components/QualityFeed";
import { RunMonitor } from "./components/RunMonitor";
import { SeriesTimeline } from "./components/SeriesTimeline";
import { SkillLibrary } from "./components/SkillLibrary";
import { VoiceCalibration } from "./components/VoiceCalibration";
import { WordBudgetCard } from "./components/WordBudgetCard";

const defaultRunId = import.meta.env.VITE_DEFAULT_RUN_ID ?? "default";
const defaultBookId = import.meta.env.VITE_DEFAULT_BOOK_ID ?? "default";
const defaultSeriesId = import.meta.env.VITE_DEFAULT_SERIES_ID ?? "default";
const defaultCharacterIds = import.meta.env.VITE_DEFAULT_CHARACTER_IDS ?? "sarah,miles";

export default function App() {
  const [runId, setRunId] = useState(defaultRunId);
  const [bookId, setBookId] = useState(defaultBookId);
  const [seriesId, setSeriesId] = useState(defaultSeriesId);
  const [characterIdsText, setCharacterIdsText] = useState(defaultCharacterIds);

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
          Series ID
          <input value={seriesId} onChange={(event) => setSeriesId(event.target.value)} />
        </label>
        <label>
          Character IDs
          <input value={characterIdsText} onChange={(event) => setCharacterIdsText(event.target.value)} />
        </label>
      </section>

      <section className="dashboard-grid">
        <RunMonitor runId={runId} />
        <WordBudgetCard bookId={bookId} />
        <QualityFeed bookId={bookId} runId={runId} />
        <LedgerDashboard bookId={bookId} />
        <MetricPlotter bookId={bookId} />
        <CharacterVoiceChart bookId={bookId} characterIdsText={characterIdsText} />
        <PromiseLedger bookId={bookId} />
        <IntimacyTimeline bookId={bookId} />
        <SeriesTimeline seriesId={seriesId} />
        <SkillLibrary seriesId={seriesId} />
        <VoiceCalibration seriesId={seriesId} />
      </section>
    </main>
  );
}
