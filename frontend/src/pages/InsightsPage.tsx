import { useParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Lightbulb, RefreshCw, TrendingDown, TrendingUp } from 'lucide-react';
import { useAnalyze, useInsights } from '../hooks/usePortfolio';

export default function InsightsPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const { data, isLoading, isError } = useInsights(id!);
  const analyze = useAnalyze(id!);

  const handleRegenerate = async () => {
    await analyze.mutateAsync();
    qc.invalidateQueries({ queryKey: ['insights', id] });
    qc.invalidateQueries({ queryKey: ['analytics', id] });
  };

  if (isLoading || analyze.isPending) {
    return (
      <div className="text-center py-20">
        <div className="inline-block animate-spin rounded-full h-10 w-10 border-b-2 border-primary-600 mb-4"></div>
        <p className="text-gray-400">
          {analyze.isPending ? 'Regenerating insights…' : 'Loading insights…'}
        </p>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="max-w-3xl mx-auto text-center py-20 space-y-4">
        <p className="text-gray-500">No insights available yet.</p>
        <button
          onClick={handleRegenerate}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg text-sm hover:bg-primary-700"
        >
          Generate insights
        </button>
      </div>
    );
  }

  const findings = (data.key_findings ?? []).filter((finding) => {
    const text = finding.trim();
    if (!text) return false;
    // Hide legacy placeholder rows from older generated payloads.
    if (text.includes('Need more closed-trade diversity')) return false;
    if (text.includes('Not enough closed trades yet')) return false;
    return true;
  });

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">AI Insights</h1>
        <button
          onClick={handleRegenerate}
          disabled={analyze.isPending}
          className="flex items-center gap-2 px-4 py-2 border rounded-lg text-sm hover:bg-gray-50 disabled:opacity-50"
        >
          <RefreshCw size={14} className={analyze.isPending ? 'animate-spin' : ''} />
          Regenerate
        </button>
      </div>

      <div className="card p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Lightbulb size={18} className="text-yellow-500" /> Key Findings
        </h2>
        <p className="text-sm text-gray-500 mb-4">
          Real trade examples where timing likely cost you returns, and the specific
          signals that could have helped you make a better decision in the moment.
        </p>
        <ul className="space-y-3">
          {findings.map((finding, i) => (
            <li key={i} className="flex gap-3 text-sm">
              <span className="shrink-0 w-6 h-6 bg-primary-100 text-primary-700 rounded-full flex items-center justify-center text-xs font-bold">
                {i + 1}
              </span>
              <span>{finding}</span>
            </li>
          ))}
        </ul>
        {findings.length === 0 && (
          <p className="text-sm text-gray-500">No coaching instances yet. Click Regenerate.</p>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-green-50 border border-green-200 rounded-xl p-5">
          <h3 className="font-semibold text-green-800 flex items-center gap-2 mb-2">
            <TrendingUp size={16} /> What You're Doing Well
          </h3>
          <p className="text-sm text-green-900">
            {data.doing_well || 'No standout strength identified yet. Regenerate after more trades.'}
          </p>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-xl p-5">
          <h3 className="font-semibold text-red-800 flex items-center gap-2 mb-2">
            <TrendingDown size={16} /> What's Costing You Money
          </h3>
          <p className="text-sm text-red-900">
            {data.costing_money || 'No single dominant cost driver identified yet. Regenerate after more trades.'}
          </p>
        </div>
      </div>

      {data.generated_at && (
        <p className="text-xs text-gray-400 text-center">
          Generated {new Date(data.generated_at).toLocaleString()}
        </p>
      )}
    </div>
  );
}
