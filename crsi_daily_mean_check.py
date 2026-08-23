# -*- coding: utf-8 -*-
"""
crsi_daily_mean_check.py

快速查看：日线CRSI的20日滚动均值，用在刚才 unified_scan_20260807_1401.csv
里那7支股票上。纯观察用途，不是新的独立验证线——只是看看这个数字长什么样,
不代表已经验证过它有预测力。

运行方式:
    cd ~/Documents/PlanB_Scanner
    python3 crsi_daily_mean_check.py
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

TICKERS = ["6947.KL", "4863.KL", "6012.KL", "6888.KL", "5031.KL", "0172.KL", "9431.KL"]


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
    print("=" * 78)
    print(f"日线CRSI + {DAILY_MEAN_WINDOW}日滚动均值 快速查看")
    print("=" * 78)
    for t in TICKERS:
        try:
            df = clean(yf.download(t, period="2y", auto_adjust=True, progress=False))
            if df.empty or len(df) < ROC_RANK_PERIOD + 30:
                print(f"{t}: 数据不足")
                continue
            crsi_daily = calc_crsi_daily(df['Close'])
            crsi_mean = crsi_daily.rolling(DAILY_MEAN_WINDOW).mean()

            last_crsi = crsi_daily.iloc[-1]
            last_mean = crsi_mean.iloc[-1]
            mean_5d_ago = crsi_mean.iloc[-6] if len(crsi_mean) > 6 else np.nan
            trend = "↑上升" if pd.notna(mean_5d_ago) and last_mean > mean_5d_ago else "↓下降/持平"

            bias = "偏多头动能" if last_mean > 50 else "偏空头动能"
            print(f"{t:<10} 最新日CRSI={last_crsi:>5.1f}  {DAILY_MEAN_WINDOW}日均值={last_mean:>5.1f} "
                  f"({bias}, 5日内{trend})")
        except Exception as e:
            print(f"{t}: 错误 {e}")


if __name__ == "__main__":
    main()

