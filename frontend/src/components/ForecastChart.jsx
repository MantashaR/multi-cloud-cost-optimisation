import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function fmtDate(d) {
  return new Date(d).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function ForecastChart({ trend, forecast }) {
  const actual = trend.map((row) => ({
    date: row.date,
    actual: (row.aws || 0) + (row.azure || 0) + (row.gcp || 0),
  }));

  const merged = [
    ...actual.map((r) => ({ ...r, range: undefined, predicted: undefined })),
    ...forecast.map((r) => ({
      date: r.date,
      predicted: r.predicted,
      range: [r.lower, r.upper],
    })),
  ];

  if (!merged.length) {
    return <div className="empty-state">No forecast yet. Run analysis to generate one.</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <ComposedChart data={merged} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
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
          formatter={(value, name) => {
            if (name === "range" && Array.isArray(value)) {
              return [`$${value[0].toFixed(0)} - $${value[1].toFixed(0)}`, "Confidence band"];
            }
            return [`$${Number(value).toFixed(2)}`, name];
          }}
          contentStyle={{ background: "var(--surface-1)", border: "1px solid var(--border)", fontSize: 12 }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Area
          type="monotone"
          dataKey="range"
          name="Confidence band"
          stroke="none"
          fill="var(--series-forecast)"
          fillOpacity={0.15}
        />
        <Line type="monotone" dataKey="actual" name="Actual" stroke="var(--series-aws)" strokeWidth={2} dot={false} />
        <Line
          type="monotone"
          dataKey="predicted"
          name="Forecast"
          stroke="var(--series-forecast)"
          strokeWidth={2}
          strokeDasharray="4 3"
          dot={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
