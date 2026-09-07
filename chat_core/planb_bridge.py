# -*- coding: utf-8 -*-
"""
planb_bridge.py — 让 Plan B 各脚本共用同一套 V7 Pro 指标逻辑
用法: from planb_bridge import compute_resonance_score, compute_persistence

2026-09-01 变更：compute_persistence 新增 exclude_incomplete 参数
--------------------------------------------------------------
问题：v7.resample_ohlcv 不排除未走完的周期。9月1日跑扫描时，「9月」
会被聚成一根只含一个交易日的月线柱，占掉 tail(18) 的一格，使 red_ratio
产生 ±1/18 (≈0.056) 的月内漂移。实测 2026-09-01：
    7161 KERJAYA  含9月柱 0.389 → 只到8月底 0.333
    8907 EG       含9月柱 0.667 → 只到8月底 0.611
    5263 SUNCON   含9月柱 0.778 → 只到8月底 0.722
    5053 OSK      两者皆 0.833（当月柱未翻红，不受影响）
这足以让 0.85 边缘的股票在甜蜜点与满仓警惕之间跳动。

处理方式：预设 exclude_incomplete=False，保持与既有回测结果向后相容
（511信号回测、sweet-spot 63.6%胜率那批数字都是旧口径算的）。
新脚本可显式传 True 取得干净口径。若将来要全面切换，必须重跑全部回测，
且新旧数字不可直接比较。

已知取舍：判定「未走完」是拿柱子的周期结束日跟 as_of（预设今天）比。
在月底最后一个交易日当天跑，该月柱也会被排除 —— 偏保守，但每天口径一致。
"""
import pandas as pd

import v7pro_mcdx_scan as v7

PERSIST_WINDOW_MONTHS = 18
_MIN_TF_LEN = max(v7.BANKER_PERIOD, v7.HOT_PERIOD) + 10


def _min_or_neg(*scores):
    vals = [s for s in scores if s is not None]
    if len(vals) < 3:
        return -999.0
    return float(min(vals))


def drop_incomplete_period(resampled, as_of=None):
    """去掉最后一根还没走完的周期柱。

    resampled 的 index 是周期的结束日（'ME' → 月底，'W' → 周日）。
    若该日期 >= as_of，代表这根柱子还在累积中，排除。
    """
    if resampled is None or len(resampled) == 0:
        return resampled
    as_of = pd.Timestamp(as_of) if as_of is not None else pd.Timestamp.today().normalize()
    last_edge = pd.Timestamp(resampled.index[-1]).normalize()
    if last_edge >= as_of:
        return resampled.iloc[:-1]
    return resampled


def compute_resonance_score(window):
    if window is None or len(window) < _MIN_TF_LEN:
        return -999.0
    d_tf = v7.analyze_timeframe_last(window, _MIN_TF_LEN)
    w_tf = v7.analyze_timeframe_last(v7.resample_ohlcv(window, 'W'), _MIN_TF_LEN)
    m_tf = v7.analyze_timeframe_last(v7.resample_ohlcv(window, 'ME'), _MIN_TF_LEN)
    d = d_tf['mcdx_score'] if d_tf else None
    w = w_tf['mcdx_score'] if w_tf else None
    m = m_tf['mcdx_score'] if m_tf else None
    return _min_or_neg(d, w, m)


def compute_persistence(window, months=PERSIST_WINDOW_MONTHS, freq='ME',
                        exclude_incomplete=False, as_of=None):
    if window is None or len(window) < _MIN_TF_LEN:
        return {"red_ratio": 0.0, "red_streak": 0}
    resampled = v7.resample_ohlcv(window, freq)
    if exclude_incomplete:
        resampled = drop_incomplete_period(resampled, as_of)
    if len(resampled) < _MIN_TF_LEN:
        # 根数不足(<60根),RSI(50)算不出来,不能拿0.0冒充"无庄家"
        return {"red_ratio": None, "red_streak": 0}
    _, _, _, dom_series, _ = v7.calc_mcdx_series(resampled['Close'])
    dom_series = dom_series[dom_series != -1]
    recent = dom_series.tail(months)
    if len(recent) == 0:
        return {"red_ratio": 0.0, "red_streak": 0}
    is_red = (recent == 0)
    red_ratio = float(is_red.mean())
    streak = 0
    for v in reversed(is_red.tolist()):
        if v:
            streak += 1
        else:
            break
    return {"red_ratio": red_ratio, "red_streak": int(streak)}
