#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Industry MCDX Tier 分类 + 完整 Sweet Spot 批量扫描
====================================================
复用 v7pro_mcdx_scan.py 的 calc_mcdx_series() / analyze_timeframe_last() 和
dwm_macd_scanner.py 的 check_dwm_signal()，对指定股票清单做：
  1. Tier 分类 (weekly / monthly mcdx_score 是否达到满分 100)
  2. red_ratio / red_streak (月线庄家主导持续性，18个月窗口)
  3. 完整 Sweet Spot 判定 (日周月共振 >= 55 且 red_ratio 落在 0.60~0.85)
  4. 流动性过滤 (近20日均成交额 < RM50,000 剔除)

【重要偏差说明 - 数据周期】
题目要求 period="1y"（约240根日K），但月线 red_ratio 需要最近18个月的
月线 dominant 判定，而月线 banker RSI(period=50) 本身就需要至少50根月K
才有第一个非NaN读数（50+18=68个月 ≈ 5.7年历史才能拿到完整18个月窗口）。
只抓1年数据的话，月线读数永远是 None，Tier/red_ratio 逻辑整个无法运作。
因此本脚本改为抓取 7年 日线（与 v7pro_mcdx_scan.py / dwm_macd_scanner.py
现有的 period='7y' 一致），日/周分数仍然只取最后一根的读数——RSI 只看
固定回看窗口，多抓历史只是让暖机更稳，不影响最新读数本身。
历史不足 18个月/50个月 的新股会被如实标记为「monthly 数据不足」，不会
被丢弃，对齐 scanner.md 里「新股例外」的规则。

本脚本设计为在【本地机器】运行 (需要能连到 Yahoo Finance，且
~/Documents/PlanB_Scanner/ 是本机目录)。
"""

import os
import sys
import csv
import json
import warnings
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import yfinance as yf

from v7pro_mcdx_scan import (
    calc_mcdx_series,
    resample_ohlcv,
    analyze_timeframe_last,
    compute_resonance_score,
    compute_monthly_persistence,
    is_sweet_spot,
    scan_sweet_spot,
    BANKER_PERIOD,
    HOT_PERIOD,
    STRONG_TH,
    MEDIUM_TH,
    DWM_BULL_TH,
    DWM_STRONG_TH,
    RED_RATIO_LOW,
    RED_RATIO_HIGH,
    PERSIST_WINDOW_MONTHS,
    SWEET_SPOT_RESONANCE_MIN,
)
from dwm_macd_scanner import check_dwm_signal

# =====================================================
# 0. 股票清单 (Bursa Malaysia, 39支要求 -> 实际收到35支，见脚本末尾说明)
# =====================================================
TICKERS = OrderedDict([
    ("8869.KL", "PMETAL"),
    ("5183.KL", "PCHEM"),
    ("5211.KL", "SUNWAY"),
    ("3794.KL", "MCEMENT"),
    ("5273.KL", "CHINHIN"),
    ("5340.KL", "UMSINT"),
    ("0151.KL", "KGB"),
    ("3034.KL", "HAPSENG"),
    ("4731.KL", "SCIENTX"),
    ("9822.KL", "SAM"),
    ("7172.KL", "PMBTECH"),
    ("5151.KL", "HEXTAR"),
    ("0225.KL", "SCGBHD"),
    ("0270.KL", "NATGATE"),
    ("5330.KL", "TMK"),
    ("5000.KL", "HUMEIND"),
    ("3476.KL", "KSENG"),
    ("8907.KL", "EG"),
    ("5916.KL", "MSC"),
    ("3395.KL", "BJCORP"),
    ("5327.KL", "MEGAFB"),
    ("7100.KL", "UCHITEC"),
    ("7233.KL", "DUFU"),
    ("2852.KL", "CMSB"),
    ("4758.KL", "ANCOMNY"),
    ("5271.KL", "PECCA"),
    ("5302.KL", "ATECH"),
    ("6963.KL", "VS"),
    ("6491.KL", "KFIMA"),
    ("7241.KL", "NGGB"),
    ("6971.KL", "KOBAY"),
    ("5284.KL", "LCTITAN"),
    ("0161.KL", "HEXIND"),
    ("0291.KL", "CHB"),
    ("5317.KL", "CPETECH"),
])

HOLDING_TICKER = "5026.KL"
HOLDING_NAME = "MHC"

# =====================================================
# 1. 参数
# =====================================================
FETCH_PERIOD = "7y"           # 见文件头【重要偏差说明】
LIQUIDITY_MIN_MYR = 50_000.0  # 近20日均成交额门槛
LIQUIDITY_LOOKBACK = 20

# red_ratio / resonance 的窗口与门槛现在统一定义在 v7pro_mcdx_scan.py
# (PERSIST_WINDOW_MONTHS / RED_RATIO_LOW / RED_RATIO_HIGH / SWEET_SPOT_RESONANCE_MIN)，
# 这里直接复用，避免跟那边的定义各写一份、日后悄悄跑偏。
RESONANCE_MIN = SWEET_SPOT_RESONANCE_MIN  # 55

DW_MIN_LEN = max(BANKER_PERIOD, HOT_PERIOD) + 10  # 60，跟 v7pro 保持一致

# Tier 分类允许纳入 sweet spot 起飞信号扫描的档位 (Tier 3 排除)
SWEET_SPOT_ALERT_TIERS = {"Tier 1", "Tier 1B", "Tier 2"}


# =====================================================
# 2. 数据获取
# =====================================================
def fetch_daily(ticker: str) -> pd.DataFrame:
    try:
        df = yf.download(ticker, period=FETCH_PERIOD, progress=False)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna(subset=["Close"])
        if df.empty:
            return None
        return df
    except Exception as e:
        print(f"  [警告] {ticker} 数据获取失败: {e}")
        return None


def compute_liquidity(df: pd.DataFrame):
    turnover = (df["Close"] * df["Volume"]).tail(LIQUIDITY_LOOKBACK)
    if turnover.empty:
        return None
    return float(turnover.mean())


# =====================================================
# 3. Tier 分类
# =====================================================
def classify_tier(w_score, m_score):
    cond_w = w_score is not None and w_score >= 100
    cond_m = m_score is not None and m_score >= 100
    if cond_w and cond_m:
        return "Tier 1"
    if cond_w and m_score is None:
        return "Tier 1B"
    if cond_w or cond_m:
        return "Tier 2"
    return "Tier 3"


# =====================================================
# 4. 单一股票完整分析
# =====================================================
def analyze_ticker(ticker: str, name: str):
    """回传 (record, df)。df 是原始日线 OHLCV (失败时为 None)，
    留给后面的 sweet spot 起飞信号扫描复用，不必重新抓一次。"""
    record = {"ticker": ticker, "name": name, "error": None}

    df = fetch_daily(ticker)
    if df is None or len(df) < DW_MIN_LEN:
        record["error"] = "数据不足"
        return record, None

    liquidity = compute_liquidity(df)
    record["liquidity_myr"] = liquidity
    record["liquidity_ok"] = liquidity is not None and liquidity >= LIQUIDITY_MIN_MYR

    d_tf = analyze_timeframe_last(df, min_len=DW_MIN_LEN)
    weekly_df = resample_ohlcv(df, "W")
    w_tf = analyze_timeframe_last(weekly_df, min_len=DW_MIN_LEN)
    monthly_df = resample_ohlcv(df, "ME")
    m_tf = analyze_timeframe_last(monthly_df, min_len=BANKER_PERIOD)

    d_score = d_tf["mcdx_score"] if d_tf else None
    w_score = w_tf["mcdx_score"] if w_tf else None
    m_score = m_tf["mcdx_score"] if m_tf else None

    red_ratio, red_streak, window_n = compute_monthly_persistence(df)

    record.update({
        "d_score": d_score,
        "w_score": w_score,
        "m_score": m_score,
        "red_ratio": red_ratio,
        "red_streak": red_streak,
        "red_window_months": window_n,
        "red_window_full": window_n == PERSIST_WINDOW_MONTHS,
        "tier": classify_tier(w_score, m_score),
        "is_new_listing": red_ratio is None,
    })

    resonance = compute_resonance_score(d_tf, w_tf, m_tf)
    record["resonance"] = resonance
    record["sweet_spot"] = is_sweet_spot(resonance, red_ratio)

    dwm = check_dwm_signal(ticker)
    record["dwm_macd_resonance"] = dwm.get("resonance") if dwm.get("valid") else None

    return record, df


# =====================================================
# 5. Sweet Spot 起飞信号 (刚进入区间，非旧信号)
# =====================================================
def scan_sweet_spot_alerts(pairs):
    """pairs: [(record, df), ...]，只挑 Tier 1/1B/2 + 流动性达标的股票，
    用 v7pro_mcdx_scan.scan_sweet_spot() 判断今天是否『刚进入』sweet spot。"""
    alerts = []
    for record, df in pairs:
        if record.get("error") or df is None:
            continue
        if record["tier"] not in SWEET_SPOT_ALERT_TIERS:
            continue
        if not record.get("liquidity_ok"):
            continue

        result = scan_sweet_spot(df)
        if result["just_entered"]:
            alerts.append({
                "ticker": record["ticker"],
                "name": record["name"],
                "resonance": result["resonance"],
                "red_ratio": result["red_ratio"],
                "entry_date": result["date"],
            })
    return alerts


# =====================================================
# 6. 输出
# =====================================================
TIER_ORDER = {"Tier 1": 0, "Tier 1B": 1, "Tier 2": 2, "Tier 3": 3}


def fmt(x, nd=1):
    if x is None:
        return "N/A"
    if isinstance(x, bool):
        return "是" if x else "否"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def build_row(r):
    new_flag = " ⭐新股" if r.get("is_new_listing") else ""
    return [
        r["ticker"], r["name"], r["tier"] + new_flag,
        fmt(r.get("d_score"), 0), fmt(r.get("w_score"), 0), fmt(r.get("m_score"), 0),
        fmt(r.get("red_ratio"), 2), fmt(r.get("red_streak"), 0),
        fmt(r.get("resonance"), 0),
        fmt(r.get("sweet_spot")),
        fmt(r.get("liquidity_myr"), 0),
    ]


HEADERS = ["代码", "名称", "Tier", "日", "周", "月", "red_ratio", "red_streak", "共振(min)", "完整SweetSpot", "20日均成交额(MYR)"]


def print_table(rows):
    widths = [max(len(str(h)), *(len(str(row[i])) for row in rows)) if rows else len(str(h))
              for i, h in enumerate(HEADERS)]
    line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(HEADERS))
    print(line)
    print("-" * len(line))
    for row in rows:
        print(" | ".join(str(row[i]).ljust(widths[i]) for i in range(len(HEADERS))))


def main():
    print(f"{'#'*100}\n📊 Industry MCDX Tier 分类 + 完整 Sweet Spot 批量扫描\n"
          f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n{'#'*100}")

    all_pairs = []
    for i, (ticker, name) in enumerate(TICKERS.items(), 1):
        print(f"[{i}/{len(TICKERS)}] 扫描 {ticker} ({name}) ...")
        all_pairs.append(analyze_ticker(ticker, name))
    all_records = [r for r, _df in all_pairs]

    print(f"\n[持仓] 扫描 {HOLDING_TICKER} ({HOLDING_NAME}) ...")
    holding_record, holding_df = analyze_ticker(HOLDING_TICKER, HOLDING_NAME)

    errored = [r for r in all_records if r.get("error")]
    ok_records = [r for r in all_records if not r.get("error")]
    excluded_liquidity = [r for r in ok_records if not r.get("liquidity_ok")]
    tier_records = [r for r in ok_records if r.get("liquidity_ok")]

    tier_records.sort(key=lambda r: (TIER_ORDER.get(r["tier"], 9), -(r.get("resonance") or -999)))

    print(f"\n{'='*100}\nTier 分类表 (已通过流动性过滤：近20日均成交额 >= RM{LIQUIDITY_MIN_MYR:,.0f})\n{'='*100}")
    print_table([build_row(r) for r in tier_records])

    sweet_spot_hits = [r for r in tier_records if r["sweet_spot"]]
    print(f"\n{'='*100}\n完整 Sweet Spot 命中 ({len(sweet_spot_hits)} 支)："
          f"共振>=55 且 red_ratio 落在 [{RED_RATIO_LOW},{RED_RATIO_HIGH}]\n{'='*100}")
    if sweet_spot_hits:
        print_table([build_row(r) for r in sweet_spot_hits])
    else:
        print("(本次扫描无命中)")

    sweet_spot_alerts = scan_sweet_spot_alerts(all_pairs)
    print(f"\n{'='*100}\n🚀 Sweet Spot 起飞信号 ({len(sweet_spot_alerts)} 支，仅限 Tier 1/1B/2 且今天『刚进入』区间)\n{'='*100}")
    if sweet_spot_alerts:
        for a in sweet_spot_alerts:
            entry_date = a["entry_date"].strftime("%Y-%m-%d") if a["entry_date"] is not None else "N/A"
            print(f"  🚀 {a['ticker']:<10} {a['name']:<10} resonance={fmt(a['resonance'],0):<6} "
                  f"red_ratio={fmt(a['red_ratio'],2):<6} 进入日期={entry_date}")
    else:
        print("(本次扫描无新进入信号——沿用旧信号的股票不重复报)")

    if excluded_liquidity:
        print(f"\n{'='*100}\n流动性剔除 ({len(excluded_liquidity)} 支，近20日均成交额 < RM{LIQUIDITY_MIN_MYR:,.0f})\n{'='*100}")
        for r in excluded_liquidity:
            print(f"  {r['ticker']:<10} {r['name']:<10} 均成交额={fmt(r.get('liquidity_myr'), 0)}")

    if errored:
        print(f"\n{'='*100}\n数据获取失败/不足 ({len(errored)} 支)\n{'='*100}")
        for r in errored:
            print(f"  {r['ticker']:<10} {r['name']:<10} {r['error']}")

    print(f"\n{'='*100}\n持仓交叉核对: {HOLDING_TICKER} ({HOLDING_NAME})\n{'='*100}")
    if holding_record.get("error"):
        print(f"  ❌ {holding_record['error']}")
    else:
        print_table([build_row(holding_record)])
        print(f"  DWM MACD 金叉+零轴上方 三线共振: {fmt(holding_record.get('dwm_macd_resonance'))}")
        print(f"  流动性达标: {fmt(holding_record.get('liquidity_ok'))} "
              f"(20日均成交额={fmt(holding_record.get('liquidity_myr'), 0)} MYR)")
        if holding_df is not None:
            holding_sweet = scan_sweet_spot(holding_df)
            print(f"  今天是否『刚进入』Sweet Spot: {fmt(holding_sweet['just_entered'])} "
                  f"(今天在区间内: {fmt(holding_sweet['in_sweet_spot'])}，昨天在区间内: {fmt(holding_sweet['prev_in_sweet_spot'])})")

    # ---------------- 保存到本地 ----------------
    out_dir = Path.home() / "Documents" / "PlanB_Scanner" / f"industry_tier_scan_{datetime.now().strftime('%Y%m%d_%H%M')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(out_dir / "full_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "params": {
                "fetch_period": FETCH_PERIOD,
                "liquidity_min_myr": LIQUIDITY_MIN_MYR,
                "persist_window_months": PERSIST_WINDOW_MONTHS,
                "red_ratio_range": [RED_RATIO_LOW, RED_RATIO_HIGH],
                "resonance_min": RESONANCE_MIN,
            },
            "watchlist_results": all_records,
            "holding": holding_record,
            "sweet_spot_alerts": sweet_spot_alerts,
        }, f, ensure_ascii=False, indent=2, default=str)

    with open(out_dir / "tier_table.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        for r in tier_records:
            writer.writerow(build_row(r))

    with open(out_dir / "sweet_spot_hits.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        for r in sweet_spot_hits:
            writer.writerow(build_row(r))

    alert_headers = ["代码", "名称", "resonance", "red_ratio", "进入日期"]
    with open(out_dir / "sweet_spot_alerts.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(alert_headers)
        for a in sweet_spot_alerts:
            entry_date = a["entry_date"].strftime("%Y-%m-%d") if a["entry_date"] is not None else "N/A"
            writer.writerow([a["ticker"], a["name"], fmt(a["resonance"], 0), fmt(a["red_ratio"], 2), entry_date])

    print(f"\n✅ 结果已保存到: {out_dir}")
    print("   - full_results.json    (全部原始字段，含持仓 + 起飞信号)")
    print("   - tier_table.csv       (通过流动性过滤的 Tier 分类表)")
    print("   - sweet_spot_hits.csv  (完整 Sweet Spot 命中清单，含旧信号)")
    print("   - sweet_spot_alerts.csv (今天『刚进入』sweet spot 的起飞信号，不含旧信号)")


if __name__ == "__main__":
    main()

# =====================================================
# 附注：股票数量核对
# =====================================================
# 任务描述写"39只"，但实际给出的清单只有35个代码 (PMETAL...CPETECH)。
# 本脚本按实际收到的35个代码运行，MHC(5026.KL)持仓另外单独核对，
# 合计36支。如果确实还有4支遗漏，请补充代码后重新运行。
