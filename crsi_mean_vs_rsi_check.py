# -*- coding: utf-8 -*-
"""
crsi_mean_vs_rsi_check.py

快速检查："CRSI日线20日滚动均值" 跟 "传统RSI(14)" 到底有多像。
如果相关性很高，说明这个均值是冗余的，不用再单独验证；
如果相关性不高，说明确实抓到了传统RSI抓不到的东西，才值得往下测。

纯粹是个诊断性检查，不是新的独立验证线。

运行方式:
    cd ~/Documents/PlanB_Scanner
    python3 crsi_mean_vs_rsi_check.py
"""

import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import yfinance as yf

RSI_SHORT = 3
STREAK_RSI_PERIOD = 2
ROC_RANK_PERIOD = 100
DAILY_MEAN_WINDOW = 20
TRADITIONAL_RSI_PERIOD = 14

TICKERS = ["8869.KL", "7095.KL", "7172.KL", "3034.KL", "2852.KL",
           "6947.KL", "4863.KL", "6012.KL", "6888.KL", "5031.KL"]


def clean(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=['Close'])


def calc_rsi_wilder(close, length):
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))


def calc_streak(close):
    direction = np.sign(close.diff())
    streak = pd.Series(0.0, index=close.index)
    cur, prev_dir = 0.0, 0.0
    for i, d in enumerate(direction.values):
        if pd.isna(d) or d == 0:
            cur = 0.0
        elif d == prev_dir or (cur == 0 and d != 0):
            cur = cur + d if cur != 0 else d
        else:
            cur = d
        streak.iloc[i] = cur
        prev_dir = d if d != 0 else prev_dir
    return streak


def percentile_rank(series, window):
    def _rank(x):
        if len(x) < 2:
            return np.nan
        return (x < x.iloc[-1]).sum() / (len(x) - 1) * 100
    return series.rolling(window).apply(_rank, raw=False)


def calc_crsi_daily(close):
    rsi_c = calc_rsi_wilder(close, RSI_SHORT)
    streak_c = calc_rsi_wilder(calc_streak(close), STREAK_RSI_PERIOD)
    roc_c = percentile_rank(close.pct_change(1) * 100, ROC_RANK_PERIOD)
    return (rsi_c + streak_c + roc_c) / 3.0


def main():
    print("=" * 70)
    print("检查: CRSI日线20日均值 vs 传统RSI(14) 相关性")
    print("=" * 70)

    all_corrs = []
    for t in TICKERS:
        try:
            df = clean(yf.download(t, period="2y", auto_adjust=True, progress=False))
            if df.empty or len(df) < ROC_RANK_PERIOD + 30:
                continue
            crsi_daily = calc_crsi_daily(df['Close'])
            crsi_mean = crsi_daily.rolling(DAILY_MEAN_WINDOW).mean()
            rsi14 = calc_rsi_wilder(df['Close'], TRADITIONAL_RSI_PERIOD)

            combined = pd.DataFrame({'crsi_mean': crsi_mean, 'rsi14': rsi14}).dropna()
            if len(combined) < 30:
                continue
            corr = combined['crsi_mean'].corr(combined['rsi14'])
            all_corrs.append(corr)
            print(f"{t:<10} 相关系数 = {corr:.3f}")
        except Exception as e:
            print(f"{t}: 错误 {e}")

    if all_corrs:
        avg_corr = np.mean(all_corrs)
        print(f"\n平均相关系数: {avg_corr:.3f}")
        if avg_corr > 0.85:
            print("→ 相关性非常高：CRSI均值基本上就是换了个复杂公式的RSI(14)，")
            print("  确认是冗余的，不用再单独验证这个方向")
        elif avg_corr > 0.6:
            print("→ 中等相关：有重叠但不完全一样，可能有一部分独特信息，")
            print("  但价值有限，优先级应该排在CRSI主线之后")
        else:
            print("→ 相关性不算高：CRSI均值确实在测不一样的东西，")
            print("  可能值得之后正式排期验证")


if __name__ == "__main__":
    main()

