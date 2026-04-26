export interface UploadResponse {
  portfolio_id: string;
  trade_count: number;
  date_range: { start: string; end: string };
  tickers_found: string[];
  detected_format?: string;
}

export interface Portfolio {
  id: string;
  name: string;
  broker: string;
  trade_count: number;
  tickers: string[];
  date_range: { start: string; end: string };
  created_at: string;
}

export interface Trade {
  id: string;
  ticker: string;
  action: 'BUY' | 'SELL';
  quantity: number;
  price: number;
  total_amount: number;
  fees: number;
  currency: string;
  trade_date: string;
  cluster_id?: number;
}

export interface PerformanceMetrics {
  total_return_pct: number;
  annualized_return_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown_pct: number;
  max_drawdown_start: string;
  max_drawdown_end: string;
  win_rate_pct: number;
  total_trades_closed: number;
  equity_curve: { date: string; value: number }[];
  monthly_returns: { year: number; month: number; return_pct: number }[];
}

export interface RiskMetrics {
  sector_exposure: Record<string, number>;
  concentration_hhi: number;
  concentration_level: 'low' | 'moderate' | 'high';
  portfolio_beta: number;
  alpha_annualized: number;
  top_holdings: { ticker: string; weight: number }[];
  correlation_matrix: { tickers: string[]; matrix: number[][] };
}

export interface BehavioralMetrics {
  avg_holding_days: number;
  median_holding_days: number;
  trade_frequency_per_month: number;
  avg_position_size_pct: number;
  max_position_size_pct: number;
  overtrading_flag: boolean;
  overtrading_detail: string | null;
  day_of_week_distribution: Record<string, number>;
  disposition_effect: {
    avg_days_hold_winners: number;
    avg_days_hold_losers: number;
    flag: boolean;
  };
}

export interface ClusterInfo {
  cluster_id: number;
  label: string;
  trade_count: number;
  avg_return_pct: number;
  win_rate_pct: number;
  avg_holding_days: number;
  dominant_sector: string;
  dominant_action_pattern: string;
}

export interface ClusteringMetrics {
  n_clusters: number;
  clusters: ClusterInfo[];
  scatter_data: {
    x: number;
    y: number;
    cluster_id: number;
    ticker: string;
    return_pct: number;
    holding_days: number;
  }[];
}

export interface FullAnalytics {
  performance: PerformanceMetrics;
  risk: RiskMetrics;
  behavioral: BehavioralMetrics;
  clustering: ClusteringMetrics;
}

export interface InsightData {
  summary: string;
  key_findings: string[];
  doing_well: string;
  costing_money: string;
  generated_at: string;
}

export interface MetricDelta {
  previous: number;
  current: number;
  delta: number;
  direction: 'improved' | 'worsened' | 'unchanged';
}

export interface ComparisonMetric {
  key: string;
  label: string;
  unit: string;
  previous: number;
  current: number;
  delta: number;
  direction: 'improved' | 'worsened' | 'unchanged';
}

export interface ProgressData {
  current_portfolio_id: string;
  previous_portfolio_id: string;
  comparison_label: string;
  metrics: ComparisonMetric[];
  summary: string;
}
