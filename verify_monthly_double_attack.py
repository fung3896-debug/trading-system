# -*- coding: utf-8 -*-
"""
验证假设:月线连续两次 dwmScore>=70(强共振),后续60天表现如何?
不求绝对,只求有没有 edge(vs 无信号时的基准水平)。
"""
import warnings
warnings.filterwarnings('ignore')
import numpy as np
import pandas as pd
import yfinance as yf

STRONG_TH = 70
FORWARD = 60

TICKERS = ['7233.KL', '5211.KL', '8907.KL', '6459.KL', '5249.KL', '5026.KL',
           '5286.KL', '0225.KL', '0099.KL', '5031.KL', '5681.KL', '7163.KL',
           '8869.KL', '1066.KL', '0215.KL', '7103.KL', '5263.KL',
           '4863.KL', '5243.KL', '5142.KL']


def calc_rsi(close, length):
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    ag = gain.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    al = loss.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    rs = ag / al.replace(0, 1e-10)
    return 100 - (100/(1+rs))


def calc_cmf(df, length=20):
    hl = (df['High'] - df['Low']).replace(0, 1e-10)
    mfv = ((df['Close']-df['Low'])-(df['High']-df['Close']))/hl*df['Volume']
    return mfv.rolling(length).sum() / df['Volume'].rolling(length).sum()


def calc_mcdx_comp(close, length, base, sens):
    r = calc_rsi(close, length)
    return ((r - base) * sens).clip(0, 100)


def f_score_series(df):
    close = df['Close']
    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()

    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal_line

    cmf = calc_cmf(df, 20)
    rsi = calc_rsi(close, 14)
    vol_ma = df['Volume'].rolling(20).mean()

    banker = calc_mcdx_comp(close, 50, 50, 1.5)
    compare = calc_mcdx_comp(close, 30, 30, 1.0)

    trend_bull = (close > ma20) & (ma20 > ma50)
    trend_bear = (close < ma20) & (ma20 < ma50)
    big_bull = close > ma200
    macd_bull = (hist > 0) & (hist > hist.shift(1))
    macd_bear = (hist < 0) & (hist < hist.shift(1))
    cmf_bull = cmf > 0
    cmf_bear = cmf < 0
    rsi_bull = rsi > 50
    rsi_bear = rsi < 50
    vol_bull = df['Volume'] > vol_ma
    mcdx_bull = (banker > compare) & (banker > 20)
    mcdx_bear = banker < compare

    score = pd.Series(0.0, index=df.index)
    score += np.where(trend_bull, 20, np.where(trend_bear, -20, 0))
    score += np.where(big_bull, 10, -10)
    score += np.where(macd_bull, 20, np.where(macd_bear, -20, 0))
    score += np.where(cmf_bull, 15, np.where(cmf_bear, -15, 0))
    score += np.where(rsi_bull, 10, np.where(rsi_bear, -10, 0))
    score += np.where(vol_bull, 10, 0)
    score += np.where(mcdx_bull, 15, np.where(mcdx_bear, -15, 0))
    return score


def clean(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=['Close'])


def resample_monthly(df):
    agg = pd.DataFrame({
        'Open': df['Open'].resample('ME').first(),
        'High': df['High'].resample('ME').max(),
        'Low': df['Low'].resample('ME').min(),
        'Close': df['Close'].resample('ME').last(),
        'Volume': df['Volume'].resample('ME').sum(),
    })
    return agg.dropna(subset=['Close'])


print("="*80)
print(f"验证假设:月线连续两次 dwmScore>={STRONG_TH}(强共振),后续{FORWARD}天表现")
print("="*80)

all_double, all_single, all_none = [], [], []

for tk in TICKERS:
    try:
        df = clean(yf.download(tk, period='max', auto_adjust=True, progress=False))
        if len(df) < 260 * 5:
            print(f"{tk:<10} ⏭ 数据不足")
            continue

        monthly = resample_monthly(df)
        if len(monthly) < 210:
            print(f"{tk:<10} ⏭ 月线不足")
            continue

        score = f_score_series(monthly)
        is_strong = score >= STRONG_TH
        double_attack = is_strong & is_strong.shift(1).fillna(False)

        daily_close = df['Close']

        for i in range(len(monthly) - 2):
            m_date = monthly.index[i]
            pos = daily_close.index.searchsorted(m_date)
            if pos >= len(daily_close) - FORWARD or pos == 0:
                continue
            p0 = float(daily_close.iloc[pos])
            p1 = float(daily_close.iloc[pos + FORWARD])
            ret = (p1 - p0) / p0

            if double_attack.iloc[i]:
                all_double.append(ret)
            elif is_strong.iloc[i]:
                all_single.append(ret)
            else:
                all_none.append(ret)

        print(f"{tk:<10} ✅ 月线{len(monthly)}根  双满{double_attack.sum()}次")

    except Exception as e:
        print(f"{tk:<10} ❌ {str(e)[:50]}")


def stats(arr, name):
    if len(arr) < 5:
        print(f"\n【{name}】样本太少(n={len(arr)}),暂不下结论")
        return
    arr = np.array(arr)
    win = (arr > 0).mean() * 100
    avg = arr.mean() * 100
    med = np.median(arr) * 100
    print(f"\n【{name}】 n={len(arr)}")
    print(f"  胜率 {win:.1f}%   平均收益 {avg:+.2f}%   中位收益 {med:+.2f}%")


print("\n" + "="*80)
print("结果:60天后表现对照")
print("="*80)
stats(all_double, "连续两次强共振(月)")
stats(all_single, "单次强共振(月)")
stats(all_none,   "非强共振(月,基准/随机水平)")

if len(all_double) >= 5 and len(all_none) >= 5:
    diff = np.mean(all_double)*100 - np.mean(all_none)*100
    print(f"\n>>> 连续两次强共振 vs 基准，平均收益差异: {diff:+.2f} 个百分点")
    print(">>> 提醒:这不代表'一定上涨'，只代表历史上这个状态下，平均表现是否优于基准。")
