# -*- coding: utf-8 -*-
"""
crsi_top50_findings.py

从已跑出的 crsi_momentum_signals.csv 里再挖一层，看市值前50大工业股里
有没有"常客"——反复触发B组(双确认)信号、而且表现稳定好的股票，这些
可能是以后独立观察名单的候选。

完全基于本地已有CSV，不需要重新拉数据。

运行方式:
    cd ~/Documents/PlanB_Scanner
    python3 crsi_top50_findings.py
"""

import pandas as pd

CRSI_CSV = "crsi_momentum_signals.csv"


def main():
    df = pd.read_csv(CRSI_CSV)
    b = df[df['monthly_confirmed']].copy()

    print("=" * 78)
    print("【1】哪些股票最常触发双确认信号，且表现如何")
    print("=" * 78)
    per_stock = b.groupby('ticker').agg(
        触发次数=('exc_12w', 'count'),
        胜率_12周=('ret_12w', lambda x: (x > 0).mean()),
        平均超额_12周=('exc_12w', 'mean'),
        平均超额_4周=('exc_4w', 'mean'),
    ).round(3)
    per_stock = per_stock[per_stock['触发次数'] >= 20].sort_values('触发次数', ascending=False)
    print(f"触发次数>=20次的'常客'股票 (共{len(per_stock)}支):")
    print(per_stock.to_string())

    print("\n" + "=" * 78)
    print("【2】'常客'里，哪些是稳定的好表现者(触发多且胜率、超额都不错)")
    print("=" * 78)
    reliable = per_stock[(per_stock['胜率_12周'] >= 0.60) & (per_stock['平均超额_12周'] >= 0.08)]
    if len(reliable) > 0:
        print(reliable.to_string())
        print(f"\n→ 这 {len(reliable)} 支股票，触发次数多(样本可信)且表现稳定好，")
        print("  值得放进独立观察名单，日常重点盯这几支的CRSI状态")
    else:
        print("  没有股票同时满足'触发>=20次 且 胜率>=60% 且 平均超额>=8%'")

    print("\n" + "=" * 78)
    print("【3】CRSI触发值高低，是否和后续表现相关(单纯≥80 vs 更极端的90+)")
    print("=" * 78)
    b['crsi_bucket'] = pd.cut(b['crsi_weekly'], bins=[80, 85, 90, 95, 100],
                                labels=['80-85', '85-90', '90-95', '95-100'])
    bucket_stats = b.groupby('crsi_bucket', observed=True).agg(
        信号数=('exc_12w', 'count'),
        胜率=('ret_12w', lambda x: (x > 0).mean()),
        平均超额=('exc_12w', 'mean'),
    ).round(3)
    print(bucket_stats.to_string())
    print("\n(如果数值随CRSI越高越好，说明'越极端越强'；如果没有明显趋势，")
    print(" 说明只要过80这个门槛，具体多高不重要)")

    print("\n" + "=" * 78)
    print("【4】月线确认率——哪些股票'一旦周线触发，几乎总能等到月线确认'")
    print("=" * 78)
    all_weekly = df.groupby('ticker').agg(
        周线信号数=('monthly_confirmed', 'count'),
        月线确认率=('monthly_confirmed', 'mean'),
    ).round(3)
    all_weekly = all_weekly[all_weekly['周线信号数'] >= 15].sort_values('月线确认率', ascending=False)
    print(f"周线信号数>=15次的股票，按月线确认率排序 (共{len(all_weekly)}支):")
    print(all_weekly.head(15).to_string())


if __name__ == "__main__":
    main()

