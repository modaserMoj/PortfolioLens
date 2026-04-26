from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def compute_clustering(
    closed_trades: list[dict[str, Any]], enrichments: dict[str, dict]
) -> dict:
    if len(closed_trades) < 6:
        return {"n_clusters": 0, "clusters": [], "scatter_data": []}

    features: list[dict[str, Any]] = []
    for ct in closed_trades:
        sector = enrichments.get(ct["ticker"], {}).get("sector") or "Unknown"
        buy_date = ct["buy_date"]
        dow = buy_date.weekday() if hasattr(buy_date, "weekday") else 0
        features.append(
            {
                "holding_days": float(ct["holding_days"]),
                "return_pct": float(ct["return_pct"]),
                "position_value": float(ct["quantity"]) * float(ct["buy_price"]),
                "was_winner": 1.0 if ct["pnl"] > 0 else 0.0,
                "day_of_week": float(dow),
                "sector": sector,
            }
        )

    numeric_cols = [
        "holding_days",
        "return_pct",
        "position_value",
        "was_winner",
        "day_of_week",
    ]
    X_numeric = np.array([[f[c] for c in numeric_cols] for f in features], dtype=float)

    sectors = [[f["sector"]] for f in features]
    ohe = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
    X_sector = ohe.fit_transform(sectors)

    X = np.hstack([X_numeric, X_sector])
    X_scaled = StandardScaler().fit_transform(X)

    # Pick best k using silhouette score
    n = len(closed_trades)
    max_k = min(5, max(2, n // 3))
    best_k, best_score = 2, -1.0
    for k in range(2, max_k + 1):
        try:
            km = KMeans(n_clusters=k, n_init=10, random_state=42)
            labels = km.fit_predict(X_scaled)
            if len(set(labels)) < 2:
                continue
            score = silhouette_score(X_scaled, labels)
            if score > best_score:
                best_score = score
                best_k = k
        except Exception:
            continue

    km = KMeans(n_clusters=best_k, n_init=10, random_state=42)
    labels = km.fit_predict(X_scaled)

    # PCA to 2D
    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(X_scaled)

    # Cluster summaries
    members_by_cid: dict[int, list[tuple[dict, dict]]] = {i: [] for i in range(best_k)}
    for idx, ct in enumerate(closed_trades):
        cid = int(labels[idx])
        ct["cluster_id"] = cid
        members_by_cid[cid].append((ct, features[idx]))

    cluster_stats: list[dict[str, Any]] = []
    for cid in range(best_k):
        members = members_by_cid[cid]
        if not members:
            continue
        cts = [m[0] for m in members]
        feats = [m[1] for m in members]
        avg_ret = float(np.mean([ct["return_pct"] for ct in cts]))
        avg_hold = float(np.mean([ct["holding_days"] for ct in cts]))
        win_rate = sum(1 for ct in cts if ct["pnl"] > 0) / len(cts) * 100.0

        sec_counts: dict[str, int] = {}
        for f in feats:
            sec_counts[f["sector"]] = sec_counts.get(f["sector"], 0) + 1
        dominant_sector = (
            max(sec_counts, key=sec_counts.get) if sec_counts else "Mixed"
        )

        cluster_stats.append(
            {
                "cluster_id": cid,
                "trade_count": len(cts),
                "avg_return_pct": avg_ret,
                "win_rate_pct": win_rate,
                "avg_holding_days": avg_hold,
                "dominant_sector": dominant_sector,
            }
        )

    if not cluster_stats:
        return {"n_clusters": 0, "clusters": [], "scatter_data": []}

    hold_values = [c["avg_holding_days"] for c in cluster_stats]
    low_hold = float(np.percentile(hold_values, 33))
    high_hold = float(np.percentile(hold_values, 67))

    # If clusters have very similar hold durations, fall back to absolute cutoffs.
    use_absolute_hold_buckets = (high_hold - low_hold) < 7

    clusters = []
    for c in cluster_stats:
        avg_hold = c["avg_holding_days"]
        avg_ret = c["avg_return_pct"]
        win_rate = c["win_rate_pct"]

        if use_absolute_hold_buckets:
            if avg_hold < 14:
                hold_style = "Quick Turnover"
                pattern_horizon = "short-horizon"
            elif avg_hold < 60:
                hold_style = "Swing Holds"
                pattern_horizon = "mid-horizon"
            else:
                hold_style = "Long Holds"
                pattern_horizon = "long-horizon"
        else:
            if avg_hold <= low_hold:
                hold_style = "Quick Turnover"
                pattern_horizon = "short-horizon"
            elif avg_hold >= high_hold:
                hold_style = "Long Holds"
                pattern_horizon = "long-horizon"
            else:
                hold_style = "Swing Holds"
                pattern_horizon = "mid-horizon"

        if avg_ret >= 8 and win_rate >= 60:
            perf_style = "Strong Winners"
            pattern_outcome = "high-win profile"
        elif avg_ret >= 3:
            perf_style = "Steady Winners"
            pattern_outcome = "mostly profitable"
        elif avg_ret <= -5 and win_rate < 45:
            perf_style = "Consistent Losers"
            pattern_outcome = "low-win profile"
        elif avg_ret < 0:
            perf_style = "Choppy Returns"
            pattern_outcome = "mixed results"
        else:
            perf_style = "Balanced Returns"
            pattern_outcome = "balanced results"

        clusters.append(
            {
                "cluster_id": c["cluster_id"],
                "label": f"{hold_style} · {perf_style}",
                "trade_count": c["trade_count"],
                "avg_return_pct": round(avg_ret, 2),
                "win_rate_pct": round(win_rate, 1),
                "avg_holding_days": round(avg_hold, 1),
                "dominant_sector": c["dominant_sector"],
                "dominant_action_pattern": f"{pattern_horizon}, {pattern_outcome}",
            }
        )

    scatter = []
    for idx, ct in enumerate(closed_trades):
        scatter.append(
            {
                "x": round(float(coords[idx][0]), 3),
                "y": round(float(coords[idx][1]), 3),
                "cluster_id": int(labels[idx]),
                "ticker": ct["ticker"],
                "return_pct": round(float(ct["return_pct"]), 2),
                "holding_days": int(ct["holding_days"]),
            }
        )

    return {
        "n_clusters": best_k,
        "clusters": clusters,
        "scatter_data": scatter,
    }
