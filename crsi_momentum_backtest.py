# -*- coding: utf-8 -*-
"""
crsi_momentum_backtest.py

独立新信号测试（v2，动能持续版，不是超卖反弹版）：
    周线CRSI连续两周达到80以上 = 强势动能确认信号
    同期月线CRSI是否也达到80以上 = 是否有更高时间框架的确认

这跟经典Connors用法（CRSI<10抄底）方向相反——这里测的是"强者恒强、
顺势而为"的持续性逻辑，思路上更接近Plan B主线（MCDX看的也是持续性，
只是资金结构状态而不是动能强度）。

分两组对比:
    A组: 只有周线连续两周≥80(不管月线)
    B组: 周线连续两周≥80 且 当月月线CRSI也≥80(双重确认)
比较两组后续4/8/12周表现，看"月线确认"这层有没有额外贡献。

用市值前50大工业股(已用get_top50_by_marketcap.py在Colab筛选出来)，
不用220支全量,是因为你想先看这个更聚焦、流动性更好的子集表现如何。
⚠️ 50支股票比220支更容易有集中度问题,这版会照样做集中度检查。

运行方式:
    cd ~/Documents/PlanB_Scanner
    python3 crsi_momentum_backtest.py
"""

import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import yfinance as yf

# ---- config -------------------------------------------------------------
RSI_SHORT = 3
STREAK_RSI_PERIOD = 2
ROC_RANK_PERIOD = 100
STRONG_TH = 80.0          # 强势动能阈值(不是超卖,是超强)
CONSEC_WEEKS = 2           # 周线连续达标周数
HOLD_WEEKS_LIST = [4, 8, 12]
BENCHMARK_TICKER = "^KLSE"
IN_SAMPLE_CUTOFF = "2016-08-14"

# 市值前50大工业股 (2026年8月用get_top50_by_marketcap.py在Colab筛选)
TICKERS = [
    '8869.KL', '5183.KL', '5211.KL', '3794.KL', '0151.KL', '5273.KL', '5340.KL', '3034.KL',
    '4731.KL', '0270.KL', '7172.KL', '0225.KL', '5151.KL', '9822.KL', '5330.KL', '5000.KL',
    '3476.KL', '5916.KL', '8907.KL', '5327.KL', '7233.KL', '3395.KL', '7100.KL', '2852.KL',
    '5271.KL', '6963.KL', '5302.KL', '4758.KL', '7241.KL', '6971.KL', '5317.KL', '6491.KL',
    '0099.KL', '0161.KL', '0291.KL', '5284.KL', '5001.KL', '7095.KL', '7034.KL', '5665.KL',
    '7231.KL', '5015.KL', '7197.KL', '7609.KL', '5125.KL', '6874.KL', '7155.KL', '5298.KL',
    '5308.KL', '0196.KL',
]


def clean(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=['Close'])


def fetch(ticker: str) -> pd.DataFrame:
    df = yf.download(ticker, period="max", auto_adjust=True, progress=False)
    return clean(df)


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = pd.DataFrame({
        'Open': df['Open'].resample(rule).first(),
        'High': df['High'].resample(rule).max(),
        'Low': df['Low'].resample(rule).min(),
        'Close': df['Close'].resample(rule).last(),
        'Volume': df['Volume'].resample(rule).sum(),
    })
    return agg.dropna(subset=['Close'])


def calc_rsi_wilder(close: pd.Series, length: int) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))


def calc_streak(close: pd.Series) -> pd.Series:
    direction = np.sign(close.diff())
    streak = pd.Series(0.0, index=close.index)
    cur = 0.0
    prev_dir = 0.0
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


def percentile_rank(series: pd.Series, window: int) -> pd.Series:
    def _rank(x):
        if len(x) < 2:
            return np.nan
        return (x < x.iloc[-1]).sum() / (len(x) - 1) * 100
    return series.rolling(window).apply(_rank, raw=False)


def calc_crsi(ohlcv_df: pd.DataFrame) -> pd.Series:
    close = ohlcv_df['Close']
    rsi_component = calc_rsi_wilder(close, RSI_SHORT)
    streak = calc_streak(close)
    streak_rsi_component = calc_rsi_wilder(streak, STREAK_RSI_PERIOD)
    roc1 = close.pct_change(1) * 100
    roc_rank_component = percentile_rank(roc1, ROC_RANK_PERIOD)
    return (rsi_component + streak_rsi_component + roc_rank_component) / 3.0


def get_benchmark_weekly() -> pd.DataFrame:
    df = fetch(BENCHMARK_TICKER)
    return resample_ohlcv(df, 'W')


def forward_return(close: pd.Series, pos: int, weeks: int):
    if pos + weeks >= len(close):
        return np.nan
    return float((close.iloc[pos + weeks] - close.iloc[pos]) / close.iloc[pos])


def run_backtest():
    print("=" * 78)
    print(f"周线CRSI动能持续测试 (连续{CONSEC_WEEKS}周≥{STRONG_TH:.0f} + 月线确认对比)")
    print("=" * 78)

    bench_weekly = get_benchmark_weekly()
    bench_close = bench_weekly['Close']

    rows = []
    for i, ticker in enumerate(TICKERS):
        if (i + 1) % 15 == 0:
            print(f"  处理中... {i + 1}/{len(TICKERS)}")
        try:
            df = fetch(ticker)
            if df.empty or len(df) < 400:
                continue
            weekly = resample_ohlcv(df, 'W')
            monthly = resample_ohlcv(df, 'ME')
            if len(weekly) < ROC_RANK_PERIOD + 20 or len(monthly) < ROC_RANK_PERIOD + 20:
                continue

            crsi_w = calc_crsi(weekly)
            crsi_m = calc_crsi(monthly)
            close_w = weekly['Close']

            # 周线连续 CONSEC_WEEKS 周 >= STRONG_TH
            above = crsi_w >= STRONG_TH
            consec_ok = above.rolling(CONSEC_WEEKS).sum() == CONSEC_WEEKS
            sig_positions = np.where(consec_ok.values)[0]

            for pos in sig_positions:
                signal_date = weekly.index[pos]

                # 找同期(该周所在月份)的月线CRSI值
                m_pos = crsi_m.index.searchsorted(signal_date)
                if m_pos >= len(crsi_m):
                    m_pos = len(crsi_m) - 1
                monthly_confirmed = bool(crsi_m.iloc[m_pos] >= STRONG_TH) if not pd.isna(crsi_m.iloc[m_pos]) else False

                bench_pos = bench_close.index.searchsorted(signal_date)

                row = {
                    'ticker': ticker,
                    'signal_date': signal_date,
                    'crsi_weekly': crsi_w.iloc[pos],
                    'crsi_monthly': crsi_m.iloc[m_pos] if not pd.isna(crsi_m.iloc[m_pos]) else np.nan,
                    'monthly_confirmed': monthly_confirmed,
                }
                ok = True
                for wk in HOLD_WEEKS_LIST:
                    stock_ret = forward_return(close_w, pos, wk)
                    bench_ret = forward_return(bench_close, bench_pos, wk)
                    if pd.isna(stock_ret) or pd.isna(bench_ret):
                        ok = False
                        break
                    row[f'ret_{wk}w'] = stock_ret
                    row[f'exc_{wk}w'] = stock_ret - bench_ret
                if ok:
                    rows.append(row)
        except Exception as e:
            print(f"  {ticker} 错误: {e}")
            continue

    if not rows:
        print("\n未产生任何信号。")
        return

    df_sig = pd.DataFrame(rows)
    df_sig['sample'] = np.where(
        df_sig['signal_date'] < pd.Timestamp(IN_SAMPLE_CUTOFF), 'in_sample', 'out_of_sample'
    )

    print(f"\n总信号数: {len(df_sig)}  |  其中月线也确认(双确认): {df_sig['monthly_confirmed'].sum()}")
    if len(df_sig) < 30:
        print("⚠️ 总信号数低于30，统计量参考价值有限")

    unique_tickers = df_sig['ticker'].nunique()
    top3_share = df_sig['ticker'].value_counts().head(3).sum() / len(df_sig)
    print(f"不同股票数: {unique_tickers}  前3只股票占比: {top3_share:.1%}"
          + ("  ⚠️ 超过30%集中度红线" if top3_share > 0.30 else ""))

    print("\n" + "=" * 78)
    print("A组: 仅周线确认(不管月线) vs B组: 周线+月线双确认")
    print("=" * 78)
    for wk in HOLD_WEEKS_LIST:
        print(f"\n-- 持有 {wk} 周 --")
        for sample_name, sub in df_sig.groupby('sample'):
            group_a = sub  # 全部(仅周线口径,不筛月线)
            group_b = sub[sub['monthly_confirmed']]
            wa = (group_a[f'ret_{wk}w'] > 0).mean()
            ea = group_a[f'exc_{wk}w'].mean()
            if len(group_b) > 0:
                wb = (group_b[f'ret_{wk}w'] > 0).mean()
                eb = group_b[f'exc_{wk}w'].mean()
                print(f"  [{sample_name}] A组(n={len(group_a)}) 胜率={wa:.1%} 超额={ea:.2%}  |  "
                      f"B组双确认(n={len(group_b)}) 胜率={wb:.1%} 超额={eb:.2%}")
            else:
                print(f"  [{sample_name}] A组(n={len(group_a)}) 胜率={wa:.1%} 超额={ea:.2%}  |  "
                      f"B组双确认(n=0) 无样本")

    print("\n" + "=" * 78)
    print("判定标准（跑之前定好）：")
    print("  1. A组(仅周线)本身，至少一个持有周期在in/out-of-sample两边都要")
    print("     胜率>55%且超额收益>0，否则这个信号本身不成立，不用再看月线加成")
    print("  2. 若A组成立，再看B组(双确认)是否显著优于A组——如果优于，月线")
    print("     确认这层有价值；如果差不多甚至更差，月线是多余的过滤")
    print("  3. 集中度不能超30%红线")
    print("=" * 78)

    df_sig.to_csv("crsi_momentum_signals.csv", index=False)
    print("\n已保存: crsi_momentum_signals.csv")


if __name__ == "__main__":
    run_backtest()
