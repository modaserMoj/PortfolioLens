import { useParams } from 'react-router-dom';
import { clsx } from 'clsx';
import { useAnalytics } from '../hooks/usePortfolio';
import MetricCard from '../components/MetricCard';
import SectorDonut from '../components/charts/SectorDonut';
import HelpHint from '../components/HelpHint';

function corrColor(v: number, isDiag: boolean): string {
  if (isDiag) return 'bg-gray-100 text-gray-500';
  if (v > 0.7) return 'bg-red-200 text-red-900 font-bold';
  if (v > 0.4) return 'bg-amber-100 text-amber-900';
  if (v > 0) return 'bg-gray-50';
  if (v > -0.4) return 'bg-blue-50 text-blue-900';
  return 'bg-blue-200 text-blue-900';
}

export default function RiskPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading } = useAnalytics(id!);

  if (isLoading) {
    return <div className="text-center py-20 text-gray-400">Loading…</div>;
  }
  const risk = data?.risk;
  if (!risk) {
    return (
      <div className="text-center py-20 text-gray-500">
        No risk data available. Analyze the portfolio first.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Risk Analysis</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label={
            <HelpHint
              term="Portfolio Beta"
              meaning="How strongly your portfolio tends to move when the market moves. 1.0 means about the same as the market."
            />
          }
          value={risk.portfolio_beta}
          trend={
            risk.portfolio_beta > 1.3
              ? 'down'
              : risk.portfolio_beta < 0.7
              ? 'neutral'
              : 'up'
          }
          detail={
            <HelpHint
              term="vs SPY"
              meaning="Compared against SPY, an ETF often used as a stand-in for the U.S. stock market."
            />
          }
        />
        <MetricCard
          label={
            <HelpHint
              term="Alpha (Annual)"
              meaning="Extra return beyond what market risk alone would predict, shown per year."
            />
          }
          value={`${risk.alpha_annualized >= 0 ? '+' : ''}${risk.alpha_annualized}`}
          suffix="%"
          trend={risk.alpha_annualized > 0 ? 'up' : 'down'}
        />
        <MetricCard
          label={
            <HelpHint
              term="Concentration (HHI)"
              meaning="How concentrated your holdings are. HHI is a concentration score: higher means less diversified."
            />
          }
          value={risk.concentration_hhi}
          detail={risk.concentration_level}
          trend={
            risk.concentration_level === 'high'
              ? 'down'
              : risk.concentration_level === 'low'
              ? 'up'
              : 'neutral'
          }
        />
        <MetricCard
          label="Top Holding"
          value={risk.top_holdings[0]?.ticker ?? '—'}
          detail={`${((risk.top_holdings[0]?.weight ?? 0) * 100).toFixed(1)}% of capital`}
        />
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="card p-5">
          <h2 className="text-lg font-semibold mb-3">
            <HelpHint
              term="Sector Allocation"
              meaning="How your portfolio is split across industries like tech, finance, or energy."
            />
          </h2>
          <SectorDonut data={risk.sector_exposure} />
        </div>
        <div className="card p-5">
          <h2 className="text-lg font-semibold mb-3">Top Holdings</h2>
          <div className="space-y-2">
            {risk.top_holdings.slice(0, 10).map((h) => (
              <div key={h.ticker} className="flex justify-between items-center">
                <span className="font-medium">{h.ticker}</span>
                <div className="flex items-center gap-2">
                  <div className="w-40 bg-gray-200 rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-primary-600 h-2 rounded-full"
                      style={{ width: `${Math.min(h.weight * 100, 100)}%` }}
                    />
                  </div>
                  <span className="text-sm text-gray-500 w-14 text-right">
                    {(h.weight * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {risk.correlation_matrix.tickers.length > 0 && (
        <div className="card p-5">
          <h2 className="text-lg font-semibold mb-3">
            <HelpHint
              term="Correlation Matrix — Top Holdings"
              meaning="A grid showing which holdings tend to move together. Higher correlation means similar movement."
            />
          </h2>
          <p className="text-sm text-gray-500 mb-3">
            Highlighted cells &gt; 0.7 indicate holdings that move together — you're less
            diversified than you think.
          </p>
          <div className="overflow-x-auto thin-scroll">
            <table className="text-xs border-separate border-spacing-1">
              <thead>
                <tr>
                  <th className="p-2 w-16"></th>
                  {risk.correlation_matrix.tickers.map((t) => (
                    <th key={t} className="p-2 text-gray-500 font-medium">{t}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {risk.correlation_matrix.tickers.map((t, i) => (
                  <tr key={t}>
                    <td className="p-2 font-medium text-gray-600">{t}</td>
                    {risk.correlation_matrix.matrix[i].map((val, j) => (
                      <td
                        key={j}
                        className={clsx('p-2 text-center rounded', corrColor(val, i === j))}
                      >
                        {val.toFixed(2)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
