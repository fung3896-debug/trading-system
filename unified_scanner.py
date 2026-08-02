#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plan B 统一扫描器 —— 一次抓取，三套指标
=========================================================
把原本要跑两次的扫描合并成一次：
  1. MCDX Tier 分类 (weekly/monthly mcdx_score)     ← 复用 v7pro_mcdx_scan.py
  2. resonance + red_ratio + red_streak             ← 复用 planb_bridge.py
  3. VWAP 三层偏离 + A/D 方向 + 量比评分            ← 原 vwap_ad_scanner_fixed.py 逻辑
  4. banker_flag 诊断标签（双强/真庄家/纯游资）     ← 新增，不影响Tier/red_ratio计算

关键设计：每只股票只调用一次 yfinance，抓 7y 数据后分给三套指标用。
  - MCDX 月线需要 60 根月K (min_len = max(50,40)+10)，所以必须 7y，不能用 1y
  - red_ratio 需要 18 个月月线，7y 绰绰有余
  - VWAP 只需 2y，用 7y 的尾段即可

banker_flag 说明：
  banker 和 hot 两者若都逼近 strongTh 天花板（比如双强科技股），比大小会产生
  临界噪声，导致月度 dominant 在"庄家"/"游资"之间乱跳，进而让 red_ratio 显得
  偏低或不稳定。这个标签只做诊断展示，不改动 dominant/red_ratio 的原始计算口径
  （因为 sweet spot 的 0.60-0.85 区间是拿现有口径回测验证过的，不能换尺子）。

用法：
    python3 unified_scanner.py                    # 用内置默认清单
    python3 unified_scanner.py plantation.txt     # 用外部清单（一行一个代码，支持 #备注）

依赖：需与 v7pro_mcdx_scan.py、planb_bridge.py 放在同一目录
     (即 ~/Documents/PlanB_Scanner/)
"""

import warnings
warnings.filterwarnings('ignore')

import sys
import time
import random
import statistics
from datetime import datetime

import yfinance as yf
import pandas as pd
import numpy as np

# 复用既有模块（不重写任何指标逻辑）
import v7pro_mcdx_scan as v7
import planb_bridge as bridge


# =====================================================
# 参数
# =====================================================
FETCH_PERIOD = '7y'          # MCDX 月线需要 60 根月K，必须够长
MIN_AVG_TURNOVER = 200_000   # 20日日均成交额下限（令吉）
MIN_DAILY_BARS = 130         # 日线最少根数

MAX_RETRIES = 4
BASE_DELAY = 3.0
RATE_LIMIT_KEYWORDS = ("rate limit", "too many requests", "429")

# Sweet spot 规则（已验证）
SWEET_RESONANCE_MIN = 55.0
SWEET_RED_RATIO_LOW = 0.60
SWEET_RED_RATIO_HIGH = 0.85

# VWAP 滚动窗口
VWAP_DAILY_WIN = 20
VWAP_WEEKLY_WIN = 10
VWAP_MONTHLY_WIN = 6


# =====================================================
# 数据抓取（带限速重试）
# =====================================================
def build_session():
    try:
        from curl_cffi import requests as cffi_requests
        return cffi_requests.Session(impersonate="chrome")
    except Exception:
        return None

SESSION = build_session()


def fetch_with_retry(symbol, period=FETCH_PERIOD, max_retries=MAX_RETRIES):
    for attempt in range(max_retries):
        try:
            ticker = yf.Ticker(symbol, session=SESSION) if SESSION else yf.Ticker(symbol)
            df = ticker.history(period=period, timeout=20, auto_adjust=True)
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                return df.dropna(subset=['Close'])
            return None
        except Exception as e:
            msg = str(e).lower()
            if any(k in msg for k in RATE_LIMIT_KEYWORDS):
                wait = BASE_DELAY * (2 ** attempt) + random.uniform(0, 1.5)
                print(f"  限速，等待 {wait:.1f}s 重试 ({attempt+1}/{max_retries})...")
                time.sleep(wait)
                continue
            return None
    return None


# =====================================================
# VWAP / A-D 指标（原 vwap_ad_scanner 逻辑）
# =====================================================
def rolling_vwap(df, window):
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    pv = (tp * df['Volume']).rolling(window).sum()
    v = df['Volume'].rolling(window).sum()
    return pv / v


def ad_trend(df, lookback):
    rng = (df['High'] - df['Low']).replace(0, np.nan)
    clv = (2 * df['Close'] - df['High'] - df['Low']) / rng
    ad = (clv * df['Volume']).fillna(0).cumsum()
    if len(ad) < lookback + 1:
        return 0
    return float(ad.iloc[-1] - ad.iloc[-1 - lookback])


def calc_vwap_ad(df, weekly, monthly):
    """返回 VWAP 偏离度、A/D 方向、量比等；数据不足或流动性不达标返回 None"""
    if len(df) < MIN_DAILY_BARS:
        return None

    turnover_20d = float((df['Close'] * df['Volume']).iloc[-20:].mean())
    if turnover_20d < MIN_AVG_TURNOVER:
        return None

    vwap_d = rolling_vwap(df, VWAP_DAILY_WIN).iloc[-1]
    vwap_w = rolling_vwap(weekly, VWAP_WEEKLY_WIN).iloc[-1] if len(weekly) >= VWAP_WEEKLY_WIN else np.nan
    vwap_m = rolling_vwap(monthly, VWAP_MONTHLY_WIN).iloc[-1] if len(monthly) >= VWAP_MONTHLY_WIN else np.nan
    if any(pd.isna(x) for x in [vwap_d, vwap_w, vwap_m]):
        return None

    c = float(df['Close'].iloc[-1])
    prev_c = float(df['Close'].iloc[-2])
    change_pct = (c - prev_c) / prev_c * 100

    vol = df['Volume']
    avg10 = vol.iloc[-11:-1].mean()
    vol_ratio = float(vol.iloc[-1] / avg10) if avg10 > 0 else 0.0

    prior_avg = vol.iloc[-16:-6].mean()
    recent_avg = vol.iloc[-6:-1].mean()
    shrink_to_surge = bool(prior_avg > 0 and recent_avg / prior_avg < 0.7
                           and vol_ratio > 1.5 and change_pct > 0)

    stock_20d = (c / float(df['Close'].iloc[-21]) - 1) * 100 if len(df) > 21 else None

    return {
        'close': round(c, 3),
        'change%': round(change_pct, 2),
        'vol_ratio': round(vol_ratio, 2),
        'dv_daily%': round((c - vwap_d) / vwap_d * 100, 2),
        'dv_weekly%': round((c - vwap_w) / vwap_w * 100, 2),
        'dv_monthly%': round((c - vwap_m) / vwap_m * 100, 2),
        'ad_w_up': 1 if ad_trend(weekly, 5) > 0 else 0,
        'ad_m_up': 1 if ad_trend(monthly, 3) > 0 else 0,
        'shrink_to_surge': shrink_to_surge,
        'stock_20d%': round(stock_20d, 2) if stock_20d is not None else None,
        'turnover_20d': round(turnover_20d, 0),
    }


def score_vwap_ad(d, sector_median):
    """VWAP/AD 综合评分 + 风险标记（逻辑与原脚本一致）"""
    risks = []
    base = 0.0
    base += min(max(d['dv_daily%'], 0), 10) * 0.4
    base += min(max(d['dv_weekly%'], 0), 10) * 0.35
    base += min(max(d['dv_monthly%'], 0), 10) * 0.25
    base += d['ad_w_up'] * 1.5 + d['ad_m_up'] * 1.5

    vol_bonus = 0.0
    if d['vol_ratio'] > 2.0:
        if d['change%'] > 1:
            vol_bonus = 3
        elif d['change%'] < -1:
            vol_bonus = -2
            risks.append('放量下跌')
    elif d['vol_ratio'] > 1.5:
        if d['change%'] > 0:
            vol_bonus = 2
        elif d['change%'] < 0:
            vol_bonus = -1
            risks.append('放量滞涨')

    surge_bonus = 3.0 if d['shrink_to_surge'] else 0.0
    if surge_bonus > 0:
        risks.append('缩量突破启动')

    if base < 6:
        if vol_bonus > 0:
            vol_bonus *= 0.5
        surge_bonus *= 0.5

    score = base + vol_bonus + surge_bonus

    if sector_median is not None and d['stock_20d%'] is not None:
        rs = d['stock_20d%'] - sector_median
        d['rel_20d%'] = round(rs, 2)
        if rs > 3:
            score += 2
        elif rs > 0:
            score += 1
        elif rs < -3:
            score -= 1
            risks.append('弱于板块')
    else:
        d['rel_20d%'] = None

    if d['vol_ratio'] > 1.5 and d['dv_daily%'] < -1:
        risks.append('放量破日VWAP')

    d['base_trend'] = round(base, 2)
    return round(score, 2), risks


# =====================================================
# MCDX Tier 分类
# =====================================================
def classify_tier(w_score, m_score):
    """Tier 1: 周月都>=100 / Tier 1B: 周>=100但月缺 / Tier 2: 其一>=100 / Tier 3: 都<100"""
    if w_score is None and m_score is None:
        return "无数据"
    if w_score is not None and w_score >= 100:
        if m_score is None:
            return "Tier 1B"
        if m_score >= 100:
            return "Tier 1"
        return "Tier 2"
    if m_score is not None and m_score >= 100:
        return "Tier 2"
    return "Tier 3"


def banker_flag(d_tf, w_tf, m_tf):
    """诊断标签(不影响Tier/red_ratio计算)：
    区分'真庄家主导'/'纯游资主导'/'双强'/'混合不一致'
    banker和hot各自独立跟strongTh比，不互相比大小，避免两者都逼近
    天花板时的临界噪声被误判成'游资主导'或'庄家时有时无'"""
    def _classify(tf):
        if tf is None:
            return "none"
        banker_strong = tf['banker'] >= v7.STRONG_TH
        hot_strong = tf['hot'] >= v7.STRONG_TH
        if banker_strong and hot_strong:
            return "both"
        if banker_strong:
            return "banker"
        if hot_strong:
            return "hot"
        return "none"

    cats = [_classify(d_tf), _classify(w_tf), _classify(m_tf)]
    if all(c == "both" for c in cats):
        return "双强(庄家游资同强)"
    if all(c == "banker" for c in cats):
        return "真庄家DWM满控"
    if all(c == "hot" for c in cats):
        return "纯游资(无真庄家)"
    return "混合不一致"


# =====================================================
# 单股完整分析（一次抓取，三套指标）
# =====================================================
def analyze_one(symbol):
    df = fetch_with_retry(symbol)
    if df is None or len(df) < MIN_DAILY_BARS:
        return None, "数据不足/抓取失败"

    weekly = v7.resample_ohlcv(df, 'W')
    monthly = v7.resample_ohlcv(df, 'ME')

    # ---- 1. VWAP / A-D（同时做流动性过滤）----
    va = calc_vwap_ad(df, weekly, monthly)
    if va is None:
        return None, "流动性不足/VWAP数据不足"

    # ---- 2. MCDX 三层分数 ----
    min_len = bridge._MIN_TF_LEN
    d_tf = v7.analyze_timeframe_last(df, min_len)
    w_tf = v7.analyze_timeframe_last(weekly, min_len)
    m_tf = v7.analyze_timeframe_last(monthly, min_len)

    d_score = d_tf['mcdx_score'] if d_tf else None
    w_score = w_tf['mcdx_score'] if w_tf else None
    m_score = m_tf['mcdx_score'] if m_tf else None

    tier = classify_tier(w_score, m_score)
    resonance = bridge.compute_resonance_score(df)
    persist = bridge.compute_persistence(df)
    bflag = banker_flag(d_tf, w_tf, m_tf)

    # ---- 3. Sweet spot 判定 ----
    is_sweet = (resonance >= SWEET_RESONANCE_MIN and
                SWEET_RED_RATIO_LOW <= persist['red_ratio'] <= SWEET_RED_RATIO_HIGH)

    va.update({
        'symbol': symbol,
        'tier': tier,
        'd_score': d_score,
        'w_score': w_score,
        'm_score': m_score,
        'resonance': resonance,
        'red_ratio': persist['red_ratio'],
        'red_streak': persist['red_streak'],
        'sweet_spot': is_sweet,
        'banker_flag': bflag,
    })
    return va, None


# =====================================================
# 清单加载
# =====================================================
DEFAULT_WATCHLIST = ["5026.KL", "7103.KL", "8907.KL", "7115.KL", "5053.KL", "6262.KL"]


def load_watchlist(path):
    codes = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            code = line.split('#')[0].strip()
            if code:
                codes.append(code)
    return codes


# =====================================================
# 主程序
# =====================================================
def main():
    if len(sys.argv) > 1:
        list_path = sys.argv[1]
        watchlist = load_watchlist(list_path)
        label = list_path
    else:
        watchlist = DEFAULT_WATCHLIST
        label = "默认清单"

    print(f"\n扫描时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"清单：{label}   共 {len(watchlist)} 只")
    print(f"抓取周期：{FETCH_PERIOD}（MCDX月线需60根月K）")
    print("=" * 100)

    results = []
    for i, sym in enumerate(watchlist, 1):
        print(f"[{i}/{len(watchlist)}] {sym} ...", end=" ", flush=True)
        try:
            r, err = analyze_one(sym)
            if r is None:
                print(f"跳过（{err}）")
                continue
            if (r.get('close') is None or r.get('tier') is None
                    or r.get('resonance') is None or r.get('red_ratio') is None):
                print(f"跳过（数据不完整，close/tier/resonance/red_ratio缺失，"
                      f"可能是yfinance返回数据异常）")
                continue
            results.append(r)
            print(f"OK  价:{r['close']:>7.3f}  {r['tier']:<8} "
                  f"共振:{r['resonance']:>6.1f}  red:{r['red_ratio']:.2f}")
        except Exception as e:
            print(f"跳过（内部错误：{type(e).__name__}: {str(e)[:60]}）")
        finally:
            time.sleep(BASE_DELAY + random.uniform(0, 1.5))

    if not results:
        print("\n没有任何有效数据。")
        return

    # 板块相对强度基准
    valid_20d = [r['stock_20d%'] for r in results if r['stock_20d%'] is not None]
    sector_median = statistics.median(valid_20d) if valid_20d else None

    for r in results:
        r['vwap_score'], r['risks'] = score_vwap_ad(r, sector_median)

    print("\n" + "=" * 100)
    print(f"板块基准（20日涨幅中位数）：{round(sector_median, 2) if sector_median is not None else 'N/A'}%")
    print(f"有效 {len(results)}/{len(watchlist)} 只")

    # ---- Tier 分类表 ----
    print("\n" + "=" * 100)
    print("MCDX Tier 分类")
    print("=" * 100)
    print(f"{'代码':<11}{'Tier':<9}{'周分':>6}{'月分':>6}{'共振':>8}{'red_ratio':>11}{'streak':>8}{'SweetSpot':>11}  诊断")
    print("-" * 100)

    def _f(x):
        return f"{x:.0f}" if x is not None else "N/A"

    tier_order = {"Tier 1": 0, "Tier 1B": 1, "Tier 2": 2, "Tier 3": 3, "无数据": 4}
    for r in sorted(results, key=lambda x: (tier_order.get(x['tier'], 9), -x['resonance'])):
        print(f"{r['symbol']:<11}{r['tier']:<9}{_f(r['w_score']):>6}{_f(r['m_score']):>6}"
              f"{r['resonance']:>8.1f}{r['red_ratio']:>11.2f}{r['red_streak']:>8}"
              f"{'★ YES' if r['sweet_spot'] else '-':>11}  {r['banker_flag']}")

    # ---- Sweet spot 名单 ----
    sweets = [r for r in results if r['sweet_spot']]
    print("\n" + "=" * 100)
    print(f"完整 Sweet Spot（共振≥{SWEET_RESONANCE_MIN:.0f} 且 red_ratio {SWEET_RED_RATIO_LOW}-{SWEET_RED_RATIO_HIGH}）：{len(sweets)} 只")
    print("=" * 100)
    if sweets:
        for r in sorted(sweets, key=lambda x: -x['vwap_score']):
            print(f"  {r['symbol']:<11}价:{r['close']:>7.3f}  共振:{r['resonance']:>5.1f}  "
                  f"red:{r['red_ratio']:.2f}({r['red_streak']}月)  VWAP分:{r['vwap_score']:>6.2f}  "
                  f"[{r['banker_flag']}]")
    else:
        print("  本批无符合完整 sweet spot 的股票")

    # ---- 双强诊断提醒 ----
    both_strong = [r for r in results if r['banker_flag'] == '双强(庄家游资同强)' and r['red_ratio'] < 0.60]
    if both_strong:
        print("\n" + "=" * 100)
        print(f"⚠️ 双强诊断提醒：以下 {len(both_strong)} 只标记'双强'但 red_ratio<0.60")
        print("   可能是庄家/游资比大小的临界噪声拉低了 red_ratio，不代表真的没有庄家基础")
        print("=" * 100)
        for r in both_strong:
            print(f"  {r['symbol']:<11}red_ratio:{r['red_ratio']:.2f}  共振:{r['resonance']:>5.1f}  "
                  f"周分:{_f(r['w_score'])}  月分:{_f(r['m_score'])}")

    # ---- VWAP/AD 排名 ----
    print("\n" + "=" * 100)
    print("VWAP + A/D 综合评分 TOP 10")
    print("=" * 100)
    for i, r in enumerate(sorted(results, key=lambda x: -x['vwap_score'])[:10], 1):
        ad = f"周{'↑' if r['ad_w_up'] else '↓'}月{'↑' if r['ad_m_up'] else '↓'}"
        rel = r['rel_20d%'] if r['rel_20d%'] is not None else 'N/A'
        print(f"{i:2}. {r['symbol']:<11}价:{r['close']:>7.3f} 得分:{r['vwap_score']:>6.2f} "
              f"趋势:{r['base_trend']:>5.2f} 日:{r['dv_daily%']:>+5.1f}% 周:{r['dv_weekly%']:>+5.1f}% "
              f"月:{r['dv_monthly%']:>+5.1f}% A/D:{ad} 量比:{r['vol_ratio']:.2f} 相对:{rel}%")

    # ---- 风险标记 ----
    print("\n" + "=" * 100)
    print("风险 / 信号标记")
    print("=" * 100)
    flagged = [r for r in results if r['risks']]
    if flagged:
        for r in sorted(flagged, key=lambda x: -x['vwap_score']):
            print(f"  {r['symbol']:<11}得分:{r['vwap_score']:>6.2f}  {', '.join(r['risks'])}")
    else:
        print("  无")

    # ---- 存 CSV（带时间戳）----
    stamp = datetime.now().strftime('%Y%m%d_%H%M')
    out_name = f"unified_scan_{stamp}.csv"
    cols = ['symbol', 'close', 'tier', 'w_score', 'm_score', 'resonance',
            'red_ratio', 'red_streak', 'sweet_spot', 'banker_flag', 'vwap_score', 'base_trend',
            'dv_daily%', 'dv_weekly%', 'dv_monthly%', 'ad_w_up', 'ad_m_up',
            'vol_ratio', 'rel_20d%', 'turnover_20d']
    out_df = pd.DataFrame(results)
    out_df['scan_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    out_df['risks'] = out_df['risks'].apply(lambda x: '|'.join(x) if x else '')
    out_df[cols + ['risks', 'scan_time']].to_csv(out_name, index=False, encoding='utf-8-sig')
    print(f"\n已保存：{out_name}")


if __name__ == "__main__":
    main()