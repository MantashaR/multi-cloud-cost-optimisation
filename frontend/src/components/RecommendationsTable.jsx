import { useMemo, useState } from "react";
import { terraformDownloadUrl } from "../api";

const PROVIDER_LABEL = { aws: "AWS", azure: "Azure", gcp: "GCP" };

function ProviderChip({ provider }) {
  return (
    <span className="provider-chip">
      <span className={`provider-dot dot-${provider}`} />
      {PROVIDER_LABEL[provider] || provider}
    </span>
  );
}

function PriorityBadge({ priority }) {
  return (
    <span className={`badge badge-${priority}`}>
      <span className="badge-dot" style={{ background: "currentColor" }} />
      {priority[0].toUpperCase() + priority.slice(1)}
    </span>
  );
}

export default function RecommendationsTable({ recommendations, onUpdateStatus }) {
  const [providerFilter, setProviderFilter] = useState("all");

  const providers = useMemo(
    () => Array.from(new Set(recommendations.map((r) => r.provider))),
    [recommendations]
  );

  const filtered = useMemo(
    () =>
      providerFilter === "all"
        ? recommendations
        : recommendations.filter((r) => r.provider === providerFilter),
    [recommendations, providerFilter]
  );

  if (!recommendations.length) {
    return <div className="empty-state">No right-sizing recommendations yet. Run analysis to generate some.</div>;
  }

  return (
    <div>
      {providers.length > 1 && (
        <div className="table-filters">
          <label>
            Provider
            <select value={providerFilter} onChange={(e) => setProviderFilter(e.target.value)}>
              <option value="all">All</option>
              {providers.map((p) => (
                <option key={p} value={p}>{PROVIDER_LABEL[p] || p}</option>
              ))}
            </select>
          </label>
        </div>
      )}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Priority</th>
              <th>Provider</th>
              <th>Resource</th>
              <th>Action</th>
              <th>Utilisation (before &rarr; after)</th>
              <th>Est. savings</th>
              <th>Why this was recommended</th>
              <th>Terraform</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr key={r.id}>
                <td><PriorityBadge priority={r.priority} /></td>
                <td><ProviderChip provider={r.provider} /></td>
                <td>
                  {r.resource_id}
                  {r.action === "downsize" && (
                    <div className="stat-sub">{r.current_instance_type} &rarr; {r.recommended_instance_type}</div>
                  )}
                </td>
                <td>{r.action === "downsize" ? "Downsize" : "Terminate (idle)"}</td>
                <td>
                  {r.avg_utilization_pct?.toFixed(0)}%
                  {r.action === "downsize" && r.projected_utilization_pct != null && (
                    <> &rarr; ~{r.projected_utilization_pct.toFixed(0)}%</>
                  )}
                </td>
                <td>
                  <div className="savings-highlight">${Number(r.estimated_monthly_savings).toLocaleString()}/mo</div>
                  <div className="stat-sub">${Number(r.estimated_annual_savings).toLocaleString()}/yr</div>
                </td>
                <td className="reason-cell">{r.rationale}</td>
                <td>
                  <a href={terraformDownloadUrl(r.id)} target="_blank" rel="noreferrer">
                    {r.terraform_file_path.split("/").pop()}
                  </a>
                </td>
                <td>
                  <button className="link" onClick={() => onUpdateStatus(r.id, "applied")}>Apply</button>
                  {" · "}
                  <button className="link" onClick={() => onUpdateStatus(r.id, "dismissed")}>Dismiss</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
