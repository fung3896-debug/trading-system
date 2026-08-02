# -*- coding: utf-8 -*-
"""验证"红满紫高"直觉的第一步：用现有511信号数据，
按 red_ratio 更细的区间分组，看 exc_20d / exc_60d 表现"""
import pandas as pd

df = pd.read_csv('planb_backtest_signals.csv')

print("="*78)
print(f"总信号数：{len(df)}")
print("="*78)

bins = [-0.01, 0.30, 0.60, 0.85, 0.95, 1.001]
labels = ['0.00-0.30(几乎无庄家)', '0.30-0.60(建仓初期)',
          '0.60-0.85(已验证甜蜜点)', '0.85-0.95(接近满格)', '0.95-1.00(满格/紫线满)']
df['bucket'] = pd.cut(df['red_ratio'], bins=bins, labels=labels)

print(f"\n{'分组':<28}{'信号数':>8}{'胜率(20d)':>12}{'中位超额(20d)':>16}{'胜率(60d)':>12}{'中位超额(60d)':>16}")
print("-"*95)
for label in labels:
    sub = df[df['bucket'] == label]
    if len(sub) == 0:
        continue
    win20 = (sub['exc_20d'] > 0).mean() * 100
    med20 = sub['exc_20d'].median() * 100
    win60 = (sub['exc_60d'] > 0).mean() * 100
    med60 = sub['exc_60d'].median() * 100
    print(f"{label:<28}{len(sub):>8}{win20:>11.1f}%{med20:>15.2f}%{win60:>11.1f}%{med60:>15.2f}%")

print("\n" + "="*78)
print("解读：如果'0.95-1.00'这组胜率/超额收益明显高于'0.60-0.85'甜蜜点组，")
print("说明'红满紫高'直觉有数据支撑，值得进一步细化验证。")
print("如果差不多甚至更差，说明肉眼看到的'赢家都是红满'很可能是幸存者偏差。")
print("="*78)
