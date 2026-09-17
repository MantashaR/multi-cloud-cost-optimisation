import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const SERIES = [
  { key: "aws", label: "AWS", color: "var(--series-aws)" },
  { key: "azure", label: "Azure", color: "var(--series-azure)" },
  { key: "gcp", label: "GCP", color: "var(--series-gcp)" },
];

function fmtDate(d) {
  return new Date(d).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function CostTrendChart({ data }) {
  if (!data.length) {
    return <div className="empty-state">No cost data yet. Click "Run Analysis" to ingest data.</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="var(--gridline)" vertical={false} />
        <XAxis
          dataKey="date"
          tickFormatter={fmtDate}
          stroke="var(--baseline)"
          tick={{ fill: "var(--text-muted)", fontSize: 12 }}
          minTickGap={24}
        />
        <YAxis
          stroke="var(--baseline)"
          tick={{ fill: "var(--text-muted)", fontSize: 12 }}
          tickFormatter={(v) => `$${v}`}
          width={56}
        />
        <Tooltip
          labelFormatter={fmtDate}
          formatter={(value, name) => [`$${Number(value).toFixed(2)}`, name]}
          contentStyle={{ background: "var(--surface-1)", border: "1px solid var(--border)", fontSize: 12 }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {SERIES.map((s) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.label}
            stroke={s.color}
            strokeWidth={2}
            dot={false}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
