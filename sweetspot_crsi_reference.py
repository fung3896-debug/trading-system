# -*- coding: utf-8 -*-
"""
sweetspot_crsi_reference.py

读取 planb_daily_scan.py 生成的 sweet spot 扫描结果CSV，对同一批股票额外
算一次当前CRSI状态，加成参考列输出成一份"增强报告"。

⚠️ 定位澄清：这不是把CRSI当筛选条件接入sweet spot判断逻辑，sweet_spot这个
标记完全不受影响。CRSI只是额外显示的参考信息，方便你在同一份报告里同时
看到两条独立信号线的状态，自己综合判断。不改动 planb_daily_scan.py 本身。

⚠️ 覆盖范围提醒：CRSI已验证的股票池是市值前50大工业股，跟sweet spot
watchlist(19-21支)重叠很少(压力测试显示只有4支共同覆盖)。如果sweet spot
报告里的股票不在CRSI验证过的50支范围内，这里显示的CRSI数值只是"能算出来"
的参考信息，不代表在这支股票上CRSI也一样有效——不要把已验证的结论套用到
没验证过的股票上。

用法:
    python3 sweetspot_crsi_reference.py <sweet_spot扫描输出的csv文件名>
    例如: python3 sweetspot_crsi_reference.py unified_scan_20260807_1401.csv

    如果不带参数，默认找当前目录下最新的 unified_scan_*.csv
"""

import sys
import glob
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

# CRSI已验证过的市值前50股票池，用来判断"参考"还是"已验证"
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
    """返回 (周线CRSI, 是否周线连续2周>=80, 月线CRSI, 是否月线也>=80)"""
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
            'crsi_weekly_consec2_ge80': consec_now,
            'crsi_monthly': round(last_m, 1) if last_m is not None else None,
            'crsi_monthly_confirmed': monthly_ok if consec_now else None,
        }
    except Exception as e:
        return {'error': str(e)[:50]}


def main():
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        candidates = sorted(glob.glob("unified_scan_*.csv"))
        if not candidates:
            print("找不到 unified_scan_*.csv，也没有指定文件名，退出")
            return
        csv_path = candidates[-1]
        print(f"未指定文件，使用最新的: {csv_path}")

    df = pd.read_csv(csv_path)
    if 'symbol' not in df.columns:
        print(f"{csv_path} 里没有 symbol 列，格式不对，退出")
        return

    print(f"读取 {len(df)} 支股票，开始额外计算CRSI参考信息...")

    rows = []
    for i, symbol in enumerate(df['symbol']):
        print(f"  [{i+1}/{len(df)}] {symbol} ...", end=" ", flush=True)
        status = get_crsi_status(symbol)
        if status is None:
            print("数据不足，跳过")
            rows.append({'symbol': symbol, 'crsi_数据': '不足'})
            continue
        if 'error' in status:
            print(f"错误: {status['error']}")
            rows.append({'symbol': symbol, 'crsi_数据': f"错误:{status['error']}"})
            continue

        validated = symbol in CRSI_VALIDATED_TICKERS
        core = symbol in CRSI_CORE_WATCHLIST
        tag = "★核心观察名单" if core else ("已验证池" if validated else "⚠️未验证仅供参考")
        status['crsi_验证状态'] = tag
        status['symbol'] = symbol
        rows.append(status)
        flag = "🔥" if status.get('crsi_weekly_consec2_ge80') else "  "
        print(f"{flag} 周CRSI={status.get('crsi_weekly')}  月CRSI={status.get('crsi_monthly')}  [{tag}]")

    crsi_df = pd.DataFrame(rows)
    merged = df.merge(crsi_df, on='symbol', how='left')

    out_name = csv_path.replace('.csv', '_with_crsi.csv')
    merged.to_csv(out_name, index=False, encoding='utf-8-sig')
    print(f"\n已保存增强报告: {out_name}")

    both_triggered = merged[
        (merged.get('sweet_spot') == True) &
        (merged.get('crsi_weekly_consec2_ge80') == True)
    ]
    if len(both_triggered) > 0:
        print(f"\n同时触发 sweet_spot 且 CRSI周线连续2周>=80 的股票: {len(both_triggered)} 支")
        print(both_triggered[['symbol', 'resonance', 'crsi_weekly', 'crsi_验证状态']].to_string(index=False))
    else:
        print("\n本次没有股票同时触发两套信号(这是正常的，两者重叠度本来就只有14.3%)")


if __name__ == "__main__":
    main()

