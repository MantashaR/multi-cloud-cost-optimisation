import { useMemo, useState } from "react";

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
  const [providerFilter, setProviderFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");

  const providers = useMemo(() => Array.from(new Set(anomalies.map((a) => a.provider))), [anomalies]);

  const filtered = useMemo(
    () =>
      anomalies
        .filter((a) => providerFilter === "all" || a.provider === providerFilter)
        .filter((a) => severityFilter === "all" || a.severity === severityFilter),
    [anomalies, providerFilter, severityFilter]
  );

  if (!anomalies.length) {
    return <div className="empty-state">No anomalies detected. Run analysis after ingesting cost data.</div>;
  }

  return (
    <div>
      <div className="table-filters">
        {providers.length > 1 && (
          <label>
            Provider
            <select value={providerFilter} onChange={(e) => setProviderFilter(e.target.value)}>
              <option value="all">All</option>
              {providers.map((p) => (
                <option key={p} value={p}>{PROVIDER_LABEL[p] || p}</option>
              ))}
            </select>
          </label>
        )}
        <label>
          Severity
          <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)}>
            <option value="all">All</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </label>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Provider</th>
              <th>Service</th>
              <th>Actual vs. baseline</th>
              <th>Deviation</th>
              <th>Severity</th>
              <th>Why this was flagged</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((a) => (
              <tr key={a.id}>
                <td>{a.date}</td>
                <td><ProviderChip provider={a.provider} /></td>
                <td>{a.service}</td>
                <td>
                  ${Number(a.actual_amount).toFixed(2)}
                  <div className="stat-sub">baseline ${Number(a.expected_amount).toFixed(2)}</div>
                </td>
                <td>+{a.deviation_pct.toFixed(0)}%</td>
                <td><SeverityBadge severity={a.severity} /></td>
                <td className="reason-cell">{a.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
