#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
planb_run_backtest.py
======================================================================
一键回测:下载真实数据 → 接线 → 跑 walk-forward → 存 CSV。
放在 PlanB_Scanner/ 文件夹里,和 planb_backtest.py / planb_bridge.py /
v7pro_mcdx_scan.py 同一层。然后在 IDLE 或终端跑这个文件即可。

⚠️ 关键约束(务必读):
  月线 RSI(50) 需要 60 根月 K 才能算 → 需要约 5 年数据"预热"。
  所以下载 period 要尽量长(建议 "max"),否则回测窗口所剩无几。
  即便如此,双确认信号稀疏 + 窗口短 → 样本很可能只有个位到几十。
  这时别信胜率数字,请逐笔拉出来看图人工判断(脚本会存每笔明细)。
======================================================================
"""

import warnings
warnings.filterwarnings('ignore')

import yfinance as yf
import pandas as pd

import planb_backtest as bt
import planb_bridge as br

# ---- 接线:把桥接函数装进回测框架的两个 placeholder ----
bt.compute_resonance_score = br.compute_resonance_score
bt.compute_persistence = br.compute_persistence

# ---- 参数 ----
bt.CONFIG['warmup_days'] = 60 * 21          # 月线满 60 根(约5年)才开机
DOWNLOAD_PERIOD = "max"                       # 尽量长,换更长回测窗口
BENCHMARK_TICKER = "^KLSE"                    # 富时大马 KLCI

# 你要回测的股票(先用你 watchlist 里的 KLSE,想加就加)
TICKERS = ['7233.KL', '5211.KL', '8907.KL', '6459.KL', '5249.KL', '5026.KL',
           '5286.KL', '0225.KL', '0099.KL', '5031.KL', '5681.KL', '7163.KL',
           '8869.KL', '1066.KL', '0215.KL', '0326.KL', '7103.KL', '5263.KL',
           '4863.KL', '5243.KL', '5142.KL']


def download_clean(ticker: str, period: str = DOWNLOAD_PERIOD) -> pd.DataFrame:
    """下载 + 清洗(和你原文件同款:摊平 MultiIndex、丢幽灵行)。"""
    df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=['Close'])
    return df


def main():
    print("下载基准 (KLCI) ...")
    bench_df = download_clean(BENCHMARK_TICKER)
    if bench_df.empty:
        print("❌ 基准下载失败,换个 ticker 或检查网络"); return
    benchmark = bench_df['Close']

    print(f"下载 {len(TICKERS)} 支股票 (period={DOWNLOAD_PERIOD}) ...")
    price_dict = {}
    for tk in TICKERS:
        d = download_clean(tk)
        if len(d) >= bt.CONFIG['warmup_days'] + 60:
            price_dict[tk] = d
            print(f"  ✅ {tk:<10} {len(d)} 行 (约 {len(d)//252} 年)")
        else:
            print(f"  ⏭  {tk:<10} 数据不足({len(d)} 行),跳过 —— 5年预热都不够")

    if not price_dict:
        print("❌ 没有股票有足够历史,无法回测"); return

    print("\n开始 walk-forward 回测(会比较慢,每支约1-2分钟)...\n")
    signals = bt.run(price_dict, benchmark)

    if signals is not None and not signals.empty:
        out = "planb_backtest_signals.csv"
        signals.to_csv(out, index=False, encoding='utf-8-sig')
        print(f"\n💾 每笔信号明细已存 → {out}")
        print("   下一步:打开 CSV,把每笔 date+ticker 拉到 TradingView 看图人工验证。")
    else:
        print("\n没有任何信号触发 —— 双确认太严,或历史窗口太短。")


if __name__ == "__main__":
    main()
