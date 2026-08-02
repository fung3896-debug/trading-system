#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diagnose_banker_noise.py —— 逐月 banker/hot 数值检查
============================================================
独立诊断脚本，不改动 unified_scanner.py / v7pro_mcdx_scan.py /
planb_bridge.py 任何核心逻辑，只读取、展示、判断。

用法：
    python3 diagnose_banker_noise.py 0097.KL 5292.KL 3867.KL
"""

import warnings
warnings.filterwarnings('ignore')

import sys
import yfinance as yf
import pandas as pd

import v7pro_mcdx_scan as v7
import planb_bridge as bridge

NOISE_GAP = 2.0
PERIOD = '7y'


def build_session():
    try:
        from curl_cffi import requests as cffi_requests
        return cffi_requests.Session(impersonate="chrome")
    except Exception:
        return None

SESSION = build_session()


def fetch(symbol):
    ticker = yf.Ticker(symbol, session=SESSION) if SESSION else yf.Ticker(symbol)
    df = ticker.history(period=PERIOD, timeout=20, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=['Close'])


def diagnose(symbol):
    df = fetch(symbol)
    if df is None or len(df) < bridge._MIN_TF_LEN:
        print(f"{symbol}  数据不足，跳过")
        return

    monthly = v7.resample_ohlcv(df, 'ME')
    banker, hot, retail, dominant, mcdx_score = v7.calc_mcdx_series(monthly['Close'])

    last18 = monthly.index[-18:]
    b18 = banker.reindex(last18)
    h18 = hot.reindex(last18)
    d18 = dominant.reindex(last18)

    dom_label = {0: '庄家', 1: '游资', 2: '散户', -1: 'N/A'}

    print(f"\n{'='*78}")
    print(f"{symbol}  过去18个月 banker/hot 逐月明细")
    print(f"{'='*78}")
    print(f"{'月份':<10}{'banker':>8}{'hot':>8}{'差距':>8}{'当月dominant':>14}   备注")
    print("-" * 78)

    noise_months = 0
    flip_count = 0
    prev_dom = None

    for date in last18:
        b = b18.loc[date]
        h = h18.loc[date]
        d = d18.loc[date]
        gap = abs(b - h)
        is_noise = gap < NOISE_GAP and (b >= v7.STRONG_TH - 3 or h >= v7.STRONG_TH - 3)
        note = ""
        if is_noise:
            note = "⚠️ 临界(贴身)"
            noise_months += 1
        if prev_dom is not None and d != prev_dom and d != -1 and prev_dom != -1:
            note += "  🔀翻转"
            flip_count += 1
        prev_dom = d

        print(f"{date.strftime('%Y-%m'):<10}{b:>8.1f}{h:>8.1f}{gap:>8.1f}"
              f"{dom_label.get(int(d), 'N/A'):>14}   {note}")

    red_ratio_actual = float((d18 == 0).mean())
    print("-" * 78)
    print(f"临界(贴身)月数：{noise_months}/18   dominant翻转次数：{flip_count}")
    print(f"实际 red_ratio(庄家占比)：{red_ratio_actual:.2f}")

    if flip_count >= 3:
        print(f"👉 翻转{flip_count}次(偏多)：dominant判定不稳定，疑似真噪声，"
              f"red_ratio={red_ratio_actual:.2f} 可信度打折扣，需结合其他指标判断")
    elif noise_months >= 10:
        print(f"👉 翻转仅{flip_count}次，但临界贴身{noise_months}/18个月：'持续双强型'——"
              f"banker/hot常年同时逼近满格，只是少数月被判定游资主导。"
              f"不是噪声，但red_ratio可能低估了实际资金关注度的持续性")
    elif noise_months >= 4:
        print(f"👉 翻转{flip_count}次(不多)，临界贴身{noise_months}/18个月(中等)："
              f"部分月份存在临界情况，但整体方向仍算稳定，red_ratio基本可信")
    else:
        print(f"👉 翻转{flip_count}次，临界贴身仅{noise_months}/18个月(少)："
              f"dominant判定清晰，red_ratio={red_ratio_actual:.2f} 干净反映真实情况，不是算法噪声")


if __name__ == "__main__":
    symbols = sys.argv[1:] if len(sys.argv) > 1 else ["0097.KL"]
    for sym in symbols:
        diagnose(sym)
