const PROVIDER_LABEL = { aws: "AWS", azure: "Azure", gcp: "GCP" };

function fmtMoney(value) {
  return `$${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatMonth(monthStr) {
  const [year, month] = monthStr.split("-").map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

export default function KeyInsights({ data }) {
  const hasSpikes = data.monthly_cost_spikes?.length > 0;
  const hasRecommendations = data.recommendations?.length > 0;

  if (!hasSpikes && !hasRecommendations) {
    return (
      <div className="card key-insights empty-state">
        Click <strong>Run Analysis</strong> above to ingest cost data and generate insights.
      </div>
    );
  }

  const latestMonth = hasSpikes ? data.monthly_cost_spikes[0].month : null;
  const latestMonthSpikes = hasSpikes
    ? data.monthly_cost_spikes.filter((row) => row.month === latestMonth)
    : [];
  const latestMonthExcess = latestMonthSpikes.reduce((sum, row) => sum + row.total_excess_amount, 0);
  const topSpikeService = latestMonthSpikes[0];

  const topRecommendation = hasRecommendations ? data.recommendations[0] : null;

  return (
    <div className="card key-insights">
      <div className="section-title">Key insights</div>
      <ul>
        {hasSpikes && (
          <li>
            In <strong>{formatMonth(latestMonth)}</strong>, cost anomalies added an estimated{" "}
            <strong style={{ color: "var(--status-critical)" }}>{fmtMoney(latestMonthExcess)}</strong> in
            unexpected spend across {latestMonthSpikes.length} service{latestMonthSpikes.length === 1 ? "" : "s"}
            {topSpikeService && (
              <>
                {" "}
                &mdash; led by <strong>{topSpikeService.service}</strong> on{" "}
                <strong>{PROVIDER_LABEL[topSpikeService.provider] || topSpikeService.provider}</strong>, which
                alone accounts for {fmtMoney(topSpikeService.total_excess_amount)}.
              </>
            )}
          </li>
        )}
        {hasRecommendations && (
          <li>
            We found <strong>{data.recommendations.length}</strong> right-sizing opportunit
            {data.recommendations.length === 1 ? "y" : "ies"} worth{" "}
            <strong className="savings-highlight">
              {fmtMoney(data.total_potential_monthly_savings)}/month ({fmtMoney(data.total_potential_annual_savings)}/year)
            </strong>{" "}
            in potential savings.
            {topRecommendation && (
              <>
                {" "}
                The highest-impact one: {topRecommendation.action === "downsize" ? "downsize" : "decommission"}{" "}
                <strong>{topRecommendation.resource_id}</strong>
                {topRecommendation.action === "downsize" && (
                  <> ({topRecommendation.current_instance_type} &rarr; {topRecommendation.recommended_instance_type})</>
                )}
                , saving {fmtMoney(topRecommendation.estimated_monthly_savings)}/month on its own.
              </>
            )}
          </li>
        )}
      </ul>
    </div>
  );
}
