# -*- coding: utf-8 -*-
"""拉出指定股票的所有信号明细,方便逐笔到 TradingView 对照"""
import pandas as pd
import sys

ticker = sys.argv[1] if len(sys.argv) > 1 else '7233.KL'

df = pd.read_csv('planb_backtest_signals.csv')
df['date'] = pd.to_datetime(df['date'])

sub = df[df['ticker'] == ticker].copy().sort_values('date')

if sub.empty:
    print(f"没有 {ticker} 的信号。可用的股票代码:")
    print(", ".join(sorted(df['ticker'].unique())))
else:
    print("="*90)
    print(f"{ticker} 的所有信号明细(共 {len(sub)} 笔)")
    print("="*90)
    show = sub[['date', 'resonance', 'red_ratio',
                'ret_20d', 'exc_20d', 'ret_60d', 'exc_60d']].copy()
    show['date'] = show['date'].dt.strftime('%Y-%m-%d')
    for col in ['ret_20d', 'exc_20d', 'ret_60d', 'exc_60d']:
        show[col] = (show[col] * 100).round(1).astype(str) + '%'
    print(show.to_string(index=False))

    print("\n" + "="*90)
    print("小结")
    print("="*90)
    win60 = (sub['exc_60d'] > 0).mean() * 100
    avg60 = sub['exc_60d'].mean() * 100
    print(f"60天超额胜率: {win60:.1f}%   平均超额: {avg60:.2f}%")
    print(f"最好的一笔(60d超额): {sub['exc_60d'].max()*100:.1f}%  "
          f"日期 {sub.loc[sub['exc_60d'].idxmax(),'date'].strftime('%Y-%m-%d')}")
    print(f"最差的一笔(60d超额): {sub['exc_60d'].min()*100:.1f}%  "
          f"日期 {sub.loc[sub['exc_60d'].idxmin(),'date'].strftime('%Y-%m-%d')}")
