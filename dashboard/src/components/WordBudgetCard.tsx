import { useEffect, useMemo, useState } from "react";
import { getBookRunSummary } from "../api/client";
import type { BookRunSummary, WordBudgetSceneTrace, WordBudgetStatus } from "../types";

interface WordBudgetCardProps {
  bookId: string;
}

export function WordBudgetCard({ bookId }: WordBudgetCardProps) {
  const [summary, setSummary] = useState<BookRunSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    async function loadSummary() {
      setIsLoading(true);
      setError(null);
      try {
        const nextSummary = await getBookRunSummary(bookId);
        if (!isCancelled) {
          setSummary(nextSummary);
        }
      } catch (loadError) {
        if (!isCancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load book summary");
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadSummary();
    const interval = window.setInterval(() => void loadSummary(), 10_000);

    return () => {
      isCancelled = true;
      window.clearInterval(interval);
    };
  }, [bookId]);

  const budget = summary?.word_budget_status;
  const latestScene = useMemo(() => latestTrace(budget), [budget]);
  const sceneCountText = budget?.enabled
    ? `${budget.completed_scene_count ?? 0}/${budget.scene_count ?? 0} scenes`
    : "Pending";

  return (
    <section className="panel word-budget-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Book Budget</p>
          <h2>Word Budget</h2>
        </div>
        <span className="status-pill">{isLoading ? "Refreshing" : sceneCountText}</span>
      </div>

      {error ? <p className="error">{error}</p> : null}

      <div className="metric-grid">
        <Metric label="Book Target" value={formatNumber(budget?.book_word_count_target)} />
        <Metric label="Planned Scene Total" value={formatNumber(budget?.planned_word_count_target)} />
        <Metric label="Actual Words" value={formatNumber(budget?.actual_word_count)} />
        <Metric label="Remaining Budget" value={formatNumber(budget?.remaining_word_budget)} />
        <Metric label="Projected Final" value={formatNumber(budget?.projected_final_count)} />
        <Metric label="Min Scene Target" value={formatNumber(budget?.min_scene_target)} />
      </div>

      <div className="cost-row">
        <span>Latest adjusted scene target</span>
        <strong>{formatNumber(latestScene?.adjusted_word_count_target)}</strong>
      </div>

      {budget?.enabled ? (
        <BudgetTrace scenes={budget.scenes ?? []} />
      ) : (
        <p className="muted">
          No word-budget summary found for {bookId}. The card will populate after the book
          runner writes `book_run_summary.json`.
        </p>
      )}
    </section>
  );
}

function BudgetTrace({ scenes }: { scenes: WordBudgetSceneTrace[] }) {
  if (scenes.length === 0) {
    return <p className="muted">No per-scene budget trace rows yet.</p>;
  }

  return (
    <div className="budget-trace" role="table" aria-label="Per-scene word budget trace">
      <div className="budget-trace-row budget-trace-header" role="row">
        <span>Scene</span>
        <span>Planned</span>
        <span>Adjusted</span>
        <span>Actual</span>
        <span>Projection After</span>
      </div>
      {scenes.map((scene, index) => (
        <div className="budget-trace-row" key={`${scene.scene_id ?? "scene"}-${index}`} role="row">
          <span>{scene.scene_id ?? `Scene ${scene.scene_index ?? index + 1}`}</span>
          <strong>{formatNumber(scene.planned_word_count_target)}</strong>
          <strong>{formatNumber(scene.adjusted_word_count_target)}</strong>
          <strong>{formatNumber(scene.actual_word_count)}</strong>
          <strong>{formatNumber(scene.projected_final_count_after)}</strong>
        </div>
      ))}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function latestTrace(budget: WordBudgetStatus | undefined): WordBudgetSceneTrace | undefined {
  const scenes = budget?.scenes ?? [];
  return scenes.length > 0 ? scenes[scenes.length - 1] : undefined;
}

function formatNumber(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) {
    return "n/a";
  }
  return new Intl.NumberFormat().format(value);
}
