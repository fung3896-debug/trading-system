#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
all_klse_sweetspot.py — 全马股甜蜜点扫描（重建版，2026-09-01）
================================================================
取代已遗失的 all_klse_sweetspot_colab.py。差别：

  1. 股票池来自 bursa_universe.py（812支/13板块，含之前漏掉的 telecom），
     不再内嵌副本 —— 昨天那个 724支 / "0245" 缺 .KL 的问题不会再发生。
  2. 共振与持续性一律走 chat_core/planb_bridge.py，跟 planb_daily_scan
     用同一套逻辑，不再各自实作。
  3. 批次下载取代逐支下载（794支/414秒 已实测）。
  4. persistence 用 exclude_incomplete=True（排除未走完的当月柱）。
     注意：planb_daily_scan.py 仍用旧口径(False)以保护 sweet_spot_log.csv
     的连续记录，所以两支扫描器对同一支股票的 red_ratio 可能差 1/18
     (≈0.056)，0.85 边缘的股票可能一边进甜蜜点、一边进满仓警惕。
     这是刻意的取舍，不是 bug。要全面统一口径必须重跑所有回测。

规则（沿用 511 信号回测口径）：
    甜蜜点   resonance >= 55 且 0.60 <= red_ratio <= 0.85
    满仓警惕 resonance >= 55 且 red_ratio > 0.85（历史上表现最弱）

用法:
    python3 all_klse_sweetspot.py                 # 全池扫描
    python3 all_klse_sweetspot.py 7161.KL 8907.KL # 只跑指定股票
"""

import sys
import time
import warnings
from datetime import datetime

import pandas as pd
import yfinance as yf


from bursa_universe import ALL_TICKERS, TICKER_NAMES, TICKER_TO_SECTOR, KNOWN_BAD_TICKERS
from planb_bridge import compute_resonance_score, compute_persistence

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------- 参数
PERIOD = "7y"           # 月线持续性要 18 个月 + RSI(50) 暖机，7y 是锁定值
RESONANCE_MIN = 55.0
RED_RATIO_LO = 0.60
RED_RATIO_HI = 0.85
CHUNK = 40              # 批次下载每批支数
SKIP_KNOWN_BAD = True   # 跳过 KNOWN_BAD_TICKERS（目前只有 5235.KL KLCC）


def is_sweet_spot(resonance, red_ratio):
    """甜蜜点判定。这一行是整套规则的唯一定义，之前只存在于注解里。"""
    if resonance is None or red_ratio is None:
        return False
    return resonance >= RESONANCE_MIN and RED_RATIO_LO <= red_ratio <= RED_RATIO_HI


def is_saturated(resonance, red_ratio):
    """满仓警惕：共振够但已进极端强势区。"""
    if resonance is None or red_ratio is None:
        return False
    return resonance >= RESONANCE_MIN and red_ratio > RED_RATIO_HI


def analyse_one(ticker, df):
    """对单支已下载好的 OHLCV 算共振与持续性。"""
    resonance = compute_resonance_score(df)
    if resonance is None or resonance <= -999.0:
        return None
    pers = compute_persistence(df, exclude_incomplete=True)
    red_ratio = pers.get("red_ratio")
    if red_ratio is None:          # 根数不足，不能拿 0.0 冒充"无庄家"
        return None
    return {
        "ticker": ticker,
        "name": TICKER_NAMES.get(ticker, ""),
        "sector": TICKER_TO_SECTOR.get(ticker, ""),
        "date": df.index[-1].date(),
        "close": round(float(df["Close"].iloc[-1]), 3),
        "resonance": round(float(resonance), 1),
        "red_ratio": round(float(red_ratio), 3),
        "red_streak": int(pers.get("red_streak", 0)),
        "is_sweet": is_sweet_spot(resonance, red_ratio),
        "is_saturated": is_saturated(resonance, red_ratio),
    }


def scan(tickers):
    rows, failed = [], []
    t0 = time.time()
    total = len(tickers)

    for i in range(0, total, CHUNK):
        batch = tickers[i:i + CHUNK]
        try:
            raw = yf.download(batch, period=PERIOD, interval="1d",
                              auto_adjust=False, progress=False,
                              group_by="ticker", threads=True)
        except Exception as e:
            failed += [(t, f"download: {str(e)[:40]}") for t in batch]
            continue

        for tk in batch:
            try:
                d = raw[tk] if len(batch) > 1 else raw
                d = d[["Open", "High", "Low", "Close", "Volume"]].dropna()
                if len(d) < 60:
                    failed.append((tk, f"仅{len(d)}根"))
                    continue
                r = analyse_one(tk, d)
                if r is None:
                    failed.append((tk, "指标算不出"))
                else:
                    rows.append(r)
            except Exception as e:
                failed.append((tk, str(e)[:40]))

        done = min(i + CHUNK, total)
        print(f"  {done}/{total}  已用时{time.time() - t0:.0f}秒", end="\r")

    print()
    return pd.DataFrame(rows), failed


def main():
    cli = [t for t in sys.argv[1:] if t.endswith(".KL")]
    if cli:
        tickers = cli
    else:
        tickers = [t for t in ALL_TICKERS
                   if not (SKIP_KNOWN_BAD and t in KNOWN_BAD_TICKERS)]

    print("=" * 78)
    print(f"📊 全马股甜蜜点扫描 (共{len(tickers)}支)  |  "
          f"共振>={RESONANCE_MIN:.0f} + 强势持续度{RED_RATIO_LO}~{RED_RATIO_HI}")
    print(f"   {datetime.now():%Y-%m-%d %H:%M}  |  period={PERIOD}(锁定)")
    print("=" * 78)

    df, failed = scan(tickers)
    if df.empty:
        print("⚠️ 没有任何股票算出结果")
        return

    sweet = df[df["is_sweet"]].sort_values("resonance", ascending=False)
    saturated = df[df["is_saturated"]].sort_values("resonance", ascending=False)

    print("\n" + "=" * 78)
    print(f"🟢 甜蜜点买入清单 ({len(sweet)} 支)")
    print("=" * 78)
    for _, r in sweet.iterrows():
        print(f"  {r['ticker']:<10} {r['name']:<10} 共振{r['resonance']:>5.0f}  "
              f"强势持续度{r['red_ratio']:.2f}  连续{r['red_streak']}月  {r['sector']}")

    print("\n" + "=" * 78)
    print(f"🟡 满仓警惕清单 ({len(saturated)} 支) —— 共振够但已到极端强势区")
    print("=" * 78)
    for _, r in saturated.iterrows():
        print(f"  {r['ticker']:<10} {r['name']:<10} 共振{r['resonance']:>5.0f}  "
              f"强势持续度{r['red_ratio']:.2f}(>{RED_RATIO_HI})  {r['sector']}")

    print(f"\n跳过 {len(failed)} 支")
    if failed:
        print(f"  样本: {failed[:8]}")

    fn = f"all_klse_sweetspot_{datetime.now():%Y%m%d}.csv"
    df.to_csv(fn, index=False)
    print(f"\n📝 已存档: {fn}  (全部{len(df)}支的原始数据)")
    print("\n提醒: 强势持续度不是庄家持仓比例，是月线 dominant==0 的月份占比。")
    print("      0.85 是警戒线不是铁律，别机械一刀切。")


if __name__ == "__main__":
    main()
