import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ZAxis,
} from 'recharts';

const COLORS = ['#2563eb', '#7c3aed', '#059669', '#d97706', '#dc2626'];

interface ScatterPoint {
  x: number;
  y: number;
  cluster_id: number;
  ticker: string;
  return_pct: number;
  holding_days: number;
}

interface Props {
  data: ScatterPoint[];
  nClusters: number;
  labels?: string[];
}

export default function ClusterScatter({ data, nClusters, labels }: Props) {
  if (!data.length) return null;
  const groups = Array.from({ length: nClusters }, (_, i) =>
    data.filter((d) => d.cluster_id === i),
  );

  return (
    <ResponsiveContainer width="100%" height={360}>
      <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis
          dataKey="x"
          name="PC1"
          tick={{ fontSize: 11 }}
          label={{ value: 'PC1', position: 'insideBottom', offset: -2, fontSize: 11 }}
        />
        <YAxis
          dataKey="y"
          name="PC2"
          tick={{ fontSize: 11 }}
          label={{ value: 'PC2', angle: -90, position: 'insideLeft', fontSize: 11 }}
        />
        <ZAxis range={[60, 60]} />
        <Tooltip
          content={({ payload }) => {
            if (!payload?.length) return null;
            const p = payload[0].payload as ScatterPoint;
            return (
              <div className="bg-white border rounded p-2 text-xs shadow">
                <p className="font-bold">{p.ticker}</p>
                <p>Return: {p.return_pct}%</p>
                <p>Held: {p.holding_days} days</p>
                <p className="text-gray-400">
                  Cluster {p.cluster_id + 1}
                  {labels?.[p.cluster_id] ? ` · ${labels[p.cluster_id]}` : ''}
                </p>
              </div>
            );
          }}
        />
        {groups.map((g, i) => (
          <Scatter
            key={i}
            name={labels?.[i] || `Cluster ${i + 1}`}
            data={g}
            fill={COLORS[i % COLORS.length]}
            isAnimationActive={false}
          />
        ))}
      </ScatterChart>
    </ResponsiveContainer>
  );
}
