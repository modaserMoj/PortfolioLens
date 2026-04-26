import { clsx } from 'clsx';
import type { ReactNode } from 'react';

interface Props {
  label: ReactNode;
  value: ReactNode;
  suffix?: string;
  trend?: 'up' | 'down' | 'neutral';
  detail?: ReactNode;
}

export default function MetricCard({ label, value, suffix = '', trend, detail }: Props) {
  return (
    <div className="card p-5">
      <p className="text-sm text-gray-500 mb-1">{label}</p>
      <p
        className={clsx('text-2xl font-bold', {
          'text-green-600': trend === 'up',
          'text-red-600': trend === 'down',
          'text-gray-900': trend === 'neutral' || !trend,
        })}
      >
        {value}
        {suffix}
      </p>
      {detail && <p className="text-xs text-gray-400 mt-1">{detail}</p>}
    </div>
  );
}
