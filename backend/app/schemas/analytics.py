from pydantic import BaseModel
from datetime import datetime


class PerformanceMetrics(BaseModel):
    total_return_pct: float = 0
    annualized_return_pct: float = 0
    sharpe_ratio: float = 0
    sortino_ratio: float = 0
    max_drawdown_pct: float = 0
    max_drawdown_start: str = ""
    max_drawdown_end: str = ""
    win_rate_pct: float = 0
    total_trades_closed: int = 0
    equity_curve: list[dict] = []
    monthly_returns: list[dict] = []


class RiskMetrics(BaseModel):
    sector_exposure: dict[str, float] = {}
    concentration_hhi: float = 0
    concentration_level: str = "low"
    portfolio_beta: float = 0
    alpha_annualized: float = 0
    top_holdings: list[dict] = []
    correlation_matrix: dict = {"tickers": [], "matrix": []}


class BehavioralMetrics(BaseModel):
    avg_holding_days: float = 0
    median_holding_days: float = 0
    trade_frequency_per_month: float = 0
    avg_position_size_pct: float = 0
    max_position_size_pct: float = 0
    overtrading_flag: bool = False
    overtrading_detail: str | None = None
    day_of_week_distribution: dict[str, int] = {}
    disposition_effect: dict = {
        "avg_days_hold_winners": 0,
        "avg_days_hold_losers": 0,
        "flag": False,
    }


class ClusterInfo(BaseModel):
    cluster_id: int
    label: str
    trade_count: int
    avg_return_pct: float
    win_rate_pct: float
    avg_holding_days: float
    dominant_sector: str
    dominant_action_pattern: str


class ClusteringMetrics(BaseModel):
    n_clusters: int = 0
    clusters: list[ClusterInfo] = []
    scatter_data: list[dict] = []


class FullAnalyticsResponse(BaseModel):
    performance: PerformanceMetrics
    risk: RiskMetrics
    behavioral: BehavioralMetrics
    clustering: ClusteringMetrics


class MetricDelta(BaseModel):
    previous: float
    current: float
    delta: float
    direction: str


class ComparisonMetric(BaseModel):
    key: str
    label: str
    unit: str = ""
    previous: float
    current: float
    delta: float
    direction: str


class ProgressResponse(BaseModel):
    current_portfolio_id: str
    previous_portfolio_id: str
    comparison_label: str
    metrics: list[ComparisonMetric]
    summary: str


class InsightResponse(BaseModel):
    summary: str
    key_findings: list[str]
    doing_well: str
    costing_money: str
    generated_at: datetime


class AnalyzeResponse(BaseModel):
    status: str
    portfolio_id: str
