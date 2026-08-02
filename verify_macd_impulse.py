#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_macd_impulse.py —— 验证"MACD Impulse绿色柱"信号是否真的有效
"""

import warnings
warnings.filterwarnings('ignore')

import sys
import time
import random
import yfinance as yf
import pandas as pd
import numpy as np


def build_session():
    try:
        from curl_cffi import requests as cffi_requests
        return cffi_requests.Session(impersonate="chrome")
    except Exception:
        return None

SESSION = build_session()


def fetch(symbol, period='5y'):
    ticker = yf.Ticker(symbol, session=SESSION) if SESSION else yf.Ticker(symbol)
    df = ticker.history(period=period, timeout=20, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=['Close'])


def calc_macd_impulse_series(close, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast).mean()
    ema_slow = close.ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    hist = macd_line - signal_line
    hist_prev = hist.shift(1)

    state = pd.Series('blue', index=close.index)
    state[(hist > 0) & (hist > hist_prev)] = 'green'
    state[(hist < 0) & (hist < hist_prev)] = 'red'
    return state


def collect_signals(symbol):
    df = fetch(symbol)
    if df is None or len(df) < 100:
        return []

    close = df['Close']
    state = calc_macd_impulse_series(close)

    records = []
    n = len(close)
    for i in range(35, n - 60):
        s = state.iloc[i]
        c0 = float(close.iloc[i])
        c20 = float(close.iloc[i + 20])
        c60 = float(close.iloc[i + 60])
        ret_20d = (c20 - c0) / c0 * 100
        ret_60d = (c60 - c0) / c0 * 100
        records.append({'symbol': symbol, 'date': close.index[i], 'state': s,
                         'ret_20d': ret_20d, 'ret_60d': ret_60d})
    return records


def main():
    symbols = sys.argv[1:]
    if not symbols:
        print("用法：python3 verify_macd_impulse.py 股票代码1 股票代码2 ...")
        return

    print("=" * 90)
    print(f"验证 MACD Impulse 信号有效性  |  股票数：{len(symbols)}")
    print("=" * 90)

    all_records = []
    for i, sym in enumerate(symbols, 1):
        print(f"[{i}/{len(symbols)}] {sym} ...", end=" ", flush=True)
        try:
            recs = collect_signals(sym)
            all_records.extend(recs)
            print(f"OK  {len(recs)}条记录")
        except Exception as e:
            print(f"跳过（{type(e).__name__}: {str(e)[:50]}）")
        time.sleep(1.5 + random.uniform(0, 1.0))

    if not all_records:
        print("\n没有任何有效数据。")
        return

    df = pd.DataFrame(all_records)
    print(f"\n总记录数：{len(df)}（同一股票每天都算一条，天然存在自相关，仅供参考不是独立样本）")

    print("\n" + "=" * 90)
    print("按 MACD Impulse 状态分组表现")
    print("=" * 90)
    print(f"{'状态':<10}{'记录数':>10}{'胜率(20d)':>12}{'中位收益(20d)':>16}{'胜率(60d)':>12}{'中位收益(60d)':>16}")
    print("-" * 90)

    for state in ['green', 'blue', 'red']:
        sub = df[df['state'] == state]
        if len(sub) == 0:
            continue
        win20 = (sub['ret_20d'] > 0).mean() * 100
        med20 = sub['ret_20d'].median()
        win60 = (sub['ret_60d'] > 0).mean() * 100
        med60 = sub['ret_60d'].median()
        print(f"{state:<10}{len(sub):>10}{win20:>11.1f}%{med20:>15.2f}%{win60:>11.1f}%{med60:>15.2f}%")

    print("\n" + "=" * 90)
    print("解读：")
    print("若 green 组胜率/中位收益明显高于 blue 组(尤其是60天)，说明这个信号有一定预测力，")
    print("值得考虑正式纳入 unified_scanner.py。")
    print("若差不多甚至更差，说明'起飞三脚印'里 MACD 绿色柱+2.5分 这个权重是没有依据的，")
    print("不建议采纳，跟之前验证'红满紫高'不成立是同一类结论。")
    print("注意：本次样本存在同股票逐日高度相关的问题(不是511信号库那种独立事件)，")
    print("结论只能当参考，不能跟甜蜜点0.60-0.85那种严谨回测的可信度相提并论。")
    print("=" * 90)


if __name__ == "__main__":
    main()
