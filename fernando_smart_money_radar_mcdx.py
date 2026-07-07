"""
Fernando Smart Money Radar | 真实数据 + MCDX (对齐 Pine V7 Pro Recovery)
=========================================================================
本次更新重点:
  1. 新增 MCDX (莊家 banker / 游资 hot / 散户 retail) 计算，参数与 Pine
     的 fernando_gpt_ultimate_v7_pro_recovery.pine 默认值一致：
         banker: RSI(50), base=50, sens=1.4
         hot   : RSI(40), base=30, sens=0.65
         强阈值 strongTh=14.0, 中阈值 mediumTh=7.0
     并套用「中性判断」修正 —— 只有分数真的超过 mediumTh 才判定主导，
     不再让 retail 靠减法自动获胜。
  2. RSI 改用 Wilder 平滑 (跟 Pine 的 ta.rsi 算法一致)，
     避免 MCDX 数值跟图表对不上。
  3. 新增 MACD / 成交量 的评分函数 (对应 Pine 的 f_mtf_macd_score /
     f_mtf_vol_score)，跟 MCDX 分数一起加权算出 total_score。
  4. 修正原本的信号门槛 bug：原公式最高分只能到 32.5，但门槛却写
     >= 50，导致「买入」信号永远不会触发。这次改成跟新的分数范围
     (-90 ~ 100) 匹配的门槛。
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

WATCHLIST = {
    'NASDAQ': ['NVDA', 'JBL', 'BX', 'AMD', 'META', 'MSFT', 'INTC', 'AMZN', 'ARM', 'NVCT'],
    'KLSE': ['7233.KL', '5211.KL', '8907.KL', '6459.KL', '5249.KL', '5026.KL', '5286.KL', '0225.KL', '0099.KL',
             '5031.KL', '5681.KL', '7163.KL', '8869.KL', '1066.KL', '0215.KL', '0326.KL',
             '7103.KL', '5263.KL', '4863.KL', '5243.KL', '5142.KL'],
}

# ============ MCDX 参数 (对齐 Pine V7 Pro Recovery 默认值) ============
BANKER_PERIOD, BANKER_BASE, BANKER_SENS = 50, 50.0, 1.4
HOT_PERIOD, HOT_BASE, HOT_SENS = 40, 30.0, 0.65
STRONG_TH, MEDIUM_TH = 14.0, 7.0

MCDX_WEIGHT, MACD_WEIGHT, VOL_WEIGHT = 40.0, 35.0, 25.0


def calc_rsi_wilder(close: pd.Series, length: int = 14) -> pd.Series:
    """Wilder 平滑版 RSI，与 Pine 的 ta.rsi() 算法一致 (原本用简单 rolling mean 会跟图表对不上)"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))


def calc_cmf(df: pd.DataFrame, length: int = 20) -> pd.Series:
    high_low = (df['High'] - df['Low']).replace(0, 1e-10)
    mfv = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / high_low * df['Volume']
    return mfv.rolling(window=length).sum() / df['Volume'].rolling(window=length).sum()


def calc_macd(close: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast).mean()
    ema_slow = close.ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    return macd_line, signal_line, macd_line - signal_line


def cap20(x: float) -> float:
    return max(0.0, min(20.0, x))


def calc_mcdx(close: pd.Series):
    """
    回傳 (banker, hot, retail, dominant, mcdx_score)
    dominant: 0=莊家主導 1=游資主導 2=散戶主導 -1=中性(三方皆弱，无明显主导)
    mcdx_score: 對齊 Pine f_mtf_mcdx_score() 的 -90~100 評分
    """
    rsi_banker = calc_rsi_wilder(close, BANKER_PERIOD).iloc[-1]
    rsi_hot = calc_rsi_wilder(close, HOT_PERIOD).iloc[-1]

    banker = cap20(BANKER_SENS * (rsi_banker - BANKER_BASE))
    hot = cap20(HOT_SENS * (rsi_hot - HOT_BASE))
    retail = cap20(20.0 - max(banker, hot))

    if banker >= MEDIUM_TH and banker >= hot and banker >= retail:
        dominant = 0
    elif hot >= MEDIUM_TH and hot >= banker and hot >= retail:
        dominant = 1
    elif retail >= MEDIUM_TH and retail >= banker and retail >= hot:
        dominant = 2
    else:
        dominant = -1

    dom_value = {0: banker, 1: hot, 2: retail}.get(dominant, 0.0)
    lvl_strong = dom_value >= STRONG_TH
    lvl_medium = MEDIUM_TH <= dom_value < STRONG_TH

    if dominant == 0:
        mcdx_score = 100.0 if lvl_strong else 70.0 if lvl_medium else 40.0
    elif dominant == 1:
        mcdx_score = 85.0 if lvl_strong else 60.0 if lvl_medium else 30.0
    elif dominant == 2:
        mcdx_score = -90.0 if lvl_strong else -55.0 if lvl_medium else -20.0
    else:
        mcdx_score = 0.0

    return banker, hot, retail, dominant, mcdx_score


def calc_macd_score(hist: pd.Series) -> float:
    """对应 Pine f_mtf_macd_score()"""
    h, h_prev = hist.iloc[-1], hist.iloc[-2]
    if h > 0 and h > h_prev:
        return 100.0
    if h > 0:
        return 65.0
    if h < 0 and h > h_prev:
        return 35.0
    if h < 0 and h < h_prev:
        return -80.0
    return 0.0


def calc_vol_score(df: pd.DataFrame, length: int = 20) -> float:
    """对应 Pine f_mtf_vol_score()"""
    vol_ma = df['Volume'].rolling(length).mean().iloc[-1]
    vr = df['Volume'].iloc[-1] / vol_ma if vol_ma else 0.0
    up_candle = df['Close'].iloc[-1] >= df['Open'].iloc[-1]
    if vr >= 1.2 and up_candle:
        return 100.0
    if vr >= 1.0 and up_candle:
        return 60.0
    if vr >= 1.2 and not up_candle:
        return -80.0
    if vr >= 1.0 and not up_candle:
        return -40.0
    return 0.0


def dominant_text(dominant: int) -> str:
    return {0: "莊家主導", 1: "游資主導", 2: "散戶主導", -1: "中性/盤整"}.get(dominant, "?")


print(f"\n{'='*100}")
print(f"📊 Fernando Smart Money Radar | 真实数据 + MCDX")
print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

results = []
all_tickers = WATCHLIST['NASDAQ'] + WATCHLIST['KLSE']

for ticker in all_tickers:
    try:
        df = yf.download(ticker, period='6mo', progress=False)
        if df.empty or len(df) < 60:
            print(f"{ticker:<12} ❌ 数据不足")
            continue

        # 新版 yfinance 即使只下载单支股票，也可能回传 MultiIndex 欄位
        # (例如 ('Close','NVDA'))，导致 df['Close'] 拿到的是 DataFrame 而非
        # Series，后续所有数学运算会因为「比较一整个表格」而报错
        # (The truth value of a Series is ambiguous)。这里下载后立即攤平：
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # yfinance 有时会在交易所还没真正开盘时，提前塞入「今天」这一行
        # 空数据 (Close/Volume 全是 NaN)。这一行会让 c > m20 > m50 这种
        # 比较永远判定失败(趋势全部显示❌)，也会让 CMF 的 rolling(20).sum()
        # 因为窗口里含有 NaN 而整段变成 NaN。这里直接丢掉这种未完成的幽灵行，
        # 只用最后一个真正有收盘价的交易日。
        df = df.dropna(subset=['Close'])

        if df.empty or len(df) < 60:
            print(f"{ticker:<12} ❌ 数据不足")
            continue

        close = df['Close']
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        ma20 = close.rolling(20).mean()
        ma50 = close.rolling(50).mean()
        rsi = calc_rsi_wilder(close, 14)
        cmf = calc_cmf(df)
        macd_line, signal_line, hist = calc_macd(close)

        c = float(close.iloc[-1])
        m20 = float(ma20.iloc[-1])
        m50 = float(ma50.iloc[-1])
        r = float(rsi.iloc[-1])
        cm = float(cmf.iloc[-1])

        banker, hot, retail, dominant, mcdx_score = calc_mcdx(close)
        macd_score = calc_macd_score(hist)
        vol_score = calc_vol_score(df)

        total_weight = MCDX_WEIGHT + MACD_WEIGHT + VOL_WEIGHT
        total_score = (mcdx_score * MCDX_WEIGHT + macd_score * MACD_WEIGHT + vol_score * VOL_WEIGHT) / total_weight

        trend_bull = c > m20 > m50
        cmf_bull = cm > 0
        rsi_bull = r > 50

        if total_score >= 70:
            signal = "🟢 买入"
        elif total_score >= 35:
            signal = "🟡 关注"
        else:
            signal = "🔴 避免"

        results.append({
            'ticker': ticker, 'close': c, 'total_score': total_score, 'signal': signal,
            'rsi': r, 'cmf': cm, 'banker': banker, 'hot': hot, 'retail': retail,
            'dominant': dominant, 'trend_bull': trend_bull, 'cmf_bull': cmf_bull, 'rsi_bull': rsi_bull,
        })

        print(f"{ticker:<12} ${c:>9.2f}  总分:{total_score:>6.1f} {signal}  "
              f"MCDX:{dominant_text(dominant):<8} B{banker:>4.1f}/H{hot:>4.1f}/R{retail:>4.1f}  "
              f"RSI:{r:>5.1f}  趋势:{'✅' if trend_bull else '❌'}")

    except Exception as e:
        print(f"{ticker:<12} ❌ {str(e)[:40]}")

results.sort(key=lambda x: -x['total_score'])

print(f"\n{'='*100}")
print("🏆 Top 5 真实信号\n")
for x in results[:5]:
    print(f"{x['ticker']:<12} ${x['close']:>9.2f}  总分:{x['total_score']:>6.1f} {x['signal']}  "
          f"MCDX:{dominant_text(x['dominant']):<8} RSI:{x['rsi']:>5.1f} CMF:{x['cmf']:>6.3f}")

print(f"\n✨ 现在去 TradingView 确认这些股票的 K 线！\n")
