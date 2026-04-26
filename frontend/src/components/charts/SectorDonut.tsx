import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

const COLORS = [
  '#2563eb',
  '#7c3aed',
  '#059669',
  '#d97706',
  '#dc2626',
  '#0891b2',
  '#be185d',
  '#65a30d',
  '#6b7280',
];

interface Props {
  data: Record<string, number>;
}

export default function SectorDonut({ data }: Props) {
  const chartData = Object.entries(data)
    .map(([name, value]) => ({ name, value: Math.round(value * 1000) / 10 }))
    .filter((d) => d.value > 0)
    .sort((a, b) => b.value - a.value);

  if (!chartData.length) {
    return (
      <div className="text-gray-400 text-sm py-12 text-center">No sector data.</div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={100}
          dataKey="value"
          paddingAngle={1}
          isAnimationActive={false}
        >
          {chartData.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
        <Legend
          layout="vertical"
          align="right"
          verticalAlign="middle"
          wrapperStyle={{ fontSize: 12 }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
