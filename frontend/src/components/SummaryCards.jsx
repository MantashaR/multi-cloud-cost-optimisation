const PROVIDER_LABEL = { aws: "AWS", azure: "Azure", gcp: "GCP" };

function fmtMoney(value) {
  return `$${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export default function SummaryCards({ data }) {
  const topProvider = data.spend_by_provider?.[0];

  const tiles = [
    {
      label: "Total spend (30d)",
      value: fmtMoney(data.total_spend_30d),
      sub: `Across ${data.account_count} connected accounts`,
    },
    {
      label: "Potential monthly savings",
      value: fmtMoney(data.total_potential_monthly_savings),
      sub: `${data.recommendations?.length || 0} open right-sizing recommendations`,
      highlight: true,
    },
    {
      label: "Open anomalies",
      value: data.anomalies?.length || 0,
      sub: "Flagged by Isolation Forest",
    },
    {
      label: "Top spender",
      value: topProvider ? PROVIDER_LABEL[topProvider.provider] : "-",
      sub: topProvider ? fmtMoney(topProvider.total) + " last 30d" : "No data yet",
    },
  ];

  return (
    <div className="summary-grid">
      {tiles.map((t) => (
        <div className="card stat-tile" key={t.label}>
          <div className="stat-label">{t.label}</div>
          <div className={"stat-value" + (t.highlight ? " savings-highlight" : "")}>{t.value}</div>
          <div className="stat-sub">{t.sub}</div>
        </div>
      ))}
    </div>
  );
}
