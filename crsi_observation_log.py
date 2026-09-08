#!/usr/bin/env python3
# crsi_observation_log.py — 周线 CRSI(2,5,8) 纯观察记录，不产生任何买卖信号
# 用法: python3 crsi_observation_log.py [ticker ...]
# 不带参数则跑 WATCHLIST。追加写入 crsi_observation_log.csv，同日同票不重复。

import os
import sys
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yfinance as yf

# ---- 参数（Fu 自选，非 Connors 默认 3/2/100，未经样本外验证）----
RSI_LEN = 2
UPDOWN_LEN = 5
ROC_LEN = 8

LOG_FILE = "crsi_observation_log.csv"
PERIOD = "7y"

WATCHLIST = [
    "5026.KL", "7103.KL", "7233.KL", "8702.KL", "7161.KL",
    "1015.KL", "1066.KL", "6491.KL", "8907.KL", "5263.KL",
    "0099.KL", "5135.KL", "5142.KL", "5031.KL", "5681.KL",
    "4863.KL", "8869.KL", "5211.KL", "6459.KL", "0225.KL",
]


def wilder_rsi(series, length):
    """Wilder 平滑 RSI，对齐 Pine 的 ta.rsi()"""
    delta = series.diff()
    up = delta.clip(lower=0.0)
    down = (-delta).clip(lower=0.0)
    roll_up = up.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()
    roll_down = down.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()
    rs = roll_up / roll_down.replace(0.0, np.nan)
    rsi = 100.0 - 100.0 / (1.0 + rs)
    # 全跌段 roll_down=0 时 rs=NaN，按定义应为 100
    rsi = rsi.where(~((roll_down == 0) & (roll_up > 0)), 100.0)
    rsi = rsi.where(~((roll_up == 0) & (roll_down > 0)), 0.0)
    return rsi


def updown_streak(close):
    """Connors 的连涨/连跌计数：连涨 +1,+2...，连跌 -1,-2...，持平归 0"""
    out = np.zeros(len(close), dtype=float)
    vals = close.values
    for i in range(1, len(vals)):
        if vals[i] > vals[i - 1]:
            out[i] = out[i - 1] + 1 if out[i - 1] > 0 else 1
        elif vals[i] < vals[i - 1]:
            out[i] = out[i - 1] - 1 if out[i - 1] < 0 else -1
        else:
            out[i] = 0
    return pd.Series(out, index=close.index)


def percent_rank(series, length):
    """对齐 Pine ta.percentrank：过去 length 根中低于当前值的比例(%)"""
    def _rank(w):
        cur = w[-1]
        prior = w[:-1]
        return 100.0 * (prior < cur).sum() / len(prior)
    return series.rolling(length + 1).apply(_rank, raw=True)


def compute_crsi(close):
    """CRSI = (RSI(close,a) + RSI(streak,b) + percentrank(ROC1,c)) / 3
    返回含三个分量的 DataFrame，便于日后拆开看是哪一项在驱动"""
    r1 = wilder_rsi(close, RSI_LEN)
    r2 = wilder_rsi(updown_streak(close), UPDOWN_LEN)
    roc1 = close.pct_change() * 100.0
    r3 = percent_rank(roc1, ROC_LEN)
    return pd.DataFrame({
        "rsi_comp": r1,
        "updown_comp": r2,
        "roc_comp": r3,
        "crsi": (r1 + r2 + r3) / 3.0,
    })


def to_weekly(df):
    """周线重采样(W-FRI)，丢弃未收完的当周"""
    wk = df.resample("W-FRI").agg({
        "Open": "first", "High": "max", "Low": "min",
        "Close": "last", "Volume": "sum",
    }).dropna(subset=["Close"])
    if len(wk) == 0:
        return wk
    last_bar = wk.index[-1]
    if df.index[-1] < last_bar:
        wk = wk.iloc[:-1]
    return wk


def fetch(ticker):
    df = yf.download(ticker, period=PERIOD, auto_adjust=True,
                     progress=False, threads=False)
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def load_existing():
    if not os.path.exists(LOG_FILE):
        return set()
    try:
        old = pd.read_csv(LOG_FILE, usecols=["week_end", "ticker"])
        return set(zip(old["week_end"].astype(str), old["ticker"].astype(str)))
    except Exception as e:
        print("[警告] 读取旧日志失败，本次不做去重: %s" % e)
        return set()


def clean_tickers(args):
    """过滤掉 #注释行、空串，去重并保序"""
    out, seen_t = [], set()
    for a in args:
        a = a.strip()
        if not a or a.startswith("#"):
            continue
        if a not in seen_t:
            seen_t.add(a)
            out.append(a)
    return out


def main():
    args = sys.argv[1:]
    if args and args[0] == "--all":
        from bursa_universe import ALL_TICKERS, KNOWN_BAD_TICKERS
        tickers = [t for t in ALL_TICKERS if t not in KNOWN_BAD_TICKERS]
        source = "bursa_all"
    elif args:
        tickers = clean_tickers(args)
        source = os.environ.get("CRSI_SOURCE", "adhoc")
    else:
        tickers = WATCHLIST
        source = "watchlist"
    seen = load_existing()
    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []

    print("周线 CRSI(%d,%d,%d) 观察记录 — 纯记录，不产生买卖信号" %
          (RSI_LEN, UPDOWN_LEN, ROC_LEN))
    print("共 %d 只\n" % len(tickers))
    print("%-10s %10s %8s %8s %8s %6s" %
          ("ticker", "week_end", "CRSI", "上周", "上上周", "连续>70"))
    print("-" * 56)

    for t in tickers:
        df = fetch(t)
        if df is None:
            print("%-10s  下载失败/空" % t)
            continue
        wk = to_weekly(df)
        need = max(RSI_LEN, UPDOWN_LEN, ROC_LEN) + 12
        if len(wk) < need:
            print("%-10s  周线根数不足(%d<%d)，跳过" % (t, len(wk), need))
            continue

        c = compute_crsi(wk["Close"]).dropna()
        if len(c) < 3:
            print("%-10s  CRSI 有效值不足，跳过" % t)
            continue

        cur = c.iloc[-1]
        prev1 = c["crsi"].iloc[-2]
        prev2 = c["crsi"].iloc[-3]
        week_end = c.index[-1].strftime("%Y-%m-%d")

        # 仅为打印参考，不写入 CSV，也不构成信号
        streak = 0
        for v in reversed(c["crsi"].tolist()):
            if v > 70:
                streak += 1
            else:
                break

        print("%-10s %10s %8.2f %8.2f %8.2f %6d" %
              (t, week_end, cur["crsi"], prev1, prev2, streak))

        if (week_end, t) in seen:
            continue

        rows.append({
            "run_ts": run_ts,
            "week_end": week_end,
            "ticker": t,
            "close": round(float(wk["Close"].iloc[-1]), 4),
            "high": round(float(wk["High"].iloc[-1]), 4),
            "low": round(float(wk["Low"].iloc[-1]), 4),
            "crsi": round(float(cur["crsi"]), 4),
            "rsi_comp": round(float(cur["rsi_comp"]), 4),
            "updown_comp": round(float(cur["updown_comp"]), 4),
            "roc_comp": round(float(cur["roc_comp"]), 4),
            "crsi_prev1": round(float(prev1), 4),
            "crsi_prev2": round(float(prev2), 4),
            "params": "%d/%d/%d" % (RSI_LEN, UPDOWN_LEN, ROC_LEN),
            "source": source,
        })

    if not rows:
        print("\n无新增记录（本周数据已记录过，或全部跳过）")
        return

    out = pd.DataFrame(rows)
    header = not os.path.exists(LOG_FILE)
    out.to_csv(LOG_FILE, mode="a", header=header, index=False)
    print("\n新增 %d 条 → %s" % (len(rows), LOG_FILE))
    print("提醒：本文件仅供日后样本外检验，当前不得据此交易。")


if __name__ == "__main__":
    main()

