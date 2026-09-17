const PROVIDER_LABEL = { aws: "AWS", azure: "Azure", gcp: "GCP" };

function ProviderChip({ provider }) {
  return (
    <span className="provider-chip">
      <span className={`provider-dot dot-${provider}`} />
      {PROVIDER_LABEL[provider] || provider}
    </span>
  );
}

function SeverityBadge({ severity }) {
  return (
    <span className={`badge badge-${severity}`}>
      <span className="badge-dot" style={{ background: "currentColor" }} />
      {severity[0].toUpperCase() + severity.slice(1)}
    </span>
  );
}

function formatMonth(monthStr) {
  const [year, month] = monthStr.split("-").map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

export default function MonthlyCostSpikesTable({ data }) {
  if (!data.length) {
    return <div className="empty-state">No cost spikes recorded yet -- run analysis to detect anomalies first.</div>;
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Month</th>
            <th>Provider</th>
            <th>Service</th>
            <th># Spike days</th>
            <th>Extra spend caused</th>
            <th>Worst severity</th>
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr key={`${row.month}-${row.provider}-${row.service}`}>
              <td>{formatMonth(row.month)}</td>
              <td><ProviderChip provider={row.provider} /></td>
              <td>{row.service}</td>
              <td>{row.spike_count}</td>
              <td className="savings-highlight" style={{ color: "var(--status-critical)" }}>
                +${Number(row.total_excess_amount).toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </td>
              <td><SeverityBadge severity={row.worst_severity} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
