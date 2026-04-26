import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

interface Props {
  data: { date: string; value: number }[];
}

export default function EquityCurve({ data }: Props) {
  if (!data.length) {
    return <div className="text-gray-400 text-sm py-12 text-center">No equity data.</div>;
  }
  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11 }}
          tickFormatter={(d: string) => d.slice(5)}
          minTickGap={30}
        />
        <YAxis
          tick={{ fontSize: 11 }}
          tickFormatter={(v: number) =>
            `$${v >= 1000 ? (v / 1000).toFixed(1) + 'k' : v.toFixed(0)}`
          }
          width={60}
        />
        <Tooltip
          formatter={(v: number) => [`$${v.toLocaleString()}`, 'Portfolio']}
          labelStyle={{ fontSize: 11 }}
        />
        <Line
          type="monotone"
          dataKey="value"
          stroke="#2563eb"
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
