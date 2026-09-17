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

export default function RecommendationsTable({ recommendations, onDismiss }) {
  if (!recommendations.length) {
    return <div className="empty-state">No right-sizing recommendations yet. Run analysis to generate some.</div>;
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Provider</th>
            <th>Resource</th>
            <th>Action</th>
            <th>Utilisation</th>
            <th>Est. savings / mo</th>
            <th>Terraform</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {recommendations.map((r) => (
            <tr key={r.id}>
              <td><ProviderChip provider={r.provider} /></td>
              <td>
                {r.resource_id}
                {r.action === "downsize" && (
                  <div className="stat-sub">{r.current_instance_type} &rarr; {r.recommended_instance_type}</div>
                )}
              </td>
              <td>{r.action === "downsize" ? "Downsize" : "Terminate (idle)"}</td>
              <td>{r.avg_utilization_pct?.toFixed(0)}%</td>
              <td className="savings-highlight">${Number(r.estimated_monthly_savings).toLocaleString()}</td>
              <td>
                <a href={terraformDownloadUrl(r.id)} target="_blank" rel="noreferrer">
                  {r.terraform_file_path.split("/").pop()}
                </a>
              </td>
              <td>
                <button className="link" onClick={() => onDismiss(r.id)}>Dismiss</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
