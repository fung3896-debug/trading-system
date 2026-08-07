# -*- coding: utf-8 -*-
"""
planb_daily_scan.py —— 改进版 Plan B 日常扫描
用回测验证过的规则:日周月共振(>=55) + 庄家持续性甜蜜点(0.60~0.85)
"""
import warnings
warnings.filterwarnings('ignore')
import yfinance as yf
import pandas as pd

import v7pro_mcdx_scan as v7
import planb_bridge as br
import numpy as np

# ===== 月线双满共振(样外观察用,不参与甜蜜点买入判断)=====
def _calc_rsi(close, length):
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    ag = gain.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    al = loss.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    rs = ag / al.replace(0, 1e-10)
    return 100 - (100/(1+rs))

def _calc_cmf(df, length=20):
    hl = (df['High'] - df['Low']).replace(0, 1e-10)
    mfv = ((df['Close']-df['Low'])-(df['High']-df['Close']))/hl*df['Volume']
    return mfv.rolling(length).sum() / df['Volume'].rolling(length).sum()

def _calc_mcdx_comp(close, length, base, sens):
    r = _calc_rsi(close, length)
    return ((r - base) * sens).clip(0, 100)

def _f_score_series(df):
    close = df['Close']
    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal_line
    cmf = _calc_cmf(df, 20)
    rsi = _calc_rsi(close, 14)
    vol_ma = df['Volume'].rolling(20).mean()
    banker = _calc_mcdx_comp(close, 50, 50, 1.5)
    compare = _calc_mcdx_comp(close, 30, 30, 1.0)
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

def check_monthly_double_attack(df):
    """回传 (是否双满, 最新月线dwmScore) ,数据不足回传 (False, None)"""
    monthly = v7.resample_ohlcv(df, 'ME')
    if len(monthly) < 210:
        return False, None
    score = _f_score_series(monthly)
    is_strong = score >= 70
    if len(is_strong) < 2:
        return False, None
    double = bool(is_strong.iloc[-1] and is_strong.iloc[-2])
    return double, float(score.iloc[-1])

# 甜蜜点(回测验证:0.60-0.85 表现最好,满仓1.00反而差)
RED_LOW, RED_HIGH = 0.60, 0.85
WARN_HIGH = 0.85   # 超过此值 = 提高警惕(可能出货期)

TICKERS = ['7233.KL', '5211.KL', '8907.KL', '6459.KL', '5249.KL', '5026.KL',
           '5286.KL', '0225.KL', '0099.KL', '5031.KL', '5681.KL', '7163.KL',
           '8869.KL', '1066.KL', '0215.KL', '7103.KL', '5263.KL',
           '4863.KL', '5243.KL', '5142.KL']


def clean(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=['Close'])


print("="*95)
print("📊 改进版 Plan B 日常扫描  |  共振>=55 + 庄家持续性甜蜜点(0.60~0.85)")
print("="*95)

buy_list, watch_list = [], []

for tk in TICKERS:
    try:
        df = clean(yf.download(tk, period='7y', auto_adjust=True, progress=False))
        if len(df) < br._MIN_TF_LEN + 60:
            print(f"{tk:<10} ⏭  数据不足")
            continue

        res = br.compute_resonance_score(df)       # 日周月三层最弱的 mcdx_score
        pers = br.compute_persistence(df)          # {'red_ratio','red_streak'}
        rr = pers['red_ratio']

        if rr is None:
            print(f"{tk:<10} 共振:{res:>6.1f}  ⏭  月线历史不足5年,无法判断持续性")
            continue

        resonance_ok = res >= 55
        sweet_ok = RED_LOW <= rr <= RED_HIGH

        if resonance_ok and sweet_ok:
            tag = "🟢 甜蜜点买入"
            buy_list.append((tk, res, rr, pers['red_streak']))
        elif resonance_ok and rr > WARN_HIGH:
            tag = "🟡 共振但满仓(警惕出货)"
            watch_list.append((tk, res, rr, pers['red_streak']))
        elif resonance_ok and rr < RED_LOW:
            tag = "⚪ 共振但持续性不足"
        else:
            tag = "🔴 未共振"

        double_attack, dwm_score = check_monthly_double_attack(df)
        da_tag = "🔥双满共振" if double_attack else ""

        print(f"{tk:<10} 共振:{res:>6.1f}  红色占比:{rr:>5.2f}  连续红:{pers['red_streak']:>2}月  {tag}  {da_tag}")

        try:
            import csv, os
            from datetime import datetime as _dt
            DA_LOG = os.path.expanduser('~/Documents/PlanB_Scanner/monthly_double_attack_log.csv')
            new_f = not os.path.exists(DA_LOG)
            with open(DA_LOG, 'a', newline='') as lf:
                w = csv.writer(lf)
                if new_f:
                    w.writerow(['记录日', '股票', '双满共振', 'dwm月分数', '当日收盘'])
                w.writerow([_dt.now().strftime('%Y-%m-%d'), tk, double_attack,
                           round(dwm_score, 1) if dwm_score is not None else '',
                           round(float(df['Close'].iloc[-1]), 3)])
        except Exception:
            pass

    except Exception as e:
        print(f"{tk:<10} ❌ {str(e)[:40]}")

print("\n" + "="*95)
print(f"🟢 甜蜜点买入清单({len(buy_list)} 支)—— 回测胜率63.6%,中位超额3.43%")
print("="*95)
if buy_list:
    for tk, res, rr, streak in sorted(buy_list, key=lambda x: -x[1]):
        print(f"  {tk:<10} 共振{res:.0f}  红色占比{rr:.2f}  连续红{streak}月")
else:
    print("  今天没有股票落在甜蜜点。宁缺勿滥。")

if watch_list:
    print(f"\n🟡 满仓警惕清单({len(watch_list)} 支)—— 共振够但庄家可能在出货,别追")
    for tk, res, rr, streak in watch_list:
        print(f"  {tk:<10} 共振{res:.0f}  红色占比{rr:.2f}(>0.85)")

print("\n提醒:0.85 是警戒线不是铁律,超过就缩仓提高警惕,别机械一刀切。")

# ===== 样外验证日记:自动记录甜蜜点信号 =====
import csv, os
from datetime import datetime
LOG = 'sweet_spot_log.csv'
if buy_list:
    new_file = not os.path.exists(LOG)
    with open(LOG, 'a', newline='') as f:      # 'a' = 追加,不覆盖
        w = csv.writer(f)
        if new_file:
            w.writerow(['记录日', '股票', '共振', 'red_ratio', '连续红月', '当日收盘'])
        today = datetime.now().strftime('%Y-%m-%d')
        for tk, res, rr, streak in buy_list:
            try:
                px = float(clean(yf.download(tk, period='5d', progress=False))['Close'].iloc[-1])
            except Exception:
                px = ''
            w.writerow([today, tk, round(res, 1), round(rr, 3), streak, px])
    print(f"\n📝 已记入样外日记: {LOG}")
