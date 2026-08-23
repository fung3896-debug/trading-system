# -*- coding: utf-8 -*-
"""
planb_watchlist_crsi.py

对 planb_daily_scan.py 里那19支固定watchlist,额外查一次当前CRSI状态,
跟今天的sweet spot扫描结果放在一起看。

不解析 sweet_spot_log.csv (表头是中文,格式跟CRSI验证池的英文表头不一样)，
直接用已知的固定19支清单查CRSI,更简单可靠。

⚠️ 覆盖范围提醒: CRSI已验证的是市值前50大工业股,这19支watchlist跟那50支
重叠很少,大部分会标"未验证仅供参考"——这不代表CRSI在这些股票上无效,只是
还没有专门测试过,数值仅供参考,不代表已验证的结论。

运行方式:
    cd ~/Documents/PlanB_Scanner
    python3 planb_watchlist_crsi.py
"""

import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import yfinance as yf

RSI_SHORT = 3
STREAK_RSI_PERIOD = 2
ROC_RANK_PERIOD = 100
STRONG_TH = 80.0
CONSEC_WEEKS = 2

# 与 planb_daily_scan.py 第87-90行的 TICKERS 完全一致
TICKERS = ['7233.KL', '5211.KL', '8907.KL', '6459.KL', '5249.KL', '5026.KL',
           '5286.KL', '0225.KL', '0099.KL', '5031.KL', '5681.KL', '7163.KL',
           '8869.KL', '1066.KL', '0215.KL', '7103.KL', '5263.KL',
           '4863.KL', '5243.KL', '5142.KL']

CRSI_VALIDATED_TICKERS = {
    '8869.KL', '5183.KL', '5211.KL', '3794.KL', '0151.KL', '5273.KL', '5340.KL', '3034.KL',
    '4731.KL', '0270.KL', '7172.KL', '0225.KL', '5151.KL', '9822.KL', '5330.KL', '5000.KL',
    '3476.KL', '5916.KL', '8907.KL', '5327.KL', '7233.KL', '3395.KL', '7100.KL', '2852.KL',
    '5271.KL', '6963.KL', '5302.KL', '4758.KL', '7241.KL', '6971.KL', '5317.KL', '6491.KL',
    '0099.KL', '0161.KL', '0291.KL', '5284.KL', '5001.KL', '7095.KL', '7034.KL', '5665.KL',
    '7231.KL', '5015.KL', '7197.KL', '7609.KL', '5125.KL', '6874.KL', '7155.KL', '5298.KL',
    '5308.KL', '0196.KL',
}
CRSI_CORE_WATCHLIST = {'7095.KL', '8869.KL', '7172.KL', '3034.KL', '2852.KL'}
CRSI_WATCH_CLOSELY = {'5000.KL', '7233.KL', '7197.KL'}


def clean(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=['Close'])


def resample_ohlcv(df, rule):
    agg = pd.DataFrame({
        'Open': df['Open'].resample(rule).first(),
        'High': df['High'].resample(rule).max(),
        'Low': df['Low'].resample(rule).min(),
        'Close': df['Close'].resample(rule).last(),
        'Volume': df['Volume'].resample(rule).sum(),
    })
    return agg.dropna(subset=['Close'])


def calc_rsi_wilder(close, length):
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))


def calc_streak(close):
    direction = np.sign(close.diff())
    streak = pd.Series(0.0, index=close.index)
    cur, prev_dir = 0.0, 0.0
    for i, d in enumerate(direction.values):
        if pd.isna(d) or d == 0:
            cur = 0.0
        elif d == prev_dir or (cur == 0 and d != 0):
            cur = cur + d if cur != 0 else d
        else:
            cur = d
        streak.iloc[i] = cur
        prev_dir = d if d != 0 else prev_dir
    return streak


def percentile_rank(series, window):
    def _rank(x):
        if len(x) < 2:
            return np.nan
        return (x < x.iloc[-1]).sum() / (len(x) - 1) * 100
    return series.rolling(window).apply(_rank, raw=False)


def calc_crsi(ohlcv_df):
    close = ohlcv_df['Close']
    rsi_c = calc_rsi_wilder(close, RSI_SHORT)
    streak_c = calc_rsi_wilder(calc_streak(close), STREAK_RSI_PERIOD)
    roc_c = percentile_rank(close.pct_change(1) * 100, ROC_RANK_PERIOD)
    return (rsi_c + streak_c + roc_c) / 3.0


def get_crsi_status(symbol):
    try:
        df = clean(yf.download(symbol, period="max", auto_adjust=True, progress=False))
        if df.empty or len(df) < 400:
            return None
        weekly = resample_ohlcv(df, 'W')
        monthly = resample_ohlcv(df, 'ME')
        if len(weekly) < ROC_RANK_PERIOD + 20 or len(monthly) < ROC_RANK_PERIOD + 20:
            return None

        crsi_w = calc_crsi(weekly)
        crsi_m = calc_crsi(monthly)

        last_w = float(crsi_w.iloc[-1]) if not pd.isna(crsi_w.iloc[-1]) else None
        above = crsi_w >= STRONG_TH
        consec_now = bool(above.tail(CONSEC_WEEKS).all()) if len(above) >= CONSEC_WEEKS else False
        last_m = float(crsi_m.iloc[-1]) if not pd.isna(crsi_m.iloc[-1]) else None
        monthly_ok = bool(last_m is not None and last_m >= STRONG_TH)

        return {
            'crsi_weekly': round(last_w, 1) if last_w is not None else None,
            'triggered': consec_now,
            'crsi_monthly': round(last_m, 1) if last_m is not None else None,
            'monthly_confirmed': monthly_ok if consec_now else None,
        }
    except Exception as e:
        return {'error': str(e)[:50]}


def main():
    print("=" * 90)
    print("Plan B Watchlist (19支) —— CRSI当前状态查看")
    print("=" * 90)

    for t in TICKERS:
        status = get_crsi_status(t)
        if status is None:
            print(f"{t:<10} 数据不足")
            continue
        if 'error' in status:
            print(f"{t:<10} 错误: {status['error']}")
            continue

        if t in CRSI_CORE_WATCHLIST:
            tag = "★核心观察名单"
        elif t in CRSI_WATCH_CLOSELY:
            tag = "⚠️需额外小心(压力测试垫底股)"
        elif t in CRSI_VALIDATED_TICKERS:
            tag = "已验证池"
        else:
            tag = "未验证仅供参考"

        flag = "🔥双确认" if status['triggered'] and status['monthly_confirmed'] else \
               ("🟠仅周线" if status['triggered'] else "  ")
        print(f"{t:<10} {flag}  周CRSI={status['crsi_weekly']:>5}  "
              f"月CRSI={status['crsi_monthly']:>5}  [{tag}]")

    print("\n🔥 = 周线连续2周≥80 且 月线也≥80 (双确认，已验证信号)")
    print("🟠 = 仅周线连续2周≥80，月线未确认")


if __name__ == "__main__":
    main()

