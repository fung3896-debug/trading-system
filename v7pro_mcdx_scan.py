#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fernando Smart Money Radar | 真实数据 + MCDX (完整对齐 Pine V7 Pro Recovery)
=============================================================================
本版本相对上一版的关键修正：
  1. 【核心修正】MCDX共振判断，改成跟 Pine 完全一致的两级分数门槛：
         dMcdxScore >= 55 and wMcdxScore >= 55 and mMcdxScore >= 55  → "✅ 日周月偏多"
         dMcdxScore >= 80 and wMcdxScore >= 80 and mMcdxScore >= 80  → "🚀 日周月满"
         否则                                                        → "⚠️ 未共振"
     (上一版只检查 dominant 是 0 或 1，不看分数高低，导致跟 Pine 状态表显示不一致)
  2. 【新增】背离侦测 (bearishDivergence)，逻辑对齐 Pine 第 8.5 节新增的：
         priceHighest      = close >= 20 日内最高价
         rsiNotHighest     = rsi < 20 日内最高 rsi (前一根)
         bankerNotHighest  = banker < 20 日内最高 banker (前一根)
         bearishDivergence = priceHighest and (rsiNotHighest or bankerNotHighest) and rsi > 60
  3. 保留原本的 MCDX / MACD / 成交量 三层加权总分系统 (对齐 f_mtf_total_score)。
  4. 风险栏输出，比照 Pine 状态表第16行的判断优先级：
         danger > bearishDivergence > distributeRisk(近似) > 正常

未对齐项目 (下次再补，见对话说明)：
  - RCI (f_rci) 排名相关系数，本版尚未实作
  - VP / POC 真实成交量分布，本版尚未实作
  这两项目前状态表会显示 "N/A"，不影响 MCDX共振与背离判断的准确性。
"""

import warnings
warnings.filterwarnings('ignore')

import time
import pandas as pd
import numpy as np
from datetime import datetime
from yahoo_fetch import fetch_ohlcv

# =====================================================
# 0. Watchlist
# =====================================================
WATCHLIST = {
    'NASDAQ': ['NVDA', 'JBL', 'BX', 'AMD', 'META', 'MSFT', 'INTC', 'AMZN', 'ARM', 'NVCT'],
    'KLSE': [
        '9393.KL',  # ITRONIC
        '0029.KL',  # DIGISTA
        '7181.KL',  # ARBB
        '0143.KL',  # KEYASIC
        '0200.KL',  # REVENUE
        '4359.KL',  # TURIYA
        '8338.KL',  # DATAPRP
        '0041.KL',  # AIMAX
        '0113.KL',  # MMSV
        '9075.KL',  # THETA
        '5036.KL',  # EDARAN
        '5011.KL',  # MSNIAGA
        '0126.KL',  # MICROLN
        '0051.KL',  # CUSCAPI
        '0065.KL',  # EFORCE
        '5195.KL',  # CENSOF
        '0258.KL',  # AGMO
        '9377.KL',  # FSBM
        '0253.KL',  # INFOTEC
        '0040.KL',  # OPENSYS
        '0008.KL',  # WILLOW
        '0090.KL',  # ELSOFT
        '9008.KL',  # OMESTI
        '9334.KL',  # KESM
        '7022.KL',  # GTRONIC
        '0249.KL',  # LGMS
        '5028.KL',  # HTPADU
        '0277.KL',  # CLOUDPT
        '0127.KL',  # JHM
        '5204.KL',  # AWANTEC
        '0104.KL',  # GENETEC
        '0083.KL',  # NOTION
        '0246.KL',  # CNERGEN
        '0276.KL',  # ADB
        '7204.KL',  # D&O
        '0146.KL',  # JFTECH
        '5161.KL',  # JCY
        '0259.KL',  # SNS
        '5216.KL',  # NEXG
        '4456.KL',  # DNEX
        '5301.KL',  # CTOS
        '5162.KL',  # VSTECS
        '7160.KL',  # PENTA
        '5286.KL',  # MI
        '5309.KL',  # ITMAX
        '5357.KL',  # SKYECHIP
        '0208.KL',  # GREATEC
        '0138.KL',  # ZETRIX
        '5292.KL',  # UWC
        '5005.KL',  # UNISEM
        '0166.KL',  # INARI
        '0128.KL',  # FRONTKN
        '3867.KL',  # MPI
        '0097.KL',  # VITROX
    ],
}

BATCH_SIZE = 10
BATCH_PAUSE_SEC = 2

# =====================================================
# 1. 参数 (对齐 Pine V7 Pro Recovery 默认值)
# =====================================================
BANKER_PERIOD, BANKER_BASE, BANKER_SENS = 50, 50.0, 1.4
HOT_PERIOD, HOT_BASE, HOT_SENS = 40, 30.0, 0.65
STRONG_TH, MEDIUM_TH = 14.0, 7.0

MCDX_WEIGHT, MACD_WEIGHT, VOL_WEIGHT = 40.0, 35.0, 25.0

# MCDX共振门槛 (对齐 Pine 第13节 mcdxDWM_Bull / mcdxDWM_Strong)
DWM_BULL_TH = 55.0
DWM_STRONG_TH = 80.0

# 背离侦测参数 (对齐 Pine 第8.5节)
DIVERGENCE_LOOKBACK = 20
DIVERGENCE_RSI_MIN = 60.0

MA20_LEN, MA50_LEN, MA200_LEN = 20, 50, 200
RSI_LEN = 14
CMF_LEN = 20
VOL_LEN = 20


# =====================================================
# 2. 基础指标函数
# =====================================================
def calc_rsi_wilder(close: pd.Series, length: int) -> pd.Series:
    """Wilder 平滑版 RSI，与 Pine 的 ta.rsi() 算法一致"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))


def calc_cmf(df: pd.DataFrame, length: int = CMF_LEN) -> pd.Series:
    high_low = (df['High'] - df['Low']).replace(0, 1e-10)
    mfv = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / high_low * df['Volume']
    return mfv.rolling(window=length).sum() / df['Volume'].rolling(window=length).sum()


def calc_macd(close: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast).mean()
    ema_slow = close.ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    return macd_line, signal_line, macd_line - signal_line


def cap20(x) -> pd.Series:
    return x.clip(lower=0.0, upper=20.0)


# =====================================================
# 3. MCDX 全序列计算 (为了背离侦测，需要整条 banker 序列，不能只算最后一个值)
# =====================================================
def calc_mcdx_series(close: pd.Series):
    """回傳整条序列的 banker / hot / retail / dominant / mcdx_score，
    (原本旧版只算最后一天的单一数值，这次改成算整条序列，
    是因为背离侦测需要比较『过去20天内banker的最高值』，缺一不可)"""
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


def calc_macd_score_series(hist: pd.Series) -> pd.Series:
    """对应 Pine f_mtf_macd_score()，逐点计算"""
    h_prev = hist.shift(1)
    score = pd.Series(0.0, index=hist.index)
    score[(hist > 0) & (hist > h_prev)] = 100.0
    score[(hist > 0) & (hist <= h_prev)] = 65.0
    score[(hist < 0) & (hist > h_prev)] = 35.0
    score[(hist < 0) & (hist <= h_prev)] = -80.0
    return score


def calc_vol_score_series(df: pd.DataFrame, length: int = VOL_LEN) -> pd.Series:
    """对应 Pine f_mtf_vol_score()，逐点计算"""
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


# =====================================================
# 4. 週期聚合
# =====================================================
def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = pd.DataFrame({
        'Open': df['Open'].resample(rule).first(),
        'High': df['High'].resample(rule).max(),
        'Low': df['Low'].resample(rule).min(),
        'Close': df['Close'].resample(rule).last(),
        'Volume': df['Volume'].resample(rule).sum(),
    })
    return agg.dropna(subset=['Close'])


def analyze_timeframe_last(tf_df: pd.DataFrame, min_len: int):
    """取单一时间週期(日/週/月)最后一天的 mcdx_score / macd_score / vol_score / total"""
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


def resonance_text(d_tf, w_tf, m_tf):
    """对齐 Pine 第18节 statusTable row 8 的三级判断"""
    if d_tf is None or w_tf is None or m_tf is None:
        return "⚠️ 数据不足", None
    d, w, m = d_tf['mcdx_score'], w_tf['mcdx_score'], m_tf['mcdx_score']
    if d >= DWM_STRONG_TH and w >= DWM_STRONG_TH and m >= DWM_STRONG_TH:
        return "🚀 日周月满", True
    elif d >= DWM_BULL_TH and w >= DWM_BULL_TH and m >= DWM_BULL_TH:
        return "✅ 日周月偏多", True
    else:
        return "⚠️ 未共振", False


def dwm_weighted_banker(d, w, m, day_w=20.0, week_w=35.0, month_w=45.0):
    """真庄家强度：只用 banker 原始值(0-20) 做 DWM 加权，不混入游资/散户分数
    (对齐 Pine 脚本的 bankerStrength)"""
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


def real_banker_flag(d_tf, w_tf, m_tf):
    """区分『真庄家』与『纯游资』推动的共振 (对齐 Pine isRealBankerDWM / isHotMoneyOnlyDWM)
    Python 原本的 resonance_text 只看 mcdx_score 门槛，dominant=1(游资)一样能推高分数触发
    "🚀日周月满"，不区分这是真庄家控盘还是纯游资炒作——这里补上这个区分"""
    if d_tf is None or w_tf is None or m_tf is None:
        return "N/A"
    d, w, m = d_tf['dominant'], w_tf['dominant'], m_tf['dominant']
    if d == 0 and w == 0 and m == 0:
        return "🟢 真庄家DWM满控"
    if d == 1 and w == 1 and m == 1:
        return "🟠 纯游资DWM(无真庄家)"
    return "-"


# =====================================================
# 5. 背离侦测 (对齐 Pine 8.5 节)
# =====================================================
def detect_bearish_divergence(df: pd.DataFrame, lookback: int = DIVERGENCE_LOOKBACK):
    """回傳 (bearishDivergence: bool, rsi_now: float)，只针对日线最后一根K棒判断，
    跟 Pine 图表版一致 (Pine 的 divergenceLookback 也是套用在当前主图表週期，
    也就是日线，不是週线或月线)"""
    close = df['Close']
    rsi = calc_rsi_wilder(close, RSI_LEN)
    banker, _, _, _, _ = calc_mcdx_series(close)

    if len(df) < lookback + 2:
        return False, float(rsi.iloc[-1]) if len(rsi) else np.nan

    price_highest = close.iloc[-1] >= close.iloc[-lookback:].max()
    # Pine 用 [1] 代表「不含当前K棒的前一根」为基准的 highest，這裡用 shift(1) 對齊
    rsi_highest_prev = rsi.shift(1).iloc[-lookback:].max()
    banker_highest_prev = banker.shift(1).iloc[-lookback:].max()

    rsi_not_highest = rsi.iloc[-1] < rsi_highest_prev
    banker_not_highest = banker.iloc[-1] < banker_highest_prev

    bearish_div = bool(price_highest and (rsi_not_highest or banker_not_highest) and rsi.iloc[-1] > DIVERGENCE_RSI_MIN)
    return bearish_div, float(rsi.iloc[-1])


# =====================================================
# 6. 单一股票完整分析
# =====================================================
def analyze_stock(ticker: str):
    try:
        df = fetch_ohlcv(ticker, range_='10y', interval='1d')
        if df.empty or len(df) < 60:
            return None, "数据不足"

        df = df.dropna(subset=['Close'])
        if df.empty or len(df) < 60:
            return None, "数据不足"

        close = df['Close']

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

        # 背离 (对齐 Pine 8.5 节，用日线序列)
        bearish_div, rsi_now = detect_bearish_divergence(df)

        # 日/週/月 三层
        weekly_df = resample_ohlcv(df, 'W')
        monthly_df = resample_ohlcv(df, 'ME')
        min_len = max(BANKER_PERIOD, HOT_PERIOD) + 10

        d_tf = analyze_timeframe_last(df, min_len)
        w_tf = analyze_timeframe_last(weekly_df, min_len)
        m_tf = analyze_timeframe_last(monthly_df, min_len)

        dwm_total = dwm_weighted_total(d_tf, w_tf, m_tf)
        if dwm_total is None:
            return None, "週期数据不足"

        res_text, res_bull = resonance_text(d_tf, w_tf, m_tf)
        banker_strength = dwm_weighted_banker(d_tf, w_tf, m_tf)
        banker_flag = real_banker_flag(d_tf, w_tf, m_tf)

        # 简化版风险判断 (对齐 Pine 第16节优先级: danger > 背离 > 正常)
        # 注：Pine 的 danger 需要週线趋势与 MA200，这里用近似条件
        danger = (m200 is not None and c < m200) or (d_tf is not None and d_tf['dominant'] == 2 and d_tf['mcdx_score'] <= -55)

        if danger:
            risk_text = "❌ 危险"
        elif bearish_div:
            risk_text = "⚠️ 頂背離警告"
        else:
            risk_text = "✅ 正常"

        # 信号分级 (沿用总分门槛，非 Pine 逐项加总的 100 分制，仅作排序参考)
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
            'banker_strength': banker_strength,
            'banker_flag': banker_flag,
        }, None

    except Exception as e:
        return None, str(e)[:50]


# =====================================================
# 7. 扫描 + 报告
# =====================================================
def scan_market(market_name: str, emoji: str, tickers: list):
    n_batches = (len(tickers) - 1) // BATCH_SIZE + 1
    print(f"\n{'='*110}")
    print(f"{emoji} {market_name}  |  时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  分{n_batches}批, 每批{BATCH_SIZE}支")
    print(f"{'='*110}")
    print(f"{'代码':<10} {'价格':>10} {'总分':>7} {'信号':<8} {'MCDX共振':<12} {'真庄家/游资':<18} {'风险':<14} {'D/W/M分':<18} {'RSI':>6}")
    print("-" * 110)

    results = []
    batches = [tickers[i:i + BATCH_SIZE] for i in range(0, len(tickers), BATCH_SIZE)]
    for bi, batch in enumerate(batches, 1):
        print(f"\n--- 第 {bi}/{len(batches)} 批 ---")
        for ticker in batch:
            result, err = analyze_stock(ticker)
            if result is None:
                print(f"{ticker:<10} ❌ {err}")
                continue
            results.append(result)

            def _fmt(x):
                return f"{x:.0f}" if x is not None else "N/A"

            dwm_str = f"{_fmt(result['d_score'])}/{_fmt(result['w_score'])}/{_fmt(result['m_score'])}"
            print(f"{result['ticker']:<10} {result['price']:>10.2f} {result['dwm_total']:>7.1f} "
                  f"{result['signal']:<8} {result['resonance']:<12} {result['banker_flag']:<18} {result['risk']:<14} "
                  f"{dwm_str:<18} {result['rsi']:>6.1f}")
        if bi < len(batches):
            time.sleep(BATCH_PAUSE_SEC)

    results.sort(key=lambda x: -x['dwm_total'])

    print(f"\n🏆 {market_name} Top 5 (含背离警告标注)")
    for r in results[:5]:
        div_tag = " 【⚠️背离】" if r['bearish_div'] else ""
        bs = f"{r['banker_strength']:.1f}" if r['banker_strength'] is not None else "N/A"
        print(f"{r['ticker']:<10} ${r['price']:>9.2f}  总分:{r['dwm_total']:>6.1f} {r['signal']}  "
              f"{r['resonance']}  真庄家强度:{bs}/20 {r['banker_flag']}  RSI:{r['rsi']:>5.1f} CMF:{r['cmf']:>6.3f}{div_tag}")

    print(f"\n🔍 {market_name} MCDX共振清单中『真庄家 vs 纯游资』区分 (对齐 Pine isRealBankerDWM/isHotMoneyOnlyDWM)")
    resonance_hits = [r for r in results if r['resonance'] in ('🚀 日周月满', '✅ 日周月偏多')]
    if not resonance_hits:
        print("  (本次无共振信号)")
    for r in sorted(resonance_hits, key=lambda x: -x['dwm_total']):
        bs = f"{r['banker_strength']:.1f}" if r['banker_strength'] is not None else "N/A"
        div_tag = " 【⚠️顶背离】" if r['bearish_div'] else ""
        print(f"  {r['ticker']:<10} {r['resonance']:<12} {r['banker_flag']:<20} 真庄家强度:{bs}/20{div_tag}")

    return results


if __name__ == "__main__":
    print(f"\n{'#'*110}")
    print(f"📊 Fernando Smart Money Radar | 完整对齐 Pine V7 Pro Recovery (含背离侦测)")
    print(f"{'#'*110}")

    nasdaq_results = scan_market("NASDAQ 美股", "🇺🇸", WATCHLIST['NASDAQ'])
    klse_results = scan_market("KLSE 马股", "🇲🇾", WATCHLIST['KLSE'])

    print(f"\n{'='*110}")
    print("✨ 完成！MCDX共振门槛与背离侦测已对齐 Pine 状态表逻辑")
    print("   若某股票显示【⚠️背离】，代表当前日K棒符合『价格创新高但RSI或莊家指标未跟上』")
    print("   建议优先看 Top 5 中『🟢 买入』且『MCDX共振』为 ✅/🚀、且无【⚠️背离】标注的股票")
    print(f"{'='*110}\n")
