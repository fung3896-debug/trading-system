# -*- coding: utf-8 -*-
"""按板块拆分511信号，分别验证甜蜜点(0.60-0.85)规则是否在各板块都成立"""
import pandas as pd
import os

def load_tickers(path):
    codes = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            code = line.split('#')[0].strip()
            if code:
                codes.append(code)
    return set(codes)

sectors = {
    '种植': os.path.expanduser('~/Desktop/plantation.txt'),
    '科技': os.path.expanduser('~/Desktop/tech_full.txt'),
    '消费1': os.path.expanduser('~/Desktop/consumer_1.txt'),
    '消费2': os.path.expanduser('~/Desktop/consumer_2.txt'),
    '消费3': os.path.expanduser('~/Desktop/consumer_3.txt'),
    '消费4': os.path.expanduser('~/Desktop/consumer_4.txt'),
    '能源': os.path.expanduser('~/Desktop/energy.txt'),
}

df = pd.read_csv('planb_backtest_signals.csv')
bins = [-0.01, 0.60, 0.85, 1.001]
labels = ['<0.60', '0.60-0.85(甜蜜点)', '>0.85(含满格)']

print("="*90)
print(f"511信号总数：{len(df)}  |  按板块拆分验证甜蜜点规则")
print("="*90)

for name, path in sectors.items():
    if not os.path.exists(path):
        print(f"\n{name}：清单文件不存在，跳过 ({path})")
        continue
    tickers = load_tickers(path)
    sub_all = df[df['ticker'].isin(tickers)]
    if len(sub_all) == 0:
        print(f"\n{name}：511信号里没有这个板块的历史记录，跳过")
        continue

    print(f"\n【{name}】板块清单{len(tickers)}只，511信号里命中{len(sub_all)}条")
    sub_all = sub_all.copy()
    sub_all['bucket'] = pd.cut(sub_all['red_ratio'], bins=bins, labels=labels)
    print(f"  {'分组':<20}{'信号数':>8}{'胜率(60d)':>12}{'中位超额(60d)':>16}")
    for label in labels:
        g = sub_all[sub_all['bucket'] == label]
        if len(g) == 0:
            continue
        win = (g['exc_60d'] > 0).mean() * 100
        med = g['exc_60d'].median() * 100
        print(f"  {label:<20}{len(g):>8}{win:>11.1f}%{med:>15.2f}%")

print("\n" + "="*90)
print("解读：若各板块都是'甜蜜点'组胜率/超额收益最高，说明规则跨板块稳定，")
print("可以放心继续用同一套规则扫新板块。若某板块明显不同，扫那类板块时要格外小心。")
print("="*90)
