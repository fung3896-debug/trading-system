# -*- coding: utf-8 -*-
"""
antimatter_squeeze_backtest.py

独立策略回测：波动率挤压突破（"反物质"框架的技术分析版本）。

⚠️ 定位澄清：这跟 Plan B 主线（MCDX 资金结构状态识别）是完全独立的策略，
不共享信号、不共享验证结果，也不写入任何 Plan B 生产脚本。这条支线现在
就跑；Plan B 的成交量模块研究仍按原计划延到 monthly double-attack 样本外
验证完成（预计~2026年10月）。

修复了原版代码的三个问题：
  1. 方向确认对齐错位：原代码对 annihilation_up 做了 shift(1)，
     导致实际比较的是"湮灭后第2天"而不是"湮灭后第1天"的方向确认，
     错位了一天。这里改成不对信号本身shift，而是直接用 shift(-1)
     把次日收盘价带到当天这一行来比较，逻辑对齐。
  2. 入场价用了信号确认当天的收盘价（该价格本身正是确认信号用到的数据
     之一），有前视偏差、实盘执行不了。改成信号确认后"次日开盘价"入场。
  3. 6个月数据 + 50日回顾窗口，实际能测的窗口只剩约3个月，19支股票下
     信号数大概率是个位数，做胜率统计没有意义。改成用长历史（period='max'，
     和 Plan B 511-signal 回测保持一致的做法），并加了 KLCI 超额收益对比、
     in-sample/out-of-sample 切分，让这套支线也能用跟 Plan B 一样的
     稳健性标准去检验。

运行方式:
    cd ~/Documents/PlanB_Scanner
    python3 antimatter_squeeze_backtest.py
"""

import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import yfinance as yf

# ---- config -------------------------------------------------------------
# TODO: 换成你实际的 watchlist（跟 v7pro_mcdx_scan.py / planb_daily_scan.py
# 里 TICKERS 变量保持一致，直接复制过来，不要重新手打一份新清单）
TICKERS = ['7233.KL', '5211.KL', '8907.KL', '6459.KL', '5249.KL', '5026.KL',
           '5286.KL', '0225.KL', '0099.KL', '5031.KL', '5681.KL', '7163.KL',
           '8869.KL', '1066.KL', '0215.KL', '7103.KL', '5263.KL',
           '4863.KL', '5243.KL', '5142.KL']
NAME_MAP = {}  # 可选：ticker -> 中文名，不填就直接显示ticker

BB_PERIOD = 20
BB_STD = 2.0
SQUEEZE_LOOKBACK = 50
VOL_EXPAND_RATIO = 2.0
HOLD_DAYS = 5
BENCHMARK_TICKER = "^KLSE"
IN_SAMPLE_CUTOFF = "2020-01-01"  # 数据量比511信号那份少很多，先用粗略中点，
                                   # 真正切分点等看到实际信号日期分布后再调整


def fetch(ticker: str) -> pd.DataFrame:
    df = yf.download(ticker, period="max", auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=['Close'])


def get_benchmark_return(bench: pd.DataFrame, entry_date, hold_days: int) -> float:
    """入场日之后 hold_days 个交易日的 KLCI 涨跌幅，用来算超额收益"""
    idx = bench.index.searchsorted(entry_date)
    if idx + hold_days >= len(bench):
        return np.nan
    entry_px = bench['Close'].iloc[idx]
    exit_px = bench['Close'].iloc[idx + hold_days]
    return float((exit_px - entry_px) / entry_px)


def run_backtest():
    if not TICKERS:
        print("⚠️ TICKERS 列表是空的，先把你的 watchlist 填进 config 部分再跑")
        return

    print("=" * 80)
    print("反物质策略 - 波动率挤压突破测试 (已修复对齐/入场/样本量问题)")
    print("=" * 80)

    bench = fetch(BENCHMARK_TICKER)

    signals = []
    for ticker in TICKERS:
        name = NAME_MAP.get(ticker, ticker)
        try:
            df = fetch(ticker)
            if df.empty or len(df) < SQUEEZE_LOOKBACK + 10:
                continue

            close, high, low, volume = df['Close'], df['High'], df['Low'], df['Volume']

            # ---- 1. 磁阱 ----
            bb_mid = close.rolling(BB_PERIOD).mean()
            bb_std = close.rolling(BB_PERIOD).std()
            bb_upper = bb_mid + BB_STD * bb_std
            bb_lower = bb_mid - BB_STD * bb_std
            bb_width = (bb_upper - bb_lower) / bb_mid
            bb_width_min = bb_width.rolling(SQUEEZE_LOOKBACK).min()
            in_squeeze = bb_width <= bb_width_min

            # ---- 2. 湮灭事件 ----
            vol_ma20 = volume.rolling(20).mean()
            break_upper = (close > bb_upper) & in_squeeze
            break_lower = (close < bb_lower) & in_squeeze
            vol_surge = volume > vol_ma20 * VOL_EXPAND_RATIO
            annihilation_up = break_upper & vol_surge
            annihilation_down = break_lower & vol_surge

            # ---- 3. 光子喷射（方向确认，对齐修复版） ----
            # 不对 annihilation 信号做 shift；直接把"次日收盘"带到当天这一行来比较，
            # 这样 photon_up[t] 的含义就是"t日发生湮灭，且t+1日收盘确认了方向"
            next_close = close.shift(-1)
            photon_up = annihilation_up & (next_close > high)
            photon_down = annihilation_down & (next_close < low)

            trade_signal = (photon_up | photon_down)
            signal_positions = np.where(trade_signal.values)[0]

            for pos in signal_positions:
                # 信号在 pos 日确认（需要 pos+1 日收盘数据才能确认），
                # 入场统一放在 pos+2 日的开盘价，避免用到"确认信号那天"的收盘价
                entry_pos = pos + 2
                exit_pos = entry_pos + HOLD_DAYS
                if exit_pos >= len(df):
                    continue

                direction = '多头' if photon_up.iloc[pos] else '空头'
                entry_price = df['Open'].iloc[entry_pos]
                exit_price = df['Close'].iloc[exit_pos]
                pnl_pct = (exit_price - entry_price) / entry_price
                if direction == '空头':
                    pnl_pct = -pnl_pct

                entry_date = df.index[entry_pos]
                bench_ret = get_benchmark_return(bench, entry_date, HOLD_DAYS)
                excess = pnl_pct - bench_ret if pd.notna(bench_ret) else np.nan

                signals.append({
                    '名称': name, '代码': ticker,
                    '信号日期': df.index[pos].strftime('%Y-%m-%d'),
                    '入场日期': entry_date.strftime('%Y-%m-%d'),
                    '方向': direction,
                    '入场价': round(float(entry_price), 3),
                    '出场价': round(float(exit_price), 3),
                    '持仓天数': HOLD_DAYS,
                    '盈亏%': round(pnl_pct * 100, 2),
                    '超额收益%': round(excess * 100, 2) if pd.notna(excess) else np.nan,
                    '突破类型': '突破上轨' if break_upper.iloc[pos] else '突破下轨',
                    'sample': 'in_sample' if entry_date < pd.Timestamp(IN_SAMPLE_CUTOFF) else 'out_of_sample',
                })
        except Exception as e:
            print(f"  {name} 回测错误: {e}")
            continue

    if not signals:
        print("\n未产生任何交易信号，可能原因：")
        print("1. 无股票出现波动率挤压状态")
        print("2. 挤压后的突破未伴随成交量放大")
        print("3. 突破后次日方向确认失败")
        return

    df_signals = pd.DataFrame(signals)
    print(f"\n总信号数: {len(df_signals)}")
    if len(df_signals) < 30:
        print("⚠️ 信号数低于30，统计量（胜率/盈亏比）参考价值有限，先当探索性结果看")

    print(f"整体胜率: {(df_signals['盈亏%'] > 0).mean():.1%}")
    print(f"整体平均超额收益: {df_signals['超额收益%'].mean():.2f}%")

    print("\n分 in/out-of-sample:")
    print(df_signals.groupby('sample').agg(
        信号数=('盈亏%', 'count'),
        胜率=('盈亏%', lambda x: (x > 0).mean()),
        平均超额收益=('超额收益%', 'mean'),
    ).round(3).to_string())

    print("\n按股票分组表现:")
    print(df_signals.groupby('名称').agg(
        信号次数=('盈亏%', 'count'),
        胜率=('盈亏%', lambda x: (x > 0).mean()),
        平均超额收益=('超额收益%', 'mean'),
    ).round(3).to_string())

    df_signals.to_csv("antimatter_squeeze_signals.csv", index=False)
    print("\n已保存: antimatter_squeeze_signals.csv")


if __name__ == "__main__":
    run_backtest()
