import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

const PROVIDER_LABEL = { aws: "AWS", azure: "Azure", gcp: "GCP" };
const PROVIDER_COLOR = {
  aws: "var(--series-aws)",
  azure: "var(--series-azure)",
  gcp: "var(--series-gcp)",
};

export default function SpendByProviderChart({ data }) {
  if (!data.length) {
    return <div className="empty-state">No spend data yet.</div>;
  }

  const chartData = data.map((row) => ({
    name: PROVIDER_LABEL[row.provider] || row.provider,
    provider: row.provider,
    value: row.total,
  }));
  const total = chartData.reduce((sum, row) => sum + row.value, 0);

  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={chartData}
          dataKey="value"
          nameKey="name"
          innerRadius={55}
          outerRadius={80}
          paddingAngle={2}
          stroke="var(--surface-1)"
          strokeWidth={2}
        >
          {chartData.map((row) => (
            <Cell key={row.provider} fill={PROVIDER_COLOR[row.provider] || "var(--text-muted)"} />
          ))}
        </Pie>
        <Tooltip
          formatter={(value, name) => [
            `$${Number(value).toFixed(2)} (${((value / total) * 100).toFixed(0)}%)`,
            name,
          ]}
          contentStyle={{ background: "var(--surface-1)", border: "1px solid var(--border)", fontSize: 12 }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
      </PieChart>
    </ResponsiveContainer>
  );
}
