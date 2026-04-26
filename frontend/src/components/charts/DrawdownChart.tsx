import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

interface Props {
  data: { date: string; value: number }[];
}

export default function DrawdownChart({ data }: Props) {
  if (!data.length) return null;

  let peak = data[0].value;
  const ddData = data.map((d) => {
    peak = Math.max(peak, d.value);
    const dd = peak > 0 ? ((d.value - peak) / peak) * 100 : 0;
    return { date: d.date, drawdown: Math.round(dd * 100) / 100 };
  });

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={ddData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11 }}
          tickFormatter={(d: string) => d.slice(5)}
          minTickGap={30}
        />
        <YAxis
          tick={{ fontSize: 11 }}
          tickFormatter={(v: number) => `${v}%`}
          width={50}
        />
        <Tooltip formatter={(v: number) => [`${v}%`, 'Drawdown']} />
        <Area
          type="monotone"
          dataKey="drawdown"
          stroke="#dc2626"
          fill="#fee2e2"
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
