#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diagnose_banker_noise.py —— 逐月banker/hot明细核查
============================================================
用法：
    python3 diagnose_banker_noise.py 股票代码.KL
"""

import warnings
warnings.filterwarnings('ignore')

import sys
import yfinance as yf
import pandas as pd

import v7pro_mcdx_scan as v7

NOISE_GAP = 2.0  # 临界(贴身)判定门槛：banker与hot差距在此范围内视为噪声区


def clean(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=['Close'])


def diagnose(symbol, months=18):
    print("curl_cffi not available; falling back to requests without browser TLS impersonation. "
          "Yahoo Finance may rate-limit or block this client. Install curl_cffi (>=0.15) for the "
          "supported configuration.")

    df = clean(yf.download(symbol, period='7y', auto_adjust=True, progress=False))
    if len(df) < 200:
        print(f"{symbol}: 数据不足")
        return

    monthly = v7.resample_ohlcv(df, 'ME')
    banker, hot, retail, dominant, mcdx_score = v7.calc_mcdx_series(monthly['Close'])

    recent = monthly.tail(months)
    b_recent = banker.tail(months)
    h_recent = hot.tail(months)
    dom_recent = dominant.tail(months)

    print("=" * 78)
    print(f"{symbol}  过去{months}个月 banker/hot 逐月明细")
    print("=" * 78)
    print(f"{'月份':<12}{'banker':>8}{'hot':>8}{'差距':>8}    当月dominant   备注")
    print("-" * 78)

    dom_map = {0: '庄家', 1: '游资', 2: '散户', -1: '暖机中'}
    prev_dom = None
    flip_count = 0
    noise_months = 0

    for i in range(len(recent)):
        month_label = recent.index[i].strftime('%Y-%m')
        b_val = b_recent.iloc[i]
        h_val = h_recent.iloc[i]
        gap = abs(b_val - h_val)
        dom_val = int(dom_recent.iloc[i])
        dom_text = dom_map.get(dom_val, '未知')

        note = ""
        if gap <= NOISE_GAP and dom_val in (0, 1):
            note += "⚠️ 临界(贴身)"
            noise_months += 1

        if prev_dom is not None and dom_val != prev_dom and dom_val in (0, 1) and prev_dom in (0, 1):
            flip_count += 1
            note += "  🔀翻转" if note else "🔀翻转"
        prev_dom = dom_val

        print(f"{month_label:<12}{b_val:>8.1f}{h_val:>8.1f}{gap:>8.1f}{dom_text:>12}   {note}")

    print("-" * 78)
    red_count = sum(1 for v in dom_recent if int(v) == 0)
    red_ratio = red_count / len(dom_recent) if len(dom_recent) > 0 else 0

    print(f"临界(贴身)月数：{noise_months}/{len(recent)}   dominant翻转次数：{flip_count}")
    print(f"实际 red_ratio(庄家占比)：{red_ratio:.2f}")

    if flip_count >= 3 and noise_months < len(recent) // 2:
        print(f"👉 翻转{flip_count}次(偏多)：dominant判定不稳定，疑似真噪声，"
              f"red_ratio={red_ratio:.2f} 可信度打折扣，需结合其他指标判断")
    elif flip_count <= 2 and noise_months >= len(recent) * 0.6:
        print(f"👉 翻转仅{flip_count}次，但临界贴身{noise_months}/{len(recent)}个月："
              f"'持续双强型'——banker/hot常年同时逼近满格，只是少数月被判定游资主导。"
              f"不是噪声，但red_ratio可能低估了实际资金关注度的持续性")
    elif flip_count <= 2 and noise_months == 0:
        print(f"👉 翻转{flip_count}次，临界贴身仅0/{len(recent)}个月(少)："
              f"dominant判定清晰，red_ratio={red_ratio:.2f} 干净反映真实情况，不是算法噪声")
    else:
        print(f"👉 翻转{flip_count}次，临界贴身{noise_months}/{len(recent)}个月："
              f"混合情况，建议结合共振分数和VWAP综合判断")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python3 diagnose_banker_noise.py 股票代码.KL")
        sys.exit(1)
    diagnose(sys.argv[1])
