import { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { useAnalytics, useAnalyze, usePortfolio } from '../hooks/usePortfolio';
import MetricCard from '../components/MetricCard';
import EquityCurve from '../components/charts/EquityCurve';
import MonthlyHeatmap from '../components/charts/MonthlyHeatmap';
import SectorDonut from '../components/charts/SectorDonut';
import DrawdownChart from '../components/charts/DrawdownChart';
import HelpHint from '../components/HelpHint';

export default function DashboardPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const portfolio = usePortfolio(id!);
  const analytics = useAnalytics(id!);
  const analyze = useAnalyze(id!);

  // Auto-trigger analysis on first load if no analytics exist yet.
  useEffect(() => {
    if (analytics.isError && !analyze.isPending && !analyze.isSuccess) {
      analyze.mutate(undefined, {
        onSuccess: () => {
          qc.invalidateQueries({ queryKey: ['analytics', id] });
          qc.invalidateQueries({ queryKey: ['insights', id] });
        },
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analytics.isError]);

  if (portfolio.isLoading || analytics.isLoading || analyze.isPending) {
    return (
      <div className="text-center py-20">
        <div className="inline-block animate-spin rounded-full h-10 w-10 border-b-2 border-primary-600 mb-4"></div>
        <p className="text-gray-500">
          {analyze.isPending ? 'Running analytics pipeline…' : 'Loading…'}
        </p>
        <p className="text-xs text-gray-400 mt-2">
          Enriching sectors, fetching benchmark prices, clustering trades, generating insights.
        </p>
      </div>
    );
  }

  const perf = analytics.data?.performance;
  const risk = analytics.data?.risk;
  const behav = analytics.data?.behavioral;

  if (!perf) {
    return (
      <div className="text-center py-20 text-gray-500">
        No data yet.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">{portfolio.data?.name}</h1>
        <p className="text-sm text-gray-500">
          {portfolio.data?.trade_count} trades · {portfolio.data?.tickers.length} tickers · {portfolio.data?.broker.toUpperCase()}
        </p>
        {portfolio.data?.date_range && (
          <p className="text-xs text-gray-400 mt-1">
            {new Date(portfolio.data.date_range.start).toLocaleDateString()} - {new Date(portfolio.data.date_range.end).toLocaleDateString()}
            {' · '}
            Created {new Date(portfolio.data.created_at).toLocaleString()}
          </p>
        )}
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Total Return"
          value={`${perf.total_return_pct >= 0 ? '+' : ''}${perf.total_return_pct}`}
          suffix="%"
          trend={perf.total_return_pct >= 0 ? 'up' : 'down'}
          detail={`${perf.annualized_return_pct >= 0 ? '+' : ''}${perf.annualized_return_pct}% annualized`}
        />
        <MetricCard
          label={
            <HelpHint
              term="Sharpe Ratio"
              meaning="A score of return compared to risk. Higher means better reward for the ups and downs you took."
            />
          }
          value={perf.sharpe_ratio}
          trend={
            perf.sharpe_ratio >= 1 ? 'up' : perf.sharpe_ratio >= 0 ? 'neutral' : 'down'
          }
          detail={
            <HelpHint
              term={`Sortino ${perf.sortino_ratio}`}
              meaning="Like Sharpe, but only counts harmful volatility (downside swings)."
            />
          }
        />
        <MetricCard
          label="Win Rate"
          value={perf.win_rate_pct}
          suffix="%"
          trend={perf.win_rate_pct >= 50 ? 'up' : 'down'}
          detail={`${perf.total_trades_closed} closed trades`}
        />
        <MetricCard
          label={
            <HelpHint
              term="Max Drawdown"
              meaning="The biggest drop from a past peak to a later low in your portfolio value."
            />
          }
          value={`-${perf.max_drawdown_pct}`}
          suffix="%"
          trend="down"
          detail={
            perf.max_drawdown_start && perf.max_drawdown_end
              ? `${perf.max_drawdown_start} → ${perf.max_drawdown_end}`
              : undefined
          }
        />
      </div>

      <div className="card p-5">
        <h2 className="text-lg font-semibold mb-3">Equity Curve</h2>
        <EquityCurve data={perf.equity_curve} />
      </div>

      <div className="card p-5">
        <h2 className="text-lg font-semibold mb-3">
          <HelpHint
            term="Drawdown"
            meaning="How far your portfolio falls from its recent high before it recovers."
          />
        </h2>
        <DrawdownChart data={perf.equity_curve} />
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="card p-5">
          <h2 className="text-lg font-semibold mb-3">Monthly Returns</h2>
          <MonthlyHeatmap data={perf.monthly_returns} />
        </div>
        <div className="card p-5">
          <h2 className="text-lg font-semibold mb-3">
            <HelpHint
              term="Sector Exposure"
              meaning="How much of your money sits in each market sector, like tech or healthcare."
            />
          </h2>
          {risk && <SectorDonut data={risk.sector_exposure} />}
        </div>
      </div>

      {behav?.overtrading_flag && behav.overtrading_detail && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-900">
          <strong>Heads up:</strong> {behav.overtrading_detail}
        </div>
      )}

      {behav && (
        <div className="card p-5 space-y-4">
          <h2 className="text-lg font-semibold">Behavioral Metrics</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard label="Avg Hold" value={behav.avg_holding_days} suffix="d" />
            <MetricCard label="Median Hold" value={behav.median_holding_days} suffix="d" />
            <MetricCard label="Trades / Month" value={behav.trade_frequency_per_month} />
            <MetricCard
              label={
                <HelpHint
                  term="Max Position"
                  meaning="The largest single holding size you had, shown as a percent of your portfolio."
                />
              }
              value={behav.max_position_size_pct}
              suffix="%"
            />
          </div>

          <div className="grid md:grid-cols-2 gap-4 text-sm">
            <div className="rounded-lg border border-gray-200 p-4">
              <p className="font-medium mb-2">
                <HelpHint
                  term="Day-of-Week Distribution"
                  meaning="How many trades you opened on each weekday. Use this to spot timing concentration, like repeatedly entering trades on one day."
                />
              </p>
              {Object.keys(behav.day_of_week_distribution).length > 0 ? (
                <div className="space-y-1 text-gray-700">
                  {Object.entries(behav.day_of_week_distribution).map(([day, count]) => (
                    <div key={day} className="flex justify-between">
                      <span>{day}</span>
                      <span className="font-medium">{count}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-400">No day-of-week data.</p>
              )}
            </div>

            <div className="rounded-lg border border-gray-200 p-4">
              <p className="font-medium mb-2">
                <HelpHint
                  term="Disposition Effect"
                  meaning="Compares average hold time for winning vs losing trades. If losers are held longer than winners, the bias is detected; if not, it is not detected."
                />
              </p>
              <div className="space-y-1 text-gray-700">
                <div className="flex justify-between">
                  <span>Winners held</span>
                  <span className="font-medium">
                    {behav.disposition_effect.avg_days_hold_winners}d
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Losers held</span>
                  <span className="font-medium">
                    {behav.disposition_effect.avg_days_hold_losers}d
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Flag</span>
                  <span
                    className={
                      behav.disposition_effect.flag ? 'font-medium text-amber-700' : 'font-medium text-green-700'
                    }
                  >
                    {behav.disposition_effect.flag ? 'Detected' : 'Not detected'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
