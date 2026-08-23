# -*- coding: utf-8 -*-
"""
crsi_dwm_check.py

快速检查：CRSI 日/周/月三个时间框架各自算出来,取平均(CRSI-DWM均值)，
这个数字跟两样东西比像不像：
    1. 传统RSI(14) —— 排除"只是换个复杂公式的普通RSI"这种冗余可能
    2. 你系统已有的resonance(MCDX日周月三重共振，取最小值) —— 排除
       "只是用CRSI重新发现了MCDX已经在做的事"这种冗余可能

如果两个相关性都不算太高，说明CRSI-DWM均值可能真的抓到了不一样的东西，
才值得往下正式测试后续收益表现。

运行方式:
    cd ~/Documents/PlanB_Scanner
    python3 crsi_dwm_check.py
"""

import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import yfinance as yf

import v7pro_mcdx_scan as v7
import planb_bridge as br

RSI_SHORT = 3
STREAK_RSI_PERIOD = 2
ROC_RANK_PERIOD = 100
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


def calc_crsi(close):
    rsi_c = calc_rsi_wilder(close, RSI_SHORT)
    streak_c = calc_rsi_wilder(calc_streak(close), STREAK_RSI_PERIOD)
    roc_c = percentile_rank(close.pct_change(1) * 100, ROC_RANK_PERIOD)
    return (rsi_c + streak_c + roc_c) / 3.0


def resample_ohlcv(df, rule):
    agg = pd.DataFrame({
        'Open': df['Open'].resample(rule).first(),
        'High': df['High'].resample(rule).max(),
        'Low': df['Low'].resample(rule).min(),
        'Close': df['Close'].resample(rule).last(),
        'Volume': df['Volume'].resample(rule).sum(),
    })
    return agg.dropna(subset=['Close'])


def main():
    print("=" * 78)
    print("检查: CRSI-DWM均值(日周月三个CRSI取平均) 与 RSI14 / resonance 的相关性")
    print("=" * 78)

    corr_vs_rsi14 = []
    corr_vs_resonance = []

    for t in TICKERS:
        try:
            df = clean(yf.download(t, period="max", auto_adjust=True, progress=False))
            if df.empty or len(df) < 400:
                continue
            weekly = resample_ohlcv(df, 'W')
            monthly = resample_ohlcv(df, 'ME')
            if len(weekly) < ROC_RANK_PERIOD + 20 or len(monthly) < ROC_RANK_PERIOD + 20:
                continue

            crsi_d = calc_crsi(df['Close'])
            crsi_w = calc_crsi(weekly['Close'])
            crsi_m = calc_crsi(monthly['Close'])

            # 把周线/月线CRSI对齐到日线索引(用当天能看到的最新一根周/月K线的值)
            crsi_w_aligned = crsi_w.reindex(df.index, method='ffill')
            crsi_m_aligned = crsi_m.reindex(df.index, method='ffill')

            crsi_dwm_avg = (crsi_d + crsi_w_aligned + crsi_m_aligned) / 3.0

            # 传统RSI14
            rsi14 = calc_rsi_wilder(df['Close'], TRADITIONAL_RSI_PERIOD)

            # 你系统已有的resonance(逐日重算成本较高，这里用滚动窗口近似)
            # 为控制运行时间，这里改用每20个交易日取一个点来算resonance，做粗略相关性估计
            sample_positions = range(br._MIN_TF_LEN, len(df), 20)
            reson_vals, reson_dates = [], []
            for pos in sample_positions:
                window = df.iloc[:pos+1]
                score = br.compute_resonance_score(window)
                if score != -999.0:
                    reson_vals.append(score)
                    reson_dates.append(df.index[pos])
            reson_series = pd.Series(reson_vals, index=reson_dates)

            combined = pd.DataFrame({'crsi_dwm': crsi_dwm_avg, 'rsi14': rsi14}).dropna()
            c1 = combined['crsi_dwm'].corr(combined['rsi14']) if len(combined) > 30 else np.nan

            combined2 = pd.DataFrame({'crsi_dwm': crsi_dwm_avg}).join(reson_series.rename('resonance'), how='inner').dropna()
            c2 = combined2['crsi_dwm'].corr(combined2['resonance']) if len(combined2) > 10 else np.nan

            if pd.notna(c1):
                corr_vs_rsi14.append(c1)
            if pd.notna(c2):
                corr_vs_resonance.append(c2)

            print(f"{t:<10} vs RSI14: {c1:.3f}   vs resonance(采样估计): {c2:.3f}" if pd.notna(c2) else
                  f"{t:<10} vs RSI14: {c1:.3f}   vs resonance: 数据不足")
        except Exception as e:
            print(f"{t}: 错误 {e}")

    print("\n" + "=" * 78)
    if corr_vs_rsi14:
        print(f"平均相关系数 (vs RSI14): {np.mean(corr_vs_rsi14):.3f}")
    if corr_vs_resonance:
        print(f"平均相关系数 (vs resonance, 采样估计): {np.mean(corr_vs_resonance):.3f}")
    print("=" * 78)
    print("判断参考: 两个相关系数如果都明显低于之前日线均值那次的0.812，")
    print("说明CRSI-DWM均值确实是不一样的东西，值得往下正式测试收益表现")


if __name__ == "__main__":
    main()
