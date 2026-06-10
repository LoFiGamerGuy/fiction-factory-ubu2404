import { useEffect, useState } from "react";
import { getRunStatus } from "../api/client";
import type { RunStatus } from "../types";
import { JsonBlock } from "./JsonBlock";

interface RunMonitorProps {
  runId: string;
}

export function RunMonitor({ runId }: RunMonitorProps) {
  const [status, setStatus] = useState<RunStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    async function loadStatus() {
      setIsLoading(true);
      setError(null);
      try {
        const nextStatus = await getRunStatus(runId);
        if (!isCancelled) {
          setStatus(nextStatus);
        }
      } catch (loadError) {
        if (!isCancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load run status");
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadStatus();
    const interval = window.setInterval(() => void loadStatus(), 5_000);

    return () => {
      isCancelled = true;
      window.clearInterval(interval);
    };
  }, [runId]);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Live Run</p>
          <h2>Run Monitor</h2>
        </div>
        <span className="status-pill">{isLoading ? "Refreshing" : status?.status ?? "Unknown"}</span>
      </div>

      {error ? <p className="error">{error}</p> : null}

      <div className="metric-grid">
        <Metric label="Run" value={status?.run_id ?? runId} />
        <Metric label="Active Scene" value={status?.active_scene ?? "n/a"} />
        <Metric label="Agent" value={status?.current_agent ?? "n/a"} />
        <Metric label="Routing" value={status?.routing_decision ?? "n/a"} />
      </div>

      <div className="cost-row">
        <span>Cost vs budget</span>
        <strong>{formatBudget(status?.cost_usd, status?.budget_usd)}</strong>
      </div>

      <details>
        <summary>Raw status payload</summary>
        <JsonBlock value={status ?? undefined} />
      </details>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatBudget(cost: number | undefined, budget: number | undefined): string {
  if (cost === undefined && budget === undefined) {
    return "n/a";
  }
  const costText = cost === undefined ? "?" : `$${cost.toFixed(2)}`;
  const budgetText = budget === undefined ? "?" : `$${budget.toFixed(2)}`;
  return `${costText} / ${budgetText}`;
}
