import numpy as np
import pandas as pd

CONFIG = {
    "resonance_bull_th": 55,
    "resonance_full_th": 80,
    "persistence_red_ratio_th": 0.60,
    "persistence_window_months": 18,
    "warmup_days": 18 * 21 + 300,
    "hold_horizons": [5, 10, 20, 60],
    "cooldown_days": 20,
    "min_trustworthy_n": 30,
}


def compute_resonance_score(window):
    raise NotImplementedError("接上你的 MCDX 共振函数")


def compute_persistence(window):
    raise NotImplementedError("接上你的庄家持续性函数")


def backtest_stock(ticker, prices, benchmark, cfg=CONFIG):
    closes = prices["Close"]
    dates = prices.index
    horizons = cfg["hold_horizons"]
    max_h = max(horizons)
    start = cfg["warmup_days"]
    end = len(dates) - max_h
    if end <= start:
        return pd.DataFrame()
    rows = []
    last_entry_i = -10**9
    for i in range(start, end):
        window = prices.iloc[: i + 1]
        res = compute_resonance_score(window)
        pers = compute_persistence(window)
        if not (res >= cfg["resonance_bull_th"] and pers["red_ratio"] >= cfg["persistence_red_ratio_th"]):
            continue
        if i - last_entry_i < cfg["cooldown_days"]:
            continue
        last_entry_i = i
        entry_price = closes.iloc[i]
        entry_date = dates[i]
        row = {"ticker": ticker, "date": entry_date,
               "resonance": round(res, 1), "red_ratio": round(pers["red_ratio"], 3)}
        bench_entry = benchmark.asof(entry_date)
        for h in horizons:
            exit_date = dates[i + h]
            stock_ret = closes.iloc[i + h] / entry_price - 1
            bench_exit = benchmark.asof(exit_date)
            bench_ret = (bench_exit / bench_entry - 1) if bench_entry else np.nan
            row[f"ret_{h}d"] = stock_ret
            row[f"exc_{h}d"] = stock_ret - bench_ret
        rows.append(row)
    return pd.DataFrame(rows)


def summarize(all_signals, cfg=CONFIG):
    n = len(all_signals)
    print(f"\n总信号数 n = {n}")
    if n < cfg["min_trustworthy_n"]:
        print(f"警告 n < {cfg['min_trustworthy_n']} —— 样本太少,以下数字不可信,只能当参考")
    out = []
    for h in cfg["hold_horizons"]:
        r = all_signals[f"ret_{h}d"]
        e = all_signals[f"exc_{h}d"]
        out.append({"持有期": f"{h}d",
                    "胜率绝对": f"{(r > 0).mean():.1%}",
                    "胜率超额": f"{(e > 0).mean():.1%}",
                    "平均收益": f"{r.mean():.2%}",
                    "中位收益": f"{r.median():.2%}",
                    "平均超额": f"{e.mean():.2%}"})
    return pd.DataFrame(out)


def run(price_dict, benchmark, cfg=CONFIG):
    frames = []
    for ticker, prices in price_dict.items():
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


if __name__ == "__main__":
    print("planb_backtest 框架已载入")
