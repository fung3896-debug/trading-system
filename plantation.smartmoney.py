#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fernando Smart Money Radar - REITs专用版
=============================================================================
只扫 REITs 板块，不含美股、不含其他板块代码。
完整对齐 Pine V7 Pro Recovery：MCDX + MACD + 成交量 三层加权总分、
背离侦测、真庄家(banker原始值) Top排行 —— 专门用来验证
"REIT满共振是庄家吸筹，还是游资/消息面推动"这个问题。
"""

import warnings
warnings.filterwarnings('ignore')

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# =====================================================
# 0. REIT Watchlist (只有REITs，20只)
# =====================================================
REIT_LIST = [
    '5235SS.KL',  # KLCC
    '5227.KL',    # IGBREIT
    '5176.KL',    # SUNREIT
    '5212.KL',    # PAVREIT
    '5106.KL',    # AXREIT
    '5180.KL',    # CLMT
    '5109.KL',    # YTLREIT
    '5338.KL',    # PARADIGM
    '5299.KL',    # IGBCR
    '5116.KL',    # ALAQAR
    '5123.KL',    # SENTRAL
    '5307.KL',    # AMEREIT
    '5280.KL',    # KIPREIT
    '5110.KL',    # UOAREIT
    '5269.KL',    # ALSREIT
    '5130.KL',    # ATRIUM
    '5121.KL',    # HEKTAR
    '5127.KL',    # ARREIT
    '5120.KL',    # AMFIRST
    '5111.KL',    # TWRREIT
]

# =====================================================
# 1. 参数 (对齐 Pine V7 Pro Recovery 默认值)
# =====================================================
BANKER_PERIOD, BANKER_BASE, BANKER_SENS = 50, 50.0, 1.4
HOT_PERIOD, HOT_BASE, HOT_SENS = 40, 30.0, 0.65
STRONG_TH, MEDIUM_TH = 14.0, 7.0

MCDX_WEIGHT, MACD_WEIGHT, VOL_WEIGHT = 40.0, 35.0, 25.0

DWM_BULL_TH = 55.0
DWM_STRONG_TH = 80.0

DIVERGENCE_LOOKBACK = 20
DIVERGENCE_RSI_MIN = 60.0

MA20_LEN, MA50_LEN, MA200_LEN = 20, 50, 200
RSI_LEN = 14
CMF_LEN = 20
VOL_LEN = 20


def calc_rsi_wilder(close, length):
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))


def calc_cmf(df, length=CMF_LEN):
    high_low = (df['High'] - df['Low']).replace(0, 1e-10)
    mfv = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / high_low * df['Volume']
    return mfv.rolling(window=length).sum() / df['Volume'].rolling(window=length).sum()


def calc_macd(close, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast).mean()
    ema_slow = close.ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    return macd_line, signal_line, macd_line - signal_line


def cap20(x):
    return x.clip(lower=0.0, upper=20.0)


def calc_mcdx_series(close):
    rsi_banker = calc_rsi_wilder(close, BANKER_PERIOD)
    rsi_hot = calc_rsi_wilder(close, HOT_PERIOD)

    banker = cap20(BANKER_SENS * (rsi_banker - BANKER_BASE))
    hot = cap20(HOT_SENS * (rsi_hot - HOT_BASE))
    retail = cap20(20.0 - pd.concat([banker, hot], axis=1).max(axis=1))

    dominant = pd.Series(-1, index=close.index)
    dominant[(banker >= MEDIUM_TH) & (banker >= hot) & (banker >= retail)] = 0
    dominant[(dominant == -1) & (hot >= MEDIUM_TH) & (hot >= banker) & (hot >= retail)] = 1
    dominant[(dominant == -1) & (retail >= MEDIUM_TH) & (retail >= banker) & (retail >= hot)] = 2

    dom_value = pd.Series(0.0, index=close.index)
    dom_value[dominant == 0] = banker[dominant == 0]
    dom_value[dominant == 1] = hot[dominant == 1]
    dom_value[dominant == 2] = retail[dominant == 2]

    lvl_strong = dom_value >= STRONG_TH
    lvl_medium = (dom_value >= MEDIUM_TH) & (dom_value < STRONG_TH)

    mcdx_score = pd.Series(0.0, index=close.index)
    m0 = dominant == 0
    mcdx_score[m0 & lvl_strong] = 100.0
    mcdx_score[m0 & lvl_medium] = 70.0
    mcdx_score[m0 & ~lvl_strong & ~lvl_medium] = 40.0
    m1 = dominant == 1
    mcdx_score[m1 & lvl_strong] = 85.0
    mcdx_score[m1 & lvl_medium] = 60.0
    mcdx_score[m1 & ~lvl_strong & ~lvl_medium] = 30.0
    m2 = dominant == 2
    mcdx_score[m2 & lvl_strong] = -90.0
    mcdx_score[m2 & lvl_medium] = -55.0
    mcdx_score[m2 & ~lvl_strong & ~lvl_medium] = -20.0

    return banker, hot, retail, dominant, mcdx_score


def calc_macd_score_series(hist):
    h_prev = hist.shift(1)
    score = pd.Series(0.0, index=hist.index)
    score[(hist > 0) & (hist > h_prev)] = 100.0
    score[(hist > 0) & (hist <= h_prev)] = 65.0
    score[(hist < 0) & (hist > h_prev)] = 35.0
    score[(hist < 0) & (hist <= h_prev)] = -80.0
    return score


def calc_vol_score_series(df, length=VOL_LEN):
    vol_ma = df['Volume'].rolling(length).mean()
    vr = df['Volume'] / vol_ma.replace(0, np.nan)
    vr = vr.fillna(0.0)
    up_candle = df['Close'] >= df['Open']

    score = pd.Series(0.0, index=df.index)
    score[(vr >= 1.2) & up_candle] = 100.0
    score[(vr >= 1.0) & (vr < 1.2) & up_candle] = 60.0
    score[(vr >= 1.2) & ~up_candle] = -80.0
    score[(vr >= 1.0) & (vr < 1.2) & ~up_candle] = -40.0
    return score


def resample_ohlcv(df, rule):
    agg = pd.DataFrame({
        'Open': df['Open'].resample(rule).first(),
        'High': df['High'].resample(rule).max(),
        'Low': df['Low'].resample(rule).min(),
        'Close': df['Close'].resample(rule).last(),
        'Volume': df['Volume'].resample(rule).sum(),
    })
    return agg.dropna(subset=['Close'])


def analyze_timeframe_last(tf_df, min_len):
    if len(tf_df) < min_len:
        return None
    close = tf_df['Close']
    banker, hot, retail, dominant, mcdx_score = calc_mcdx_series(close)
    macd_line, signal_line, hist = calc_macd(close)
    macd_bull = bool(macd_line.iloc[-1] > signal_line.iloc[-1])
    macd_score = calc_macd_score_series(hist)
    vol_score = calc_vol_score_series(tf_df)

    tf_total = (mcdx_score.iloc[-1] * MCDX_WEIGHT + macd_score.iloc[-1] * MACD_WEIGHT +
                vol_score.iloc[-1] * VOL_WEIGHT) / (MCDX_WEIGHT + MACD_WEIGHT + VOL_WEIGHT)

    return {
        'banker': banker.iloc[-1], 'hot': hot.iloc[-1], 'retail': retail.iloc[-1],
        'dominant': int(dominant.iloc[-1]),
        'mcdx_score': mcdx_score.iloc[-1],
        'macd_bull': macd_bull,
        'macd_score': macd_score.iloc[-1],
        'vol_score': vol_score.iloc[-1],
        'total': tf_total,
    }


DOMINANT_LABEL = {0: '庄家', 1: '游资', 2: '散户'}


def dwm_weighted_total(d, w, m, day_w=20.0, week_w=35.0, month_w=45.0):
    parts = []
    if d is not None:
        parts.append((d['total'], day_w))
    if w is not None:
        parts.append((w['total'], week_w))
    if m is not None:
        parts.append((m['total'], month_w))
    if not parts:
        return None
    total_w = sum(wt for _, wt in parts)
    return sum(val * wt for val, wt in parts) / total_w


def dwm_weighted_banker(d, w, m, day_w=20.0, week_w=35.0, month_w=45.0):
    parts = []
    if d is not None:
        parts.append((d['banker'], day_w))
    if w is not None:
        parts.append((w['banker'], week_w))
    if m is not None:
        parts.append((m['banker'], month_w))
    if not parts:
        return None
    total_w = sum(wt for _, wt in parts)
    return sum(val * wt for val, wt in parts) / total_w


def resonance_text(d_tf, w_tf, m_tf):
    if d_tf is None or w_tf is None or m_tf is None:
        return "⚠️ 数据不足", None
    d, w, m = d_tf['mcdx_score'], w_tf['mcdx_score'], m_tf['mcdx_score']
    if d >= DWM_STRONG_TH and w >= DWM_STRONG_TH and m >= DWM_STRONG_TH:
        return "🚀 日周月满", True
    elif d >= DWM_BULL_TH and w >= DWM_BULL_TH and m >= DWM_BULL_TH:
        return "✅ 日周月偏多", True
    else:
        return "⚠️ 未共振", False


def detect_bearish_divergence(df, lookback=DIVERGENCE_LOOKBACK):
    close = df['Close']
    rsi = calc_rsi_wilder(close, RSI_LEN)
    banker, _, _, _, _ = calc_mcdx_series(close)

    if len(df) < lookback + 2:
        return False, float(rsi.iloc[-1]) if len(rsi) else np.nan

    price_highest = close.iloc[-1] >= close.iloc[-lookback:].max()
    rsi_highest_prev = rsi.shift(1).iloc[-lookback:].max()
    banker_highest_prev = banker.shift(1).iloc[-lookback:].max()

    rsi_not_highest = rsi.iloc[-1] < rsi_highest_prev
    banker_not_highest = banker.iloc[-1] < banker_highest_prev

    bearish_div = bool(price_highest and (rsi_not_highest or banker_not_highest) and rsi.iloc[-1] > DIVERGENCE_RSI_MIN)
    return bearish_div, float(rsi.iloc[-1])


def analyze_stock(ticker):
    try:
        df = yf.download(ticker, period='7y', progress=False)
        if df.empty or len(df) < 60:
            return None, "数据不足"

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna(subset=['Close'])
        if df.empty or len(df) < 60:
            return None, "数据不足"

        close = df['Close']
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        ma20 = close.rolling(MA20_LEN).mean()
        ma50 = close.rolling(MA50_LEN).mean()
        ma200 = close.rolling(MA200_LEN).mean() if len(df) >= MA200_LEN else pd.Series([np.nan] * len(df), index=df.index)
        cmf = calc_cmf(df)

        c = float(close.iloc[-1])
        m20 = float(ma20.iloc[-1])
        m50 = float(ma50.iloc[-1])
        m200 = float(ma200.iloc[-1]) if not pd.isna(ma200.iloc[-1]) else None
        cm = float(cmf.iloc[-1])
        trend_bull = c > m20 > m50
        ma_bull = (c > m20 > m50 > m200) if m200 is not None else False

        bearish_div, rsi_now = detect_bearish_divergence(df)

        weekly_df = resample_ohlcv(df, 'W')
        monthly_df = resample_ohlcv(df, 'ME')
        min_len = max(BANKER_PERIOD, HOT_PERIOD) + 10

        d_tf = analyze_timeframe_last(df, min_len)
        w_tf = analyze_timeframe_last(weekly_df, min_len)
        m_tf = analyze_timeframe_last(monthly_df, min_len)

        dwm_total = dwm_weighted_total(d_tf, w_tf, m_tf)
        if dwm_total is None:
            return None, "週期数据不足"
        banker_strength = dwm_weighted_banker(d_tf, w_tf, m_tf)

        res_text, res_bull = resonance_text(d_tf, w_tf, m_tf)
        dom_str = '/'.join(DOMINANT_LABEL[tf['dominant']] if tf else 'N/A' for tf in (d_tf, w_tf, m_tf))

        danger = (m200 is not None and c < m200) or (d_tf is not None and d_tf['dominant'] == 2 and d_tf['mcdx_score'] <= -55)

        if danger:
            risk_text = "❌ 危险"
        elif bearish_div:
            risk_text = "⚠️ 頂背離警告"
        else:
            risk_text = "✅ 正常"

        if dwm_total >= 70 and res_bull:
            signal = "🟢 买入"
        elif dwm_total >= 35:
            signal = "🟡 关注"
        else:
            signal = "🔴 避免"

        return {
            'ticker': ticker, 'price': c, 'dwm_total': dwm_total, 'signal': signal,
            'resonance': res_text, 'risk': risk_text, 'bearish_div': bearish_div,
            'rsi': rsi_now, 'cmf': cm, 'trend_bull': trend_bull, 'ma_bull': ma_bull,
            'd_score': d_tf['mcdx_score'] if d_tf else None,
            'w_score': w_tf['mcdx_score'] if w_tf else None,
            'm_score': m_tf['mcdx_score'] if m_tf else None,
            'banker': d_tf['banker'] if d_tf else None,
            'hot': d_tf['hot'] if d_tf else None,
            'retail': d_tf['retail'] if d_tf else None,
            'banker_d': d_tf['banker'] if d_tf else None,
            'banker_w': w_tf['banker'] if w_tf else None,
            'banker_m': m_tf['banker'] if m_tf else None,
            'banker_strength': banker_strength,
            'dominant_dwm': dom_str,
        }, None

    except Exception as e:
        return None, str(e)[:50]


def _bfmt(x):
    return f"{x:.1f}" if x is not None else "N/A"


def scan_reits():
    print(f"\n{'='*110}")
    print(f"🏢 REITs板块 Smart Money Radar | 时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*110}")
    print(f"{'代码':<12} {'价格':>10} {'总分':>7} {'信号':<8} {'MCDX共振':<12} {'主导(D/W/M)':<14} {'风险':<14} {'D/W/M分':<18} {'RSI':>6}")
    print("-" * 110)

    results = []
    errors = []
    for ticker in REIT_LIST:
        result, err = analyze_stock(ticker)
        if result is None:
            errors.append((ticker, err))
            print(f"{ticker:<12} ❌ {err}")
            continue
        results.append(result)

        def _fmt(x):
            return f"{x:.0f}" if x is not None else "N/A"

        dwm_str = f"{_fmt(result['d_score'])}/{_fmt(result['w_score'])}/{_fmt(result['m_score'])}"
        print(f"{result['ticker']:<12} {result['price']:>10.3f} {result['dwm_total']:>7.1f} "
              f"{result['signal']:<8} {result['resonance']:<12} {result['dominant_dwm']:<14} {result['risk']:<14} "
              f"{dwm_str:<18} {result['rsi']:>6.1f}")

    results.sort(key=lambda x: -x['dwm_total'])

    print(f"\n🏆 REITs Top 5 (MCDX总分，含背离警告标注 — 注意分数可能由游资撑起，非真庄家)")
    for r in results[:5]:
        div_tag = " 【⚠️背离】" if r['bearish_div'] else ""
        print(f"{r['ticker']:<12} RM{r['price']:>8.3f} 总分:{r['dwm_total']:>6.1f} {r['signal']} "
              f"{r['resonance']} 主导:{r['dominant_dwm']} RSI:{r['rsi']:>5.1f} CMF:{r['cmf']:>6.3f}{div_tag}")

    banker_ranked = sorted(
        [r for r in results if r['banker_strength'] is not None],
        key=lambda x: -x['banker_strength']
    )
    print(f"\n🏦 REITs 真庄家 Top 10 (按 banker 原始值加权排序，日20%/周35%/月45%，剔除游资分数干扰)")
    print(f"{'代码':<12} {'价格':>10} {'庄家强度':>10} {'D/W/M banker':<20} {'主导':<14} {'MCDX总分':>8}")
    print("-" * 90)
    for r in banker_ranked[:10]:
        print(f"{r['ticker']:<12} RM{r['price']:>8.3f} {r['banker_strength']:>8.1f}/20 "
              f"{_bfmt(r['banker_d'])}/{_bfmt(r['banker_w'])}/{_bfmt(r['banker_m']):<10} "
              f"{r['dominant_dwm']:<14} {r['dwm_total']:>8.1f}")

    if errors:
        print(f"\n⚠️ 无法处理 — 共 {len(errors)} 只")
        for t, err in errors:
            print(f"{t:<12} {err}")

    return results


if __name__ == "__main__":
    scan_reits()
    print(f"\n{'='*110}")
    print("✨ 完成！重点看「真庄家 Top 10」里 AMFIRST/ALSREIT/ARREIT 的排名和 週/月 banker 原始值")
    print(f"{'='*110}\n")
