# -*- coding: utf-8 -*-
"""分析回测信号的独立性:按股票、按年份分组,揭露隐藏偏差"""
import pandas as pd

df = pd.read_csv('planb_backtest_signals.csv')
df['date'] = pd.to_datetime(df['date'])
df['year'] = df['date'].dt.year

print("="*70)
print(f"总信号数: {len(df)}")
print("="*70)

print("\n【1】每支股票贡献多少信号 + 各自的60天平均超额")
by_stock = df.groupby('ticker').agg(
    信号数=('ticker', 'size'),
    平均超额60d=('exc_60d', 'mean'),
    胜率60d=('exc_60d', lambda x: (x > 0).mean())
).sort_values('信号数', ascending=False)
by_stock['信号占比'] = (by_stock['信号数'] / len(df) * 100).round(1)
by_stock['平均超额60d'] = (by_stock['平均超额60d'] * 100).round(2)
by_stock['胜率60d'] = (by_stock['胜率60d'] * 100).round(1)
print(by_stock.to_string())

top3_share = by_stock['信号数'].head(3).sum() / len(df) * 100
print(f"\n>>> 前3名股票占了 {top3_share:.1f}% 的信号")
if top3_share > 50:
    print("    警告:信号高度集中,'系统有效'可能其实是'这几支股恰好长期强势'")

print("\n【2】每年触发多少信号 + 当年60天平均超额")
by_year = df.groupby('year').agg(
    信号数=('year', 'size'),
    平均超额60d=('exc_60d', 'mean')
)
by_year['信号占比'] = (by_year['信号数'] / len(df) * 100).round(1)
by_year['平均超额60d'] = (by_year['平均超额60d'] * 100).round(2)
print(by_year.to_string())

print("\n【3】独立性估算")
unique_stock_year = df.groupby(['ticker', 'year']).size()
print(f"不同的 (股票×年份) 组合数: {len(unique_stock_year)}")
print(f"平均每个组合有 {len(df)/len(unique_stock_year):.1f} 个信号")
print(f">>> 真正的'独立事件'约 {len(unique_stock_year)} 个,而非表面的 {len(df)} 个")

print("\n【4】分时期看60天平均超额(检验是否只靠某段行情)")
df['period'] = pd.cut(df['year'],
    bins=[1999, 2010, 2015, 2020, 2027],
    labels=['2000-2010', '2011-2015', '2016-2020', '2021-2026'])
by_period = df.groupby('period', observed=True).agg(
    信号数=('period', 'size'),
    平均超额60d=('exc_60d', 'mean'),
    胜率60d=('exc_60d', lambda x: (x > 0).mean())
)
by_period['平均超额60d'] = (by_period['平均超额60d'] * 100).round(2)
by_period['胜率60d'] = (by_period['胜率60d'] * 100).round(1)
print(by_period.to_string())
print("\n>>> 如果某个时期超额特别高、其他时期接近0,说明系统依赖特定行情")
