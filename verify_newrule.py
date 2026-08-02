# -*- coding: utf-8 -*-
"""最终验证:比较'旧规则(≥0.60全收)' vs '新规则(0.60-0.85甜蜜点)'"""
import pandas as pd

df = pd.read_csv('planb_backtest_signals.csv')

old = df                                          # 旧规则:全部
new = df[(df['red_ratio'] >= 0.60) & (df['red_ratio'] <= 0.85)]  # 新规则

def stats(d, name):
    print(f"\n【{name}】 信号数 = {len(d)}")
    print(f"{'持有期':<8}{'胜率':<10}{'平均超额':<12}{'中位超额':<12}")
    for h in ['exc_20d', 'exc_60d']:
        win = (d[h] > 0).mean() * 100
        avg = d[h].mean() * 100
        med = d[h].median() * 100
        print(f"{h:<8}{win:>5.1f}%    {avg:>6.2f}%      {med:>6.2f}%")

print("="*70)
print("旧规则 vs 新规则对照")
print("="*70)
stats(old, "旧规则:red_ratio >= 0.60(全收)")
stats(new, "新规则:0.60 <= red_ratio <= 0.85(甜蜜点)")

print("\n" + "="*70)
print("提升幅度(60天超额)")
print("="*70)
old60_win = (old['exc_60d'] > 0).mean() * 100
new60_win = (new['exc_60d'] > 0).mean() * 100
old60_med = old['exc_60d'].median() * 100
new60_med = new['exc_60d'].median() * 100
print(f"胜率:    {old60_win:.1f}% → {new60_win:.1f}%  ({new60_win-old60_win:+.1f} 个百分点)")
print(f"中位超额: {old60_med:.2f}% → {new60_med:.2f}%  ({new60_med-old60_med:+.2f} 个百分点)")
print(f"信号数:  {len(old)} → {len(new)}  (砍掉 {len(old)-len(new)} 个,保留 {len(new)/len(old)*100:.0f}%)")
print("\n>>> 少而精:如果胜率和中位超额都上升,而信号数下降,就是正确的过滤。")
