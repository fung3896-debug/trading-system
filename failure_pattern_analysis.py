# -*- coding: utf-8 -*-
"""
failure_pattern_analysis.py

不是新假设，是对已验证有效的 sweet spot 信号（511-signal回测）做归纳分析：
表现最好的一批和表现最差的一批，触发时在已有字段上有没有肉眼可见的共同差异。

完全基于已有数据（planb_backtest_signals.csv）和已有字段，不引入任何新指标、
不需要重新拉价格数据，跑起来很快。

运行方式:
    cd ~/Documents/PlanB_Scanner
    python3 failure_pattern_analysis.py
"""

import pandas as pd
import numpy as np

SIGNALS_CSV = "planb_backtest_signals.csv"
TOP_BOTTOM_PCT = 0.20  # 各取表现最好/最差的20%


def run_analysis():
    df = pd.read_csv(SIGNALS_CSV)
    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.month
    df['year'] = df['date'].dt.year

    n = len(df)
    df_sorted = df.sort_values('exc_60d')
    cut = int(n * TOP_BOTTOM_PCT)

    worst = df_sorted.iloc[:cut].copy()
    best = df_sorted.iloc[-cut:].copy()

    print("=" * 70)
    print(f"总信号数: {n}  |  各取表现最差/最好各 {cut} 个 (前后{TOP_BOTTOM_PCT:.0%})")
    print("=" * 70)
    print(f"最差组 exc_60d 范围: {worst['exc_60d'].min():.1%} ~ {worst['exc_60d'].max():.1%}")
    print(f"最好组 exc_60d 范围: {best['exc_60d'].min():.1%} ~ {best['exc_60d'].max():.1%}")

    # ---- 1. red_ratio 分布对比 ----
    print("\n【1】red_ratio (庄家持续性) 对比")
    print(f"  最差组: 均值={worst['red_ratio'].mean():.3f}, 中位数={worst['red_ratio'].median():.3f}")
    print(f"  最好组: 均值={best['red_ratio'].mean():.3f}, 中位数={best['red_ratio'].median():.3f}")

    # ---- 2. resonance 分布对比 ----
    print("\n【2】resonance (共振强度) 对比")
    print(f"  最差组: 均值={worst['resonance'].mean():.1f}, 中位数={worst['resonance'].median():.1f}")
    print(f"  最好组: 均值={best['resonance'].mean():.1f}, 中位数={best['resonance'].median():.1f}")

    # ---- 3. 触发月份分布（是否有季节性）----
    print("\n【3】触发月份分布 (是否有季节性集中)")
    worst_month = worst['month'].value_counts(normalize=True).sort_index()
    best_month = best['month'].value_counts(normalize=True).sort_index()
    month_cmp = pd.DataFrame({'最差组占比': worst_month, '最好组占比': best_month}).fillna(0)
    print(month_cmp.applymap(lambda x: f"{x:.1%}").to_string())

    # ---- 4. 触发年份分布（是否集中在特定市场环境/危机年份）----
    print("\n【4】触发年份分布 (是否集中在特定市场环境)")
    worst_year = worst['year'].value_counts().sort_index()
    best_year = best['year'].value_counts().sort_index()
    year_cmp = pd.DataFrame({'最差组次数': worst_year, '最好组次数': best_year}).fillna(0).astype(int)
    print(year_cmp.to_string())

    # ---- 5. 股票集中度（是否是特定几只股票反复表现差/好）----
    print("\n【5】股票集中度")
    print("  最差组 前5只出现次数最多的股票:")
    print("  " + worst['ticker'].value_counts().head(5).to_string().replace("\n", "\n  "))
    print("  最好组 前5只出现次数最多的股票:")
    print("  " + best['ticker'].value_counts().head(5).to_string().replace("\n", "\n  "))

    # ---- 6. 短周期收益方向（信号触发后短期是否已经能看出苗头）----
    print("\n【6】短周期收益方向 (信号触发后5/10/20日超额收益，能否提前看出苗头)")
    for col in ['exc_5d', 'exc_10d', 'exc_20d']:
        print(f"  {col}: 最差组均值={worst[col].mean():.2%}  最好组均值={best[col].mean():.2%}")

    # ---- 7. 最差组里，有多少一开始(5天)就已经是负的 ----
    early_negative_in_worst = (worst['exc_5d'] < 0).mean()
    early_negative_in_best = (best['exc_5d'] < 0).mean()
    print(f"\n【7】触发后5天就已经跑输大盘的比例")
    print(f"  最差组: {early_negative_in_worst:.1%}")
    print(f"  最好组: {early_negative_in_best:.1%}")
    if early_negative_in_worst > early_negative_in_best + 0.15:
        print("  → 最差组明显更早就显露颓势，也许可以用'5日超额收益转负'做提前止损/减仓过滤")

    worst.to_csv("failure_pattern_worst_20pct.csv", index=False)
    best.to_csv("failure_pattern_best_20pct.csv", index=False)
    print("\n已保存: failure_pattern_worst_20pct.csv / failure_pattern_best_20pct.csv")


if __name__ == "__main__":
    run_analysis()
