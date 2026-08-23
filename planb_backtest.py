"""
planb_backtest.py
======================================================================
Walk-forward 回测框架 —— 完整组合信号 (MCDX 共振 + 庄家持续性 双确认)

设计原则:
  1. 无前视偏差:每个历史日期 T,只用 <=T 的数据重算信号
  2. 连续信号去重:同一支股连续在信号态,只算一次进场 (cooldown)
  3. 超额收益:每笔信号对比同期基准 (KLCI),不然牛市里随便买都"赢"
  4. 样本量诚实:n < MIN_TRUSTWORTHY_N 时,结果不可信,明确标注

2026-08-19更新:两个placeholder函数(compute_resonance_score / compute_persistence)
之前是空的,只会 raise NotImplementedError,导致跑不出结果。
现已接上 all_klse_sweetspot_colab.py 里正在实盘运作、511信号回测验证过的真实MCDX计算逻辑
(V7 Pro Recovery参数:bankerLen=50/base=50/sens=1.4, hotLen=40/base=30/sens=0.65)。
同时补上了yfinance数据抓取的main(),可以直接对watchlist跑。

2026-08-19再更新(合并 planb_bridge.py + planb_run_backtest.py):
  - warmup_days 改为 1260(60*21,约5年)—— 采用 planb_run_backtest.py 里更严谨的算法:
    月线RSI(50)本身需要满60根月K才稳定,不是只看18个月持续性窗口那么简单,
    数据不够长的话,连月线庄家判断本身都还在暖机、不可信。原本用18*21+300(约678天)
    低估了需要的预热长度,已改正。
  - TICKERS 清单对齐 planb_run_backtest.py,新增 0326.KL
  - 不再需要额外 import v7pro_mcdx_scan.py / planb_bridge.py 这两层,
    三份文件的功能已经合并进这一份里

2026-08-19三度更新(依"PlanB回测与估值参数.md"文档核对):
  - persistence_red_ratio_th 补上上限0.85 —— 文档"一、已验证的规则"明确写着
    0.60-0.85(有上限)才是已验证可用的甜蜜点规则,之前CONFIG只写下限0.60,
    等于在测一个更宽、没被511信号验证过的假设信号,现已改正,让backtest真正
    复现文档表格里的63.6%胜率/3.43%中位超额结果。
  - period="max"(而非文档"六、锁定参数"写的"7y")是刻意为之,不是疏漏:
    "7y"那条锁定规则针对日常scan脚本(只需最后一天的分数,7年历史够撑60根月K预热);
    这份是walk-forward,要在很多年历史上逐日回测,天然需要更长历史撑住每一天的预热窗口,
    period="max"才能让回测窗口够长,这点跟原本 planb_run_backtest.py 的设计意图一致。
======================================================================
"""

import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import yfinance as yf
import datetime

# ----------------------------------------------------------------------
# 配置
# ----------------------------------------------------------------------
CONFIG = {
    "resonance_bull_th": 55,        # 偏多阈值
    "resonance_full_th": 80,        # 满阈值
    "persistence_red_ratio_th": 0.60,   # 甜蜜点下限:红色月占比 >= 60%
    "persistence_red_ratio_high": 0.85,  # 甜蜜点上限:红色月占比 <= 85%(2026-08-19据"PlanB回测与估值参数"文档补上——0.60-0.85才是已验证的甜蜜点规则,单独0.60+是未验证的更宽假设)
    "persistence_window_months": 18,     # 持续性回看窗口
    "warmup_days": 60 * 21,         # 预热:月线RSI(50)需满60根月K才稳定,约5年
    "hold_horizons": [5, 10, 20, 60],    # forward return 持有期(交易日)
    "cooldown_days": 20,            # 同股两次进场最小间隔,避免重复计数
    "min_trustworthy_n": 30,        # 低于此样本量,统计不可信
}

# MCDX 参数 —— 与 all_klse_sweetspot_colab.py 完全一致,不要单独改动
BANKER_PERIOD, BANKER_BASE, BANKER_SENS = 50, 50.0, 1.4
HOT_PERIOD, HOT_BASE, HOT_SENS = 40, 30.0, 0.65
STRONG_TH, MEDIUM_TH = 14.0, 7.0
_MIN_TF_LEN = max(BANKER_PERIOD, HOT_PERIOD) + 10  # 60


# ----------------------------------------------------------------------
# MCDX 核心计算 —— 从 all_klse_sweetspot_colab.py 移植,逻辑完全一致
# ----------------------------------------------------------------------
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


def calc_mcdx_series(close):
    idx = close.index
    rb = calc_rsi_wilder(close, BANKER_PERIOD).to_numpy()
    rh = calc_rsi_wilder(close, HOT_PERIOD).to_numpy()

    banker = np.clip(BANKER_SENS * (rb - BANKER_BASE), 0.0, 20.0)
    hot = np.clip(HOT_SENS * (rh - HOT_BASE), 0.0, 20.0)
    retail = np.clip(20.0 - np.maximum(banker, hot), 0.0, 20.0)

    dominant = np.full(len(idx), -1)
    is_bank = (banker >= MEDIUM_TH) & (banker >= hot) & (banker >= retail)
    is_hot = (~is_bank) & (hot >= MEDIUM_TH) & (hot >= banker) & (hot >= retail)
    is_ret = (~is_bank) & (~is_hot) & (retail >= MEDIUM_TH) & (retail >= banker) & (retail >= hot)
    dominant[is_bank] = 0
    dominant[is_hot] = 1
    dominant[is_ret] = 2

    dom_value = np.zeros(len(idx))
    dom_value[is_bank] = banker[is_bank]
    dom_value[is_hot] = hot[is_hot]
    dom_value[is_ret] = retail[is_ret]

    lvl_strong = dom_value >= STRONG_TH
    lvl_medium = (dom_value >= MEDIUM_TH) & (dom_value < STRONG_TH)

    mcdx_score = np.zeros(len(idx))
    m0 = dominant == 0
    mcdx_score[m0 & lvl_strong] = 100.0
    mcdx_score[m0 & lvl_medium] = 70.0
    mcdx_score[m0 & ~lvl_strong & ~lvl_medium] = 40.0
    m1 = dominant == 1
    mcdx_score[m1 & lvl_strong] = 85.0
    mcdx_score[m1 & lvl_medium] = 60.0
    mcdx_score[m1 & ~lvl_strong & ~lvl_medium] = 30.0
    m2 = dominant == 2
    mcdx_score[m2 & lvl_strong] = -90.0
    mcdx_score[m2 & lvl_medium] = -55.0
    mcdx_score[m2 & ~lvl_strong & ~lvl_medium] = -20.0

    return (pd.Series(dominant, index=idx), pd.Series(mcdx_score, index=idx))


def _analyze_timeframe_last(df, min_len):
    if len(df) < min_len:
        return None
    dom, score = calc_mcdx_series(df['Close'])
    val = score.iloc[-1]
    if pd.isna(val):
        return None
    return float(val)


# ----------------------------------------------------------------------
# ↓↓↓ 之前是 placeholder,现在接上真实计算 ↓↓↓
# window 是截至当前日T的OHLCV(不可含T之后的数据,由 backtest_stock 保证)
# ----------------------------------------------------------------------
def compute_resonance_score(window: pd.DataFrame) -> float:
    """日/周/月三线共振分数,取三者最小值(短板决定强度)。
    与 all_klse_sweetspot_colab.py 的 compute_resonance_score 逻辑完全一致。"""
    if len(window) < _MIN_TF_LEN:
        return -999.0
    weekly = resample_ohlcv(window, 'W')
    monthly = resample_ohlcv(window, 'ME')

    d = _analyze_timeframe_last(window, _MIN_TF_LEN)
    w = _analyze_timeframe_last(weekly, _MIN_TF_LEN)
    m = _analyze_timeframe_last(monthly, _MIN_TF_LEN)

    vals = [v for v in (d, w, m) if v is not None]
    if len(vals) < 3:
        return -999.0
    return float(min(vals))


def compute_persistence(window: pd.DataFrame, months: int = CONFIG["persistence_window_months"]) -> dict:
    """月线庄家(红色)主导占比 + 连续红月数。
    与 all_klse_sweetspot_colab.py 的 compute_persistence 逻辑完全一致,
    只是把返回值包成 dict,配合 backtest_stock 里 pers["red_ratio"] 的写法。"""
    monthly = resample_ohlcv(window, 'ME')
    if len(monthly) < _MIN_TF_LEN:
        return {"red_ratio": 0.0, "red_streak": 0}

    dom, _ = calc_mcdx_series(monthly['Close'])
    dom_valid = dom[dom != -1]
    if len(dom_valid) == 0:
        return {"red_ratio": 0.0, "red_streak": 0}

    recent = dom_valid.tail(months)
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

    return {"red_ratio": red_ratio, "red_streak": streak}
# ----------------------------------------------------------------------
# ↑↑↑ 之前是 placeholder,现在接上真实计算 ↑↑↑
# ----------------------------------------------------------------------


def backtest_stock(ticker: str,
                   prices: pd.DataFrame,
                   benchmark: pd.Series,
                   cfg: dict = CONFIG,
                   verbose: bool = True) -> pd.DataFrame:
    """对单支股做 walk-forward 回测,返回每笔信号的 forward return DataFrame。"""
    closes = prices["Close"]
    dates = prices.index
    horizons = cfg["hold_horizons"]
    max_h = max(horizons)

    start = cfg["warmup_days"]
    end = len(dates) - max_h          # 留出最长持有期,否则算不到 forward return
    if end <= start:
        return pd.DataFrame()          # 数据不够,跳过

    rows = []
    last_entry_i = -10**9              # 上次进场的 index,用于 cooldown
    total_iters = end - start
    t0 = datetime.datetime.now()

    for k, i in enumerate(range(start, end)):
        # --- 关键:只用 <=T 的数据,杜绝前视偏差 ---
        window = prices.iloc[: i + 1]

        res = compute_resonance_score(window)
        pers = compute_persistence(window)

        resonance_ok = res >= cfg["resonance_bull_th"]
        persistence_ok = cfg["persistence_red_ratio_th"] <= pers["red_ratio"] <= cfg["persistence_red_ratio_high"]

        if not (resonance_ok and persistence_ok):
            pass
        elif i - last_entry_i < cfg["cooldown_days"]:
            pass                   # 还在冷却期,不算新进场
        else:
            last_entry_i = i

            entry_price = closes.iloc[i]
            entry_date = dates[i]
            row = {
                "ticker": ticker,
                "date": entry_date,
                "resonance": round(res, 1),
                "red_ratio": round(pers["red_ratio"], 3),
            }
            # 每个持有期的股票收益 + 基准同期收益 + 超额
            bench_entry = benchmark.asof(entry_date)
            for h in horizons:
                exit_date = dates[i + h]
                stock_ret = closes.iloc[i + h] / entry_price - 1
                bench_exit = benchmark.asof(exit_date)
                bench_ret = (bench_exit / bench_entry - 1) if bench_entry else np.nan
                row[f"ret_{h}d"] = stock_ret
                row[f"exc_{h}d"] = stock_ret - bench_ret     # 超额收益
            rows.append(row)

        # 进度提示:每200次循环,或最后一次,印一次
        if verbose and ((k + 1) % 200 == 0 or k == total_iters - 1):
            elapsed = (datetime.datetime.now() - t0).total_seconds()
            avg = elapsed / (k + 1)
            remaining = avg * (total_iters - k - 1)
            print(f"    [{ticker}] 循环 {k+1}/{total_iters}  "
                  f"已用时{elapsed:.0f}秒  预计还需{remaining:.0f}秒  "
                  f"目前信号数{len(rows)}")

    return pd.DataFrame(rows)


def summarize(all_signals: pd.DataFrame, cfg: dict = CONFIG) -> pd.DataFrame:
    """汇总:每个持有期的胜率、平均收益、平均超额、中位数。"""
    n = len(all_signals)
    print(f"\n总信号数 n = {n}")
    if n < cfg["min_trustworthy_n"]:
        print(f"⚠️  n < {cfg['min_trustworthy_n']} —— 样本太少,以下数字不可信,只能当参考")

    out = []
    for h in cfg["hold_horizons"]:
        r = all_signals[f"ret_{h}d"]
        e = all_signals[f"exc_{h}d"]
        out.append({
            "持有期": f"{h}d",
            "胜率(绝对)": f"{(r > 0).mean():.1%}",
            "胜率(超额)": f"{(e > 0).mean():.1%}",   # 关键:是否跑赢基准
            "平均收益": f"{r.mean():.2%}",
            "中位收益": f"{r.median():.2%}",
            "平均超额": f"{e.mean():.2%}",
        })
    return pd.DataFrame(out)


def run(price_dict: dict, benchmark: pd.Series, cfg: dict = CONFIG) -> pd.DataFrame:
    """price_dict: {ticker: OHLCV DataFrame}。benchmark: KLCI 收盘 Series。"""
    frames = []
    n_tickers = len(price_dict)
    max_h = max(cfg["hold_horizons"])
    # 先估算总循环量,让你心里有数,不用瞎等
    total_est_iters = sum(max(0, len(p) - cfg["warmup_days"] - max_h) for p in price_dict.values())
    print(f"股票数: {n_tickers}  |  预估总循环次数: {total_est_iters:,}  "
          f"(每支股票内部每200次循环会印一次进度)")
    run_start = datetime.datetime.now()

    for idx, (ticker, prices) in enumerate(price_dict.items()):
        elapsed = (datetime.datetime.now() - run_start).total_seconds()
        print(f"\n[{idx+1}/{n_tickers}] 开始回测 {ticker} ({len(prices)}天历史)  "
              f"|  总耗时已{elapsed/60:.1f}分钟")
        try:
            frames.append(backtest_stock(ticker, prices, benchmark, cfg))
        except NotImplementedError:
            raise
        except Exception as ex:
            print(f"跳过 {ticker}: {ex}")
    all_sig = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not all_sig.empty:
        print(summarize(all_sig, cfg).to_string(index=False))
    return all_sig


# ----------------------------------------------------------------------
# 数据抓取 + 主流程(新增) —— 用yfinance拉最长历史(period="max"),
# 保证 warmup_days(约658个交易日,约2.6年)有足够数据可用
# ----------------------------------------------------------------------
def clean(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=['Close'])


def main():
    # 20支watchlist —— 对齐 planb_run_backtest.py,已拿掉 0326.KL(Sorento Capital,
    # 2024/10上市不到2年,历史不够撑5年预热窗口,留着也只会被自动跳过,不如先拿掉省时间)
    TICKERS = ['7233.KL', '5211.KL', '8907.KL', '6459.KL', '5249.KL', '5026.KL',
               '5286.KL', '0225.KL', '0099.KL', '5031.KL', '5681.KL', '7163.KL',
               '8869.KL', '1066.KL', '0215.KL', '7103.KL', '5263.KL',
               '4863.KL', '5243.KL', '5142.KL']

    # KLCI 基准 —— Yahoo Finance代号,如果抓不到数据请回报,可能需要换成别的代号核对
    BENCHMARK_TICKER = "^KLSE"

    print("下载基准指数...")
    bench_df = clean(yf.download(BENCHMARK_TICKER, period="max", auto_adjust=True, progress=False))
    if bench_df.empty:
        print(f"⚠️ 基准指数 {BENCHMARK_TICKER} 抓不到数据,回测无法算超额收益,请检查代号")
        return
    benchmark = bench_df["Close"]

    price_dict = {}
    print(f"下载 {len(TICKERS)} 支股票历史数据(period=max)...")
    for i, tk in enumerate(TICKERS):
        try:
            df = clean(yf.download(tk, period="max", auto_adjust=True, progress=False))
            if len(df) < CONFIG["warmup_days"] + max(CONFIG["hold_horizons"]) + 50:
                print(f"  {tk:<10} 数据不足({len(df)}天),跳过")
                continue
            price_dict[tk] = df
            print(f"  {tk:<10} OK ({len(df)}天)")
        except Exception as e:
            print(f"  {tk:<10} 抓取失败: {str(e)[:50]}")

    if not price_dict:
        print("没有任何股票有足够数据,回测终止")
        return

    print(f"\n开始回测 {len(price_dict)} 支股票...")
    all_signals = run(price_dict, benchmark, CONFIG)

    if not all_signals.empty:
        fname = f"planb_backtest_signals_{datetime.datetime.now().strftime('%Y%m%d')}.csv"
        all_signals.to_csv(fname, index=False, encoding='utf-8-sig')
        print(f"\n📝 已存档: {fname}")
    else:
        print("\n没有产生任何信号(可能是阈值太严或数据窗口不够)")


if __name__ == "__main__":
    main()
