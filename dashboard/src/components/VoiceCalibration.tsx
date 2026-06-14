import { useEffect, useState } from "react";
import { getVoiceCalibration } from "../api/client";
import type { LedgerEvent, VoiceCalibrationResponse } from "../types";
import { eventTimestamp, fieldText } from "./historyUtils";
import { JsonBlock } from "./JsonBlock";

interface VoiceCalibrationProps {
  seriesId: string;
}

export function VoiceCalibration({ seriesId }: VoiceCalibrationProps) {
  const [calibration, setCalibration] = useState<VoiceCalibrationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    async function loadCalibration() {
      setIsLoading(true);
      setError(null);
      try {
        const response = await getVoiceCalibration(seriesId);
        if (!isCancelled) {
          setCalibration(response);
        }
      } catch (loadError) {
        if (!isCancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load voice calibration");
          setCalibration(null);
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadCalibration();
  }, [seriesId]);

  const history = calibration?.calibration_history ?? [];

  return (
    <section className="panel historical-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Author Voice</p>
          <h2>Voice Calibration</h2>
        </div>
        <span className="status-pill">{isLoading ? "Loading" : `${history.length} runs`}</span>
      </div>

      {error ? <p className="error">{error}</p> : null}

      <div className="metric-grid">
        <Metric label="Profile" value={calibration?.display_name ?? calibration?.profile_id ?? "not found"} />
        <Metric label="Version" value={calibration?.version ?? "n/a"} />
      </div>

      {calibration?.profile_path ? <p className="muted">Source: {calibration.profile_path}</p> : null}

      <ol className="event-list">
        {history.length > 0 ? (
          history.map((event, index) => <CalibrationRow event={event} key={`${eventTimestamp(event)}-${index}`} />)
        ) : (
          <li className="muted">
            {calibration?.profile_found
              ? "Voice profile found, but calibration_history is empty."
              : `No run-local voice profile found for ${seriesId}.`}
          </li>
        )}
      </ol>
    </section>
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

function CalibrationRow({ event }: { event: LedgerEvent }) {
  return (
    <li>
      <div className="event-row">
        <strong>{fieldText(event, "run_id", "Calibration run")}</strong>
        <span>{eventTimestamp(event)}</span>
      </div>
      <p className="muted">
        Distance {fieldText(event, "voice_fidelity_distance")} · Corpus {fieldText(event, "corpus_id")}
      </p>
      <details>
        <summary>Payload</summary>
        <JsonBlock value={event} />
      </details>
    </li>
  );
}
