import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useAnalytics, useTrades } from '../hooks/usePortfolio';
import ClusterScatter from '../components/charts/ClusterScatter';
import { clsx } from 'clsx';
import HelpHint from '../components/HelpHint';

const CLUSTER_COLORS = [
  'bg-blue-100 text-blue-800 border-blue-200',
  'bg-purple-100 text-purple-800 border-purple-200',
  'bg-emerald-100 text-emerald-800 border-emerald-200',
  'bg-amber-100 text-amber-800 border-amber-200',
  'bg-red-100 text-red-800 border-red-200',
];

export default function TradesPage() {
  const { id } = useParams<{ id: string }>();
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 50;
  const trades = useTrades(id!, page, PAGE_SIZE);
  const analytics = useAnalytics(id!);
  const clustering = analytics.data?.clustering;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Trade History</h1>

      {clustering && clustering.n_clusters > 0 && (
        <div className="card p-5">
          <h2 className="text-lg font-semibold mb-1">
            <HelpHint
              term="Trade Clusters"
              meaning="Groups of similar trades discovered automatically from your data."
            />
          </h2>
          <p className="text-sm text-gray-500 mb-4">
            <HelpHint
              term="K-means"
              meaning="A method that groups similar items into clusters."
            />{' '}
            clusters grouped by holding period, return, size, sector, and
            day-of-week.{' '}
            <HelpHint
              term="PCA"
              meaning="A method that compresses many inputs into a few summary dimensions so they can be charted."
            />{' '}
            projects feature vectors to 2D.
          </p>
          <p className="text-xs text-gray-500 mb-4">
            Axes are{' '}
            <HelpHint
              term="PC1"
              meaning="The strongest overall pattern in your trade data after compression. It is a relative direction, not a real-world unit."
            />{' '}
            and{' '}
            <HelpHint
              term="PC2"
              meaning="The second strongest independent pattern. Use this chart to compare similarity between trades, not absolute values."
            />
            . Points close together behave similarly; points far apart behave differently.
          </p>
          <div className="mb-4 rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs text-gray-700">
            <p className="font-semibold text-gray-900 mb-1">How to read this chart</p>
            <ul className="space-y-1 list-disc pl-4">
              <li>Each dot is one closed trade, and color shows its cluster.</li>
              <li>Top cards summarize each cluster: size, return, win rate, hold time, and sector tilt.</li>
              <li>Focus on large clusters first, because they represent your most common habits.</li>
              <li>
                Compare return and win rate together; a high win rate can still hide poor average
                returns.
              </li>
              <li>
                Use PC1/PC2 for similarity only: close points are behaviorally similar, far points
                are different.
              </li>
            </ul>
          </div>

          <div className="grid md:grid-cols-3 gap-3 mb-4">
            {clustering.clusters.map((c) => (
              <div
                key={c.cluster_id}
                className={clsx(
                  'p-3 rounded-lg border text-sm',
                  CLUSTER_COLORS[c.cluster_id % CLUSTER_COLORS.length],
                )}
              >
                <p className="font-bold">{c.label}</p>
                <p>
                  {c.trade_count} trades · {c.avg_return_pct >= 0 ? '+' : ''}
                  {c.avg_return_pct}% avg · {c.win_rate_pct}% win
                </p>
                <p className="opacity-70 text-xs mt-1">
                  {c.dominant_sector} · {c.avg_holding_days}d avg hold · {c.dominant_action_pattern}
                </p>
              </div>
            ))}
          </div>
          <ClusterScatter
            data={clustering.scatter_data}
            nClusters={clustering.n_clusters}
            labels={clustering.clusters.map((c) => c.label)}
          />
        </div>
      )}

      <div className="card overflow-hidden">
        <div className="overflow-x-auto thin-scroll">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left p-3 font-medium text-gray-600">Date</th>
                <th className="text-left p-3 font-medium text-gray-600">Ticker</th>
                <th className="text-left p-3 font-medium text-gray-600">Action</th>
                <th className="text-right p-3 font-medium text-gray-600">Qty</th>
                <th className="text-right p-3 font-medium text-gray-600">Price</th>
                <th className="text-right p-3 font-medium text-gray-600">Total</th>
                <th className="text-right p-3 font-medium text-gray-600">Fees</th>
              </tr>
            </thead>
            <tbody>
              {trades.data?.trades.map((t) => (
                <tr key={t.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="p-3">{new Date(t.trade_date).toLocaleDateString()}</td>
                  <td className="p-3 font-medium">{t.ticker}</td>
                  <td
                    className={clsx(
                      'p-3 font-medium',
                      t.action === 'BUY' ? 'text-green-600' : 'text-red-600',
                    )}
                  >
                    {t.action}
                  </td>
                  <td className="p-3 text-right">{t.quantity}</td>
                  <td className="p-3 text-right">${t.price.toFixed(2)}</td>
                  <td className="p-3 text-right">${t.total_amount.toFixed(2)}</td>
                  <td className="p-3 text-right text-gray-400">${t.fees.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {trades.data && trades.data.total > PAGE_SIZE && (
          <div className="flex justify-between items-center p-3 border-t border-gray-200">
            <span className="text-sm text-gray-400">
              Showing {(page - 1) * PAGE_SIZE + 1}–
              {Math.min(page * PAGE_SIZE, trades.data.total)} of {trades.data.total}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1 border rounded text-sm disabled:opacity-50 hover:bg-gray-50"
              >
                Prev
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={page * PAGE_SIZE >= trades.data.total}
                className="px-3 py-1 border rounded text-sm disabled:opacity-50 hover:bg-gray-50"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
