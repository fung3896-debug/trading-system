#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trade_performance.py —— 交易绩效分析
============================================================
读取 trade_log.py 里的真实交易记录，算出：
  1. 已实现盈亏（已经卖出部分的真实获利/亏损）
  2. 未实现盈亏（还持有部分，按当前市价算的浮动盈亏）
  3. 已平仓交易的胜率
  4. 按"依据类型"分类的表现（系统验证 vs 历史仓位 vs 主动决定 vs 规则触发）
  5. 持有天数（仅计算日期已知的交易）

用法：
    python3 trade_performance.py
    (需要 trade_log.py 在同一目录，需要网络抓当前价格)
"""

import warnings
warnings.filterwarnings('ignore')

from datetime import datetime
from collections import defaultdict

import yfinance as yf

from trade_log import TRADES


def fetch_current_price(symbol):
    try:
        df = yf.download(symbol, period='5d', progress=False, auto_adjust=True)
        if df.empty:
            return None
        return float(df['Close'].iloc[-1])
    except Exception:
        return None


def analyze():
    # 按股票分组，逐笔重演加权平均成本
    by_symbol = defaultdict(list)
    for t in TRADES:
        by_symbol[t['symbol']].append(t)

    realized_records = []   # 每笔已实现盈亏
    open_positions = {}     # symbol -> {name, lots, avg_cost}

    for symbol, trades in by_symbol.items():
        trades_sorted = sorted(trades, key=lambda x: (x['date'] or '0000-00-00'))
        lots = 0
        avg_cost = 0.0
        name = trades_sorted[0]['name']
        first_buy_date = None

        for t in trades_sorted:
            if t['action'] == 'BUY':
                if first_buy_date is None:
                    first_buy_date = t['date']
                new_lots = lots + t['lots']
                avg_cost = (lots * avg_cost + t['lots'] * t['price']) / new_lots if new_lots > 0 else 0
                lots = new_lots
            elif t['action'] == 'SELL':
                pnl_per_lot = t['price'] - avg_cost
                pnl_pct = (t['price'] - avg_cost) / avg_cost * 100 if avg_cost > 0 else 0
                holding_days = None
                if first_buy_date and t['date']:
                    d0 = datetime.strptime(first_buy_date, '%Y-%m-%d')
                    d1 = datetime.strptime(t['date'], '%Y-%m-%d')
                    holding_days = (d1 - d0).days
                realized_records.append({
                    'symbol': symbol, 'name': name, 'sell_date': t['date'],
                    'sell_price': t['price'], 'lots': t['lots'],
                    'cost_at_sale': avg_cost, 'pnl_per_lot': pnl_per_lot,
                    'pnl_pct': pnl_pct, 'reason': t['reason'],
                    'holding_days': holding_days,
                })
                lots -= t['lots']

        if lots > 0:
            open_positions[symbol] = {'name': name, 'lots': lots, 'avg_cost': avg_cost}

    # ===== 输出：已实现盈亏明细 =====
    print("=" * 100)
    print("已实现交易记录（已卖出部分）")
    print("=" * 100)
    print(f"{'股票':<12}{'卖出日期':<12}{'卖出价':>8}{'成本':>8}{'手数':>6}{'每手盈亏':>10}{'盈亏%':>8}  依据")
    print("-" * 100)

    total_realized_pnl = 0.0
    wins, losses = 0, 0
    for r in realized_records:
        print(f"{r['name']:<12}{r['sell_date'] or '未知':<12}{r['sell_price']:>8.3f}"
              f"{r['cost_at_sale']:>8.3f}{r['lots']:>6}{r['pnl_per_lot']:>10.3f}{r['pnl_pct']:>7.1f}%  {r['reason']}")
        total_realized_pnl += r['pnl_per_lot'] * r['lots']
        if r['pnl_per_lot'] > 0:
            wins += 1
        elif r['pnl_per_lot'] < 0:
            losses += 1

    print("-" * 100)
    print(f"已实现总盈亏（每股单位，未乘实际股数换算）：{total_realized_pnl:+.3f}")
    if wins + losses > 0:
        print(f"已平仓交易胜率：{wins}/{wins+losses} = {wins/(wins+losses)*100:.1f}%")

    # 按依据类型分类
    print("\n" + "=" * 100)
    print("按决策依据分类的表现")
    print("=" * 100)
    by_reason = defaultdict(list)
    for r in realized_records:
        # 归并成几个大类，方便比较
        reason = r['reason']
        if '系统验证' in reason:
            cat = '系统验证后建仓/规则触发'
        elif 'HALF' in reason or 'SELL触发' in reason:
            cat = '系统验证后建仓/规则触发'
        elif '历史仓位' in reason:
            cat = '历史仓位(未验证方法)'
        elif '主动决定' in reason:
            cat = '主动决定(非机械规则)'
        else:
            cat = '其他'
        by_reason[cat].append(r['pnl_pct'])

    for cat, pcts in by_reason.items():
        avg_pct = sum(pcts) / len(pcts)
        print(f"  {cat:<28}笔数:{len(pcts):>3}  平均盈亏:{avg_pct:>+7.2f}%")

    # ===== 输出：当前持仓未实现盈亏 =====
    print("\n" + "=" * 100)
    print("当前持仓（未实现盈亏，抓取最新价格中...）")
    print("=" * 100)
    print(f"{'股票':<12}{'持有手数':>8}{'加权成本':>10}{'现价':>10}{'浮动盈亏%':>12}")
    print("-" * 100)

    total_unrealized_pct_weighted = 0.0
    total_lots_for_avg = 0
    for symbol, pos in open_positions.items():
        price = fetch_current_price(symbol)
        if price is None:
            print(f"{pos['name']:<12}{pos['lots']:>8}{pos['avg_cost']:>10.3f}{'抓取失败':>10}")
            continue
        pnl_pct = (price - pos['avg_cost']) / pos['avg_cost'] * 100
        print(f"{pos['name']:<12}{pos['lots']:>8}{pos['avg_cost']:>10.3f}{price:>10.3f}{pnl_pct:>+11.2f}%")
        total_unrealized_pct_weighted += pnl_pct * pos['lots']
        total_lots_for_avg += pos['lots']

    if total_lots_for_avg > 0:
        print("-" * 100)
        print(f"当前持仓加权平均浮动盈亏：{total_unrealized_pct_weighted/total_lots_for_avg:+.2f}%")

    # ===== 持有天数（仅日期已知的） =====
    known_days = [r['holding_days'] for r in realized_records if r['holding_days'] is not None]
    print("\n" + "=" * 100)
    print("持有天数统计（仅日期已知的交易，日期缺失的交易不计入）")
    print("=" * 100)
    if known_days:
        print(f"  已知持有天数的交易：{len(known_days)} 笔")
        print(f"  平均持有天数：{sum(known_days)/len(known_days):.1f} 天")
        print(f"  最短：{min(known_days)} 天　最长：{max(known_days)} 天")
    else:
        print("  暂无日期完整的交易可计算")

    print("\n" + "=" * 100)
    print("说明：此为基于当前已记录交易的初步统计，样本量小（仅几笔），")
    print("不能当成有统计意义的胜率结论，只能作为持续记录的起点。")
    print("随着交易笔数增加，这份记录的参考价值会逐步提升。")
    print("=" * 100)


if __name__ == "__main__":
    analyze()
