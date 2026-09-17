const PROVIDER_LABEL = { aws: "AWS", azure: "Azure", gcp: "GCP" };

function SeverityBadge({ severity }) {
  return (
    <span className={`badge badge-${severity}`}>
      <span className="badge-dot" style={{ background: "currentColor" }} />
      {severity[0].toUpperCase() + severity.slice(1)}
    </span>
  );
}

function ProviderChip({ provider }) {
  return (
    <span className="provider-chip">
      <span className={`provider-dot dot-${provider}`} />
      {PROVIDER_LABEL[provider] || provider}
    </span>
  );
}

export default function AnomalyTable({ anomalies }) {
  if (!anomalies.length) {
    return <div className="empty-state">No anomalies detected. Run analysis after ingesting cost data.</div>;
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Provider</th>
            <th>Service</th>
            <th>Actual</th>
            <th>Expected</th>
            <th>Deviation</th>
            <th>Severity</th>
          </tr>
        </thead>
        <tbody>
          {anomalies.map((a) => (
            <tr key={a.id}>
              <td>{a.date}</td>
              <td><ProviderChip provider={a.provider} /></td>
              <td>{a.service}</td>
              <td>${Number(a.actual_amount).toFixed(2)}</td>
              <td>${Number(a.expected_amount).toFixed(2)}</td>
              <td>+{a.deviation_pct.toFixed(0)}%</td>
              <td><SeverityBadge severity={a.severity} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
