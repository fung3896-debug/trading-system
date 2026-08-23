# -*- coding: utf-8 -*-
"""
crsi_stress_test.py

对"周线CRSI连续2周≥80 + 月线双确认"信号做三项压力测试：
    1. 分年份稳健性 —— 是不是靠某几年牛市撑起来的
    2. 最差单笔表现 —— 不是完整的最大回撤(没有逐日净值曲线数据)，
       是"信号触发后N周持有期结束时"的最差结果分布，作为风险的近似衡量
    3. 与 sweet spot 的重叠度 —— 两套信号是不是经常在同一支股票、
       同一时间点一起触发（测的可能是同一个底层现象）

全部基于已保存的本地CSV，不需要重新拉价格数据，跑得很快：
    - crsi_momentum_signals.csv (上一步跑出来的CRSI信号)
    - planb_backtest_signals.csv (511-signal sweet spot 回测数据)

运行方式:
    cd ~/Documents/PlanB_Scanner
    python3 crsi_stress_test.py
"""

import pandas as pd
import numpy as np

CRSI_CSV = "crsi_momentum_signals.csv"
SWEETSPOT_CSV = "planb_backtest_signals.csv"
OVERLAP_WINDOW_DAYS = 10  # 判定"同期"的容差窗口


def stress_test_1_by_year(df: pd.DataFrame):
    print("=" * 78)
    print("【压力测试1】分年份稳健性 —— B组(双确认)信号")
    print("=" * 78)
    b = df[df['monthly_confirmed']].copy()
    b['year'] = pd.to_datetime(b['signal_date']).dt.year

    yearly = b.groupby('year').agg(
        信号数=('exc_12w', 'count'),
        胜率=('ret_12w', lambda x: (x > 0).mean()),
        平均超额12周=('exc_12w', 'mean'),
    ).round(3)
    print(yearly.to_string())

    n_years = yearly.shape[0]
    n_positive_years = (yearly['平均超额12周'] > 0).sum()
    print(f"\n共 {n_years} 个年份有信号，其中 {n_positive_years} 年平均超额收益为正"
          f" ({n_positive_years/n_years:.0%})")

    # 找出贡献最大的年份，看剔除后结果是否还站得住
    yearly_sorted = yearly.sort_values('信号数', ascending=False)
    top_year = yearly_sorted.index[0]
    top_year_share = yearly_sorted.iloc[0]['信号数'] / b.shape[0]
    print(f"\n信号数最多的年份: {top_year} (占比 {top_year_share:.1%})")
    b_excl = b[b['year'] != top_year]
    if len(b_excl) > 0:
        win_excl = (b_excl['ret_12w'] > 0).mean()
        exc_excl = b_excl['exc_12w'].mean()
        print(f"剔除该年份后: n={len(b_excl)}  胜率={win_excl:.1%}  平均超额12周={exc_excl:.2%}")
        if win_excl > 0.55 and exc_excl > 0:
            print("  → 剔除信号最多的年份后依然站得住，不是单一年份撑起来的")
        else:
            print("  ⚠️ 剔除该年份后明显变差，需要留意是不是被这一年主导")


def stress_test_2_worst_case(df: pd.DataFrame):
    print("\n" + "=" * 78)
    print("【压力测试2】最差单笔表现分布 —— B组(双确认)信号")
    print("=" * 78)
    print("⚠️ 注意：这不是完整的最大回撤(没有逐日净值路径数据)，是持有期")
    print("   结束时点的收益分布，用来近似衡量'最坏情况能有多坏'")

    b = df[df['monthly_confirmed']].copy()
    for wk in [4, 8, 12]:
        col_ret = f'ret_{wk}w'
        col_exc = f'exc_{wk}w'
        worst5 = b.nsmallest(5, col_ret)[['ticker', 'signal_date', col_ret, col_exc]]
        pct_big_loss = (b[col_ret] < -0.20).mean()
        pct_big_loss_excess = (b[col_exc] < -0.20).mean()
        print(f"\n-- 持有{wk}周 --")
        print(f"  最差5笔:")
        print(worst5.to_string(index=False))
        print(f"  单笔亏损超过20%的比例: {pct_big_loss:.1%}")
        print(f"  跑输大盘超过20%的比例: {pct_big_loss_excess:.1%}")


def stress_test_3_overlap_with_sweetspot(crsi_df: pd.DataFrame):
    print("\n" + "=" * 78)
    print("【压力测试3】与 sweet spot(MCDX)信号的重叠度")
    print("=" * 78)
    try:
        ss = pd.read_csv(SWEETSPOT_CSV)
        ss['date'] = pd.to_datetime(ss['date'])
    except FileNotFoundError:
        print(f"  找不到 {SWEETSPOT_CSV}，跳过这项测试")
        return

    b = crsi_df[crsi_df['monthly_confirmed']].copy()
    b['signal_date'] = pd.to_datetime(b['signal_date'])

    common_tickers = set(b['ticker'].unique()) & set(ss['ticker'].unique())
    print(f"CRSI双确认信号涉及股票数: {b['ticker'].nunique()}")
    print(f"sweet spot信号涉及股票数: {ss['ticker'].nunique()}")
    print(f"两者共同覆盖的股票数: {len(common_tickers)}")

    if not common_tickers:
        print("  没有共同股票，两套信号完全独立，测的是不同的股票池，无法直接比重叠")
        return

    b_common = b[b['ticker'].isin(common_tickers)]
    ss_common = ss[ss['ticker'].isin(common_tickers)]
    print(f"  CRSI在共同股票上的信号数: {len(b_common)}")
    print(f"  sweet spot在共同股票上的信号数: {len(ss_common)}")

    overlap_count = 0
    for _, row in b_common.iterrows():
        same_ticker = ss_common[ss_common['ticker'] == row['ticker']]
        if len(same_ticker) == 0:
            continue
        diffs = (same_ticker['date'] - row['signal_date']).abs()
        if (diffs <= pd.Timedelta(days=OVERLAP_WINDOW_DAYS)).any():
            overlap_count += 1

    if len(b_common) > 0:
        overlap_rate = overlap_count / len(b_common)
        print(f"\n  CRSI双确认信号中，±{OVERLAP_WINDOW_DAYS}天内也有sweet spot信号的比例: {overlap_rate:.1%}")
        if overlap_rate > 0.5:
            print("  → 重叠度较高，两套信号可能在捕捉同一个底层现象(强势股)，")
            print("    考虑把CRSI当作sweet spot的确认层，而不是完全独立的信号源")
        else:
            print("  → 重叠度不高，两套信号相对独立，可能捕捉的是不同类型的机会，")
            print("    值得当作独立信号源保留")
    else:
        print("  共同股票上没有足够的CRSI信号做比较")


def main():
    df = pd.read_csv(CRSI_CSV)
    stress_test_1_by_year(df)
    stress_test_2_worst_case(df)
    stress_test_3_overlap_with_sweetspot(df)


if __name__ == "__main__":
    main()

