import { useCallback, useEffect, useState } from "react";
import { dismissRecommendation, getDashboard } from "./api";
import AnomalyTable from "./components/AnomalyTable";
import CostTrendChart from "./components/CostTrendChart";
import ForecastChart from "./components/ForecastChart";
import RecommendationsTable from "./components/RecommendationsTable";
import RunAnalysisButton from "./components/RunAnalysisButton";
import SummaryCards from "./components/SummaryCards";

export default function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const result = await getDashboard();
      setData(result);
      setError(null);
    } catch (e) {
      setError("Could not reach the backend API. Is docker compose up and the backend healthy?");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleDismiss = async (id) => {
    await dismissRecommendation(id);
    refresh();
  };

  return (
    <div className="app">
      <div className="app-header">
        <div>
          <h1>Multi-Cloud Cost Optimisation &amp; Anomaly Detection</h1>
          <p>AWS &middot; Azure &middot; GCP unified FinOps intelligence layer</p>
        </div>
        <RunAnalysisButton onComplete={refresh} lastRun={data?.last_analysis_run} />
      </div>

      {error && <div className="card empty-state">{error}</div>}

      {data && (
        <>
          <SummaryCards data={data} />

          <div className="grid-2">
            <div className="card section">
              <div className="section-title">Daily spend by provider (60d)</div>
              <CostTrendChart data={data.daily_trend} />
            </div>
            <div className="card section">
              <div className="section-title">Cost forecast (Prophet)</div>
              <ForecastChart trend={data.daily_trend} forecast={data.forecast_series} />
            </div>
          </div>

          <div className="card section">
            <div className="section-title">Cost anomalies</div>
            <AnomalyTable anomalies={data.anomalies} />
          </div>

          <div className="card section">
            <div className="section-title">Right-sizing recommendations</div>
            <RecommendationsTable recommendations={data.recommendations} onDismiss={handleDismiss} />
          </div>
        </>
      )}
    </div>
  );
}
