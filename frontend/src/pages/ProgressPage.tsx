import { useMemo } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { useProgress } from '../hooks/usePortfolio';

function DeltaRow({
  label,
  suffix = '',
  previous,
  current,
  delta,
  direction,
}: {
  label: string;
  suffix?: string;
  previous: number;
  current: number;
  delta: number;
  direction: 'improved' | 'worsened' | 'unchanged';
}) {
  const tone =
    direction === 'improved'
      ? 'text-green-700 bg-green-50 border-green-200'
      : direction === 'worsened'
      ? 'text-amber-700 bg-amber-50 border-amber-200'
      : 'text-gray-700 bg-gray-50 border-gray-200';

  return (
    <div className="rounded-lg border border-gray-200 p-4 space-y-2">
      <p className="font-medium">{label}</p>
      <div className="text-sm text-gray-600 flex justify-between">
        <span>Previous</span>
        <span>{previous}{suffix}</span>
      </div>
      <div className="text-sm text-gray-600 flex justify-between">
        <span>Current</span>
        <span>{current}{suffix}</span>
      </div>
      <div className="pt-1">
        <span className={`inline-flex items-center rounded-md border px-2 py-1 text-xs font-medium ${tone}`}>
          {delta >= 0 ? '+' : ''}{delta}{suffix} · {direction}
        </span>
      </div>
    </div>
  );
}

export default function ProgressPage() {
  const { id } = useParams<{ id: string }>();
  const [params] = useSearchParams();
  const previousId = params.get('previous');
  const portfolioId = useMemo(() => id ?? '', [id]);
  const progressData = useProgress(portfolioId, previousId ?? '');

  if (!previousId) {
    return (
      <div className="max-w-3xl mx-auto card p-6 text-sm text-gray-600">
        Add a previous CSV on the upload screen to unlock progress tracking.
      </div>
    );
  }

  if (progressData.isLoading) {
    return (
      <div className="text-center py-20">
        <div className="inline-block animate-spin rounded-full h-10 w-10 border-b-2 border-primary-600 mb-4"></div>
        <p className="text-gray-500">Computing progress comparison…</p>
      </div>
    );
  }

  if (progressData.isError || !progressData.data) {
    return (
      <div className="max-w-3xl mx-auto card p-6 text-sm text-gray-600">
        Could not load progress comparison. Re-upload both CSV files and try again.
      </div>
    );
  }

  const data = progressData.data;
  const improvedCount = data.metrics.filter((m) => m.direction === 'improved').length;
  const worsenedCount = data.metrics.filter((m) => m.direction === 'worsened').length;
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">Progress</h1>
        <p className="text-sm text-gray-500">{data.comparison_label}</p>
      </header>

      <div className="card p-5">
        <p className="text-sm text-gray-500 mb-2">Comparison Snapshot</p>
        <p className="text-3xl font-bold text-primary-700">
          {improvedCount} improved
          <span className="text-base text-gray-500 font-medium"> · {worsenedCount} worsened</span>
        </p>
        <p className="text-sm text-gray-600 mt-2">Showing side-by-side metric deltas instead of a single composite score.</p>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {data.metrics.map((metric) => (
          <DeltaRow
            key={metric.key}
            label={metric.label}
            previous={metric.previous}
            current={metric.current}
            delta={metric.delta}
            direction={metric.direction}
            suffix={metric.unit}
          />
        ))}
      </div>

      <div className="card p-5 text-sm text-gray-700">
        <p className="font-medium mb-1">Takeaway</p>
        <p>{data.summary}</p>
      </div>
    </div>
  );
}
