# -*- coding: utf-8 -*-
"""
annihilation_intensity_backtest.py  (v3 —— 加入成交量加权，用来诊断集中度问题)

独立假设验证脚本 —— 不改动 unified_scanner.py / planb_daily_scan.py 等任何生产脚本。

v1: 中位数分组，fast组表面赢了，但样本比例195:60/185:71明显失衡
v2: 加了三项稳健性检查（四分位分组/零斜率占比/集中度检查），三条标准里
    a部分失败(样本外胜率反转)、b明确失败(零斜率47.4%)、c严重失败(前3只股票占比67-79%)
    → 结论：假设不成立，正式放弃"用线性斜率衡量翻转速度"这条路（已记录到Drive）

v3: 不是重启假设，而是针对 v2 暴露出的"集中度"问题做一次诊断——
    用成交量比（该信号触发日的 Volume / 该股票自己的N日均量，复用
    v7pro_mcdx_scan.py 里 calc_vol_score_series 的现成逻辑，不是新变量）
    给分组统计加权：
      - 加权平均超额收益 / 加权胜率：放量大的信号权重高，量稀薄的信号权重低
      - 加权集中度：如果某几只股票占比高只是因为反复触发很多次但每次都缩量，
        加权后占比会被稀释；如果加权后占比依然很高，说明是真实现象不是统计假象
    这不是在验证"量"本身是不是有效信号（那条路仍然按排期留到monthly
    double-attack样本外验证完成后再说），只是用它来判断 v2 的集中度问题
    是数据噪音还是真实市场行为。

运行方式:
    cd ~/Documents/PlanB_Scanner
    python3 annihilation_intensity_backtest.py
"""

import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import yfinance as yf
from dataclasses import dataclass

import v7pro_mcdx_scan as v7
import planb_bridge as br

# ---- config -----------------------------------------------------------
SIGNALS_CSV = "planb_backtest_signals.csv"
LOOKBACK_DAYS = 10
IN_SAMPLE_CUTOFF = "2016-08-14"
MIN_HISTORY_ROWS = br._MIN_TF_LEN
QUANTILE_EDGE = 0.25
VOL_LEN = v7.VOL_LEN  # 复用现成的成交量均线长度参数，不新定义

_price_cache: dict[str, pd.DataFrame] = {}


def clean(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=['Close'])


def get_price_history(ticker: str) -> pd.DataFrame:
    if ticker not in _price_cache:
        df = yf.download(ticker, period='max', auto_adjust=True, progress=False)
        _price_cache[ticker] = clean(df)
    return _price_cache[ticker]


@dataclass
class SignalRecord:
    ticker: str
    trigger_date: pd.Timestamp
    resonance_at_trigger: float
    red_ratio_at_trigger: float
    forward_return_60d: float
    excess_vs_klci_60d: float


def load_sweet_spot_signals() -> list[SignalRecord]:
    df = pd.read_csv(SIGNALS_CSV)
    df['date'] = pd.to_datetime(df['date'])
    records = []
    for _, row in df.iterrows():
        records.append(SignalRecord(
            ticker=row['ticker'],
            trigger_date=row['date'],
            resonance_at_trigger=row['resonance'],
            red_ratio_at_trigger=row['red_ratio'],
            forward_return_60d=row['ret_60d'],
            excess_vs_klci_60d=row['exc_60d'],
        ))
    return records


def get_resonance_series(ticker: str, trigger_date: pd.Timestamp,
                          lookback_days: int = LOOKBACK_DAYS) -> pd.Series:
    full_df = get_price_history(ticker)
    if full_df.empty:
        return pd.Series(dtype=float)

    idx = full_df.index.searchsorted(trigger_date)
    if idx >= len(full_df):
        idx = len(full_df) - 1

    start_pos = max(0, idx - lookback_days + 1)
    dates, scores = [], []
    for pos in range(start_pos, idx + 1):
        window = full_df.iloc[:pos + 1]
        if len(window) < MIN_HISTORY_ROWS:
            continue
        score = br.compute_resonance_score(window)
        if score == -999.0:
            continue
        dates.append(full_df.index[pos])
        scores.append(score)

    return pd.Series(scores, index=dates, dtype=float)


def get_volume_ratio(ticker: str, trigger_date: pd.Timestamp) -> float:
    """
    触发日的成交量比 = 当日 Volume / 该股票自己过去 VOL_LEN 日均量。
    直接复用 v7pro_mcdx_scan.py 里 calc_vol_score_series 用的同一套计算，
    这里只取 ratio 部分（不算完整的 vol_score，因为只是拿来当权重，不是新信号）。
    """
    full_df = get_price_history(ticker)
    if full_df.empty:
        return np.nan
    idx = full_df.index.searchsorted(trigger_date)
    if idx >= len(full_df):
        idx = len(full_df) - 1
    if idx < VOL_LEN:
        return np.nan
    vol_ma = full_df['Volume'].rolling(VOL_LEN).mean()
    vr = full_df['Volume'] / vol_ma.replace(0, np.nan)
    val = vr.iloc[idx]
    return float(val) if pd.notna(val) else np.nan


def annihilation_intensity(resonance_series: pd.Series) -> float:
    if len(resonance_series) < 3 or resonance_series.isna().any():
        return np.nan
    y = resonance_series.values
    x = np.arange(len(y))
    slope, _intercept = np.polyfit(x, y, 1)
    return slope


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    mask = values.notna() & weights.notna()
    if mask.sum() == 0:
        return np.nan
    v, w = values[mask], weights[mask]
    if w.sum() == 0:
        return np.nan
    return float((v * w).sum() / w.sum())


def _group_stats(sub: pd.DataFrame) -> dict:
    return {
        "n": len(sub),
        "mean_excess_60d": sub["excess_vs_klci_60d"].mean(),
        "win_rate": (sub["forward_return_60d"] > 0).mean(),
        "vol_weighted_mean_excess_60d": _weighted_mean(sub["excess_vs_klci_60d"], sub["vol_ratio"]),
        "vol_weighted_win_rate": _weighted_mean((sub["forward_return_60d"] > 0).astype(float), sub["vol_ratio"]),
    }


def _concentration_check(sub: pd.DataFrame, label: str):
    counts = sub["ticker"].value_counts()
    n = len(sub)
    top3_tickers = counts.head(3).index.tolist()
    top3_share_count = counts.head(3).sum() / n if n else 0.0

    vol_by_ticker = sub.groupby("ticker")["vol_ratio"].sum()
    total_vol = sub["vol_ratio"].sum()
    top3_share_vol = (vol_by_ticker.reindex(top3_tickers).sum() / total_vol
                       if total_vol and pd.notna(total_vol) else np.nan)

    print(f"  [{label}] n={n}, 不同股票数={len(counts)}")
    print(f"    按信号笔数: 前3只股票占比={top3_share_count:.1%}")
    if pd.notna(top3_share_vol):
        print(f"    按成交量加权: 前3只股票占比={top3_share_vol:.1%}")
        if top3_share_count > 0.30 and top3_share_vol <= 0.30:
            print(f"    → 加权后回到红线以下，说明原本的集中度更多是'反复触发但缩量'造成的统计假象")
        elif top3_share_count > 0.30 and top3_share_vol > 0.30:
            print(f"    → 加权后依然超标，说明这几只股票是真的放量剧烈翻转，不是噪音")
    else:
        print(f"    按成交量加权: 数据不足，无法计算")


def run_backtest():
    signals = load_sweet_spot_signals()
    print(f"共 {len(signals)} 个历史信号，开始重建 resonance 轨迹 + 成交量比...")

    rows = []
    for i, sig in enumerate(signals):
        if (i + 1) % 50 == 0:
            print(f"  处理中... {i + 1}/{len(signals)}")
        series = get_resonance_series(sig.ticker, sig.trigger_date)
        intensity = annihilation_intensity(series)
        zero_slope = bool(len(series) >= 2 and series.max() == series.min())
        vol_ratio = get_volume_ratio(sig.ticker, sig.trigger_date)
        rows.append({
            "ticker": sig.ticker,
            "trigger_date": sig.trigger_date,
            "annihilation_intensity": intensity,
            "zero_slope": zero_slope,
            "vol_ratio": vol_ratio,
            "forward_return_60d": sig.forward_return_60d,
            "excess_vs_klci_60d": sig.excess_vs_klci_60d,
        })

    df = pd.DataFrame(rows).dropna(subset=["annihilation_intensity"])
    print(f"\n成功算出斜率的信号: {len(df)} / {len(signals)}")
    print(f"成功算出成交量比的信号: {df['vol_ratio'].notna().sum()} / {len(df)}")

    zero_share = df["zero_slope"].mean()
    print(f"\n【检查1】回看窗口内完全无变化(斜率=0)的信号占比: {zero_share:.1%}")

    df["sample"] = np.where(
        df["trigger_date"] < pd.Timestamp(IN_SAMPLE_CUTOFF),
        "in_sample", "out_of_sample"
    )

    print("\n" + "=" * 70)
    print(f"【四分位分组 + 成交量加权诊断】(fast = 最快{QUANTILE_EDGE:.0%}, slow = 最慢{QUANTILE_EDGE:.0%})")
    print("=" * 70)
    quartile_rows = []
    for sample_name, sub in df.groupby("sample"):
        lo = sub["annihilation_intensity"].quantile(QUANTILE_EDGE)
        hi = sub["annihilation_intensity"].quantile(1 - QUANTILE_EDGE)
        fast = sub[sub["annihilation_intensity"] >= hi]
        slow = sub[sub["annihilation_intensity"] <= lo]
        fs, ss = _group_stats(fast), _group_stats(slow)
        quartile_rows.append({
            "sample": sample_name,
            "n_fast": fs["n"], "n_slow": ss["n"],
            "fast_mean_excess_60d": fs["mean_excess_60d"],
            "slow_mean_excess_60d": ss["mean_excess_60d"],
            "fast_win_rate": fs["win_rate"], "slow_win_rate": ss["win_rate"],
            "fast_volw_mean_excess_60d": fs["vol_weighted_mean_excess_60d"],
            "slow_volw_mean_excess_60d": ss["vol_weighted_mean_excess_60d"],
            "fast_volw_win_rate": fs["vol_weighted_win_rate"],
            "slow_volw_win_rate": ss["vol_weighted_win_rate"],
        })
        print(f"\n-- {sample_name} --")
        _concentration_check(fast, "fast (最快25%)")
        _concentration_check(slow, "slow (最慢25%)")

    print()
    print(pd.DataFrame(quartile_rows).to_string(index=False))

    print("\n" + "=" * 70)
    print("解读方式（不是重新判定假设是否成立，v2的放弃结论不变）：")
    print("  - 只是用来看：v2里那个'前3只股票占比67-79%'的集中度问题，")
    print("    加权后是被稀释了（统计假象），还是依然存在（真实现象）")
    print("  - 加权前后的超额收益/胜率差异，也可以顺便看出'量'这个维度")
    print("    单独摆在这里大概长什么样子——但这不构成对'量'的正式验证，")
    print("    真正要不要把量纳入信号体系，仍按原计划等 monthly double-attack")
    print("    样本外结果(~2026年10月)出来后再说")
    print("=" * 70)

    df.to_csv("annihilation_intensity_signals.csv", index=False)
    pd.DataFrame(quartile_rows).to_csv("annihilation_intensity_quartile_volweighted_summary.csv", index=False)
    print("\n已保存: annihilation_intensity_signals.csv / "
          "annihilation_intensity_quartile_volweighted_summary.csv")


if __name__ == "__main__":
    run_backtest()
