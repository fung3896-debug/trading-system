#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DWM MACD 金叉 + 零轴上方 扫描器 (Plan B 辅助模块)
------------------------------------------------
条件 (三线共振, 对齐 TradingView "日线满满/周线满满" 逻辑):
  Daily / Weekly / Monthly 三个周期 当前 同时处于:
    1) DIF > DEA  (金叉之后的多头区间, 不要求金叉精确发生在最后一根K线)
    2) DIF > 0    (零轴上方)

  注: 若改成"必须精确金叉发生在同一根K线", 三周期同时对齐概率极低,
      会导致长期0命中——这是本脚本上一版的 bug, 已修正。

数据源: yfinance (日线原始数据, 周线/月线通过 resample 得到)
兼容: Python 3.10 (与 fernando_smart_money_radar_mcdx.py 环境一致)
"""

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

# ============ 股票池 (沿用 Plan B 现有清单) ============

NASDAQ_LIST = [
    "NVDA", "JBL", "BX", "AMD", "META",
    "MSFT", "INTC", "AMZN", "ARM", "NVCT",
]

KLSE_LIST = [
    "5263.KL",  # SUNCON
    "6432.KL",  # APOLLO
    "8133.KL",  # BHIC
    "1694.KL",  # MENANG
    "3174.KL",  # L&G
    "2453.KL",  # KLUANG
    "7121.KL",  # XL
    "5127.KL",  # ARREIT
    "0181.KL",  # AEMULUS
    "0120.KL",  # VIS
    "3158.KL",  # YNHPROP
]

# ============ MACD 计算 ============

def calc_macd(close: pd.Series, fast=12, slow=26, signal=9):
    """标准 EMA 版 MACD,返回 DIF(macd line), DEA(signal line), HIST"""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    hist = dif - dea
    return dif, dea, hist


def is_bullish_above_zero(dif: pd.Series, dea: pd.Series, cross_lookback: int = 10) -> dict:
    """
    检查当前是否处于"金叉后 + 零轴上方"的持续多头状态 (与 TradingView 满满逻辑对齐):
      - 当前 DIF > DEA  (处于金叉之后的多头区间, 不要求金叉刚好发生在最后一根)
      - 当前 DIF > 0    (零轴上方)
      - 另外记录: 是否在最近 cross_lookback 根K线内发生过金叉 (仅供参考展示)
    """
    if len(dif) < 2 or dif.isna().iloc[-1] or dea.isna().iloc[-1]:
        return {"bullish": False, "recent_cross": False}

    curr_dif, curr_dea = dif.iloc[-1], dea.iloc[-1]
    bullish = bool(curr_dif > curr_dea and curr_dif > 0)

    # 参考: 最近N根内是否发生过一次由下往上的金叉 (信息展示用, 不作为过滤条件)
    recent_cross = False
    window = min(cross_lookback, len(dif) - 1)
    for i in range(1, window + 1):
        p_dif, p_dea = dif.iloc[-i - 1], dea.iloc[-i - 1]
        c_dif, c_dea = dif.iloc[-i], dea.iloc[-i]
        if pd.isna(p_dif) or pd.isna(p_dea):
            continue
        if p_dif <= p_dea and c_dif > c_dea:
            recent_cross = True
            break

    return {"bullish": bullish, "recent_cross": recent_cross}


# ============ 数据获取与重采样 ============

def fetch_daily(ticker: str, period="7y") -> pd.DataFrame:
    """获取日线数据 (7年历史,月线MACD计算需要足够长度)"""
    try:
        df = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=True)
        if df is None or df.empty:
            return pd.DataFrame()
        # 处理可能的 MultiIndex 列
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Close"]].dropna()
        return df
    except Exception as e:
        print(f"  [警告] {ticker} 数据获取失败: {e}")
        return pd.DataFrame()


def resample_close(daily_close: pd.Series, rule: str) -> pd.Series:
    """将日线收盘价重采样为周线('W-FRI')或月线('ME')收盘价"""
    return daily_close.resample(rule).last().dropna()


# ============ 单只股票的 DWM 检查 ============

def check_dwm_signal(ticker: str) -> dict:
    daily_df = fetch_daily(ticker)
    if daily_df.empty or len(daily_df) < 60:
        return {"ticker": ticker, "valid": False, "reason": "数据不足"}

    close_d = daily_df["Close"]
    close_w = resample_close(close_d, "W-FRI")
    close_m = resample_close(close_d, "ME")

    if len(close_w) < 35 or len(close_m) < 35:
        return {"ticker": ticker, "valid": False, "reason": "历史长度不足以计算周/月线MACD"}

    dif_d, dea_d, _ = calc_macd(close_d)
    dif_w, dea_w, _ = calc_macd(close_w)
    dif_m, dea_m, _ = calc_macd(close_m)

    d_res = is_bullish_above_zero(dif_d, dea_d)
    w_res = is_bullish_above_zero(dif_w, dea_w)
    m_res = is_bullish_above_zero(dif_m, dea_m)

    d_signal, w_signal, m_signal = d_res["bullish"], w_res["bullish"], m_res["bullish"]
    dwm_resonance = d_signal and w_signal and m_signal

    return {
        "ticker": ticker,
        "valid": True,
        "daily": d_signal,
        "weekly": w_signal,
        "monthly": m_signal,
        "daily_recent_cross": d_res["recent_cross"],
        "weekly_recent_cross": w_res["recent_cross"],
        "monthly_recent_cross": m_res["recent_cross"],
        "resonance": dwm_resonance,
        "last_close": round(float(close_d.iloc[-1]), 3),
        "dif_d": round(float(dif_d.iloc[-1]), 4),
    }


# ============ 扫描主流程 ============

def scan_list(tickers: list, label: str) -> list:
    print(f"\n{'='*50}")
    print(f"扫描 {label} ({len(tickers)} 支)")
    print(f"{'='*50}")

    results = []
    for t in tickers:
        print(f"  处理中: {t} ...", end="\r")
        r = check_dwm_signal(t)
        results.append(r)

    hits = [r for r in results if r.get("valid") and r.get("resonance")]
    return hits


def print_report(nasdaq_hits, klse_hits):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n\n{'#'*50}")
    print(f"# DWM MACD 金叉+零轴上方 三线共振报告")
    print(f"# 生成时间: {now}")
    print(f"{'#'*50}")

    for label, hits in [("NASDAQ", nasdaq_hits), ("KLSE", klse_hits)]:
        print(f"\n【{label}】命中 {len(hits)} 支:")
        if not hits:
            print("  (本次扫描无三线共振信号)")
        for r in hits:
            cross_flags = []
            if r.get("daily_recent_cross"):
                cross_flags.append("D近期金叉")
            if r.get("weekly_recent_cross"):
                cross_flags.append("W近期金叉")
            if r.get("monthly_recent_cross"):
                cross_flags.append("M近期金叉")
            flag_str = f" [{', '.join(cross_flags)}]" if cross_flags else ""
            print(f"  ✅ {r['ticker']:<10} 收盘={r['last_close']:<10} DIF(D)={r['dif_d']}{flag_str}")


def main():
    nasdaq_hits = scan_list(NASDAQ_LIST, "NASDAQ 清单")
    klse_hits = scan_list(KLSE_LIST, "KLSE 清单")
    print_report(nasdaq_hits, klse_hits)


if __name__ == "__main__":
    main()
