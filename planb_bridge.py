import pandas as pd
import v7pro_mcdx_scan as v7

PERSIST_WINDOW_MONTHS = 18
_MIN_TF_LEN = max(v7.BANKER_PERIOD, v7.HOT_PERIOD) + 10


def _min_or_neg(*scores):
    vals = [s for s in scores if s is not None]
    if len(vals) < 3:
        return -999.0
    return float(min(vals))


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


def compute_persistence(window, months=PERSIST_WINDOW_MONTHS):
    if window is None or len(window) < _MIN_TF_LEN:
        return {"red_ratio": 0.0, "red_streak": 0}
    monthly = v7.resample_ohlcv(window, 'ME')
    if len(monthly) < _MIN_TF_LEN:
        # 月线根数不足(<60根=5年),RSI(50)算不出来,不能拿0.0冒充"无庄家"
        return {"red_ratio": None, "red_streak": 0}
    _, _, _, dom_series, _ = v7.calc_mcdx_series(monthly['Close'])
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
