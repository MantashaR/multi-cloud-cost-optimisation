import { useEffect, useRef, useState } from "react";
import { getAnalysisRun, triggerAnalysis } from "../api";

export default function RunAnalysisButton({ onComplete, lastRun }) {
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState(null);
  const pollRef = useRef(null);

  useEffect(() => () => clearInterval(pollRef.current), []);

  const start = async () => {
    setRunning(true);
    setStatus("Starting pipeline...");
    const run = await triggerAnalysis();

    pollRef.current = setInterval(async () => {
      const latest = await getAnalysisRun(run.id);
      if (latest.status === "running") {
        setStatus("Ingesting costs, detecting anomalies, forecasting...");
        return;
      }
      clearInterval(pollRef.current);
      setRunning(false);
      setStatus(
        latest.status === "success"
          ? `Done: ${latest.records_ingested} records, ${latest.anomalies_found} anomalies, ${latest.recommendations_generated} recommendations.`
          : `Failed: ${latest.error_message}`
      );
      onComplete();
    }, 1500);
  };

  return (
    <div>
      <button className="primary" onClick={start} disabled={running}>
        {running ? "Running analysis..." : "Run Analysis"}
      </button>
      {status && <div className="run-status">{status}</div>}
      {!status && lastRun && (
        <div className="run-status">
          Last run: {new Date(lastRun.started_at).toLocaleString()} ({lastRun.status})
        </div>
      )}
    </div>
  );
}
