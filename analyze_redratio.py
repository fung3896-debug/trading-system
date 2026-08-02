# -*- coding: utf-8 -*-
"""按 red_ratio 分组,验证'中等红色占比反而比满格更好'的假设"""
import pandas as pd

df = pd.read_csv('planb_backtest_signals.csv')

df['red_bucket'] = pd.cut(df['red_ratio'],
    bins=[0.59, 0.70, 0.85, 0.99, 1.001],
    labels=['0.60-0.70 (庄家刚建仓)',
            '0.70-0.85 (建仓中)',
            '0.85-0.99 (接近满仓)',
            '1.00 (满仓/可能出货期)'])

print("="*80)
print("按 red_ratio(庄家红色持续占比)分组 —— 全部 511 个信号")
print("="*80)

for horizon in ['exc_20d', 'exc_60d']:
    print(f"\n【{horizon}(超额收益)】")
    g = df.groupby('red_bucket', observed=True).agg(
        信号数=('red_bucket', 'size'),
        胜率=(horizon, lambda x: (x > 0).mean()),
        平均超额=(horizon, 'mean'),
        中位超额=(horizon, 'median')
    )
    g['胜率'] = (g['胜率'] * 100).round(1).astype(str) + '%'
    g['平均超额'] = (g['平均超额'] * 100).round(2).astype(str) + '%'
    g['中位超额'] = (g['中位超额'] * 100).round(2).astype(str) + '%'
    print(g.to_string())

print("\n" + "="*80)
print("解读")
print("="*80)
print("如果 0.60-0.70 组的中位超额明显高于 1.00 组,")
print("就证明:红色占比'适中'比'满格'更好。")
