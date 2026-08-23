#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
decision_priority.py —— 持仓决策优先级分级
============================================================
不重写 position_monitor.py 的任何止盈止损规则，只是在它的输出上
加一层"今天该多在意哪一笔"的分级，帮你从"每天看到同样一句提醒"
的疲劳感里跳出来。

分级逻辑：
  🔴 重要：硬止损/NTA破位触发（永远重要）；
           或者今天的建议等级比昨天更严重（比如HOLD→HALF、HALF→SELL）
           —— 这种"状态刚恶化"的情况，今天必须看一眼
  🟡 中：建议已经持续多天、状态没有变化（比如已经挂了两天的HALF）
         —— 不是今天才发生，但这件事还没了结，提醒你还欠一个决定
  🟢 轻：HOLD 且离任何门槛都还有余量 —— 今天不用特别花心思

用法：
    python3 decision_priority.py
    (依赖同目录下的 position_monitor.py，直接复用它的 POSITIONS 清单
     和 analyze_position 函数，不重复定义规则，避免两边逻辑分裂)
"""

import json
import os
from datetime import datetime

from position_monitor import POSITIONS, analyze_position

STATE_FILE = "decision_priority_state.json"

# 与止盈规则本身无关，纯粹用来判断"这个建议算不算逼近门槛"，
# 帮HOLD再细分出"轻松持有"还是"快到门槛了，该多看两眼"
NEAR_THRESHOLD_PCT = 0.05  # 现价距离下一个触发门槛 5% 以内，算"值得留意"
VOL_SPIKE_MULTIPLIER = 3.0  # 量比超过此倍数视为异常放量，不管止盈止损等级有没有变，直接标记重要


def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, encoding='utf-8') as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def action_level(action_code):
    """把 position_monitor 的等级转成数字，方便比较"today比昨天更严重"""
    return {'HOLD': 0, 'HALF': 1, 'SELL': 2, 'STOP': 3}.get(action_code, 0)


def classify_priority(symbol, today_top_action, r, state):
    """
    回传 (priority, reason)
    priority: '重要' / '中' / '轻'
    """
    prev = state.get(symbol, {})
    prev_action = prev.get('last_action', 'HOLD')
    prev_level = action_level(prev_action)
    today_level = action_level(today_top_action)

    # ① 硬止损/NTA破位 —— 永远重要，不管是不是新的
    if today_top_action == 'STOP':
        return '重要', '硬止损或NTA破位已触发，需立即处理'

    # ② 放量异常 —— 不管止盈止损等级有没有变，量比过高本身就值得多看一眼
    vol_note = _check_vol_spike(r)
    if vol_note:
        return '重要', vol_note

    # ③ 状态比昨天更严重 —— 今天刚恶化/刚升级，重要
    if today_level > prev_level:
        return '重要', f'建议从「{prev_action}」升级为「{today_top_action}」，状态今天刚变化'

    # ④ SELL/HALF 但已经持续多天，不是今天新发生 —— 中，提醒你还没处理完
    if today_top_action in ('SELL', 'HALF'):
        days = prev.get('days_active', 1)
        return '中', f'「{today_top_action}」建议已持续{days}天，仍未执行/未了结，非今日新增'

    # ⑤ HOLD，但检查现价是否已逼近下一个门槛（提前预警，而不是等触发那天才说"重要"）
    near_note = _check_near_threshold(r)
    if near_note:
        return '中', near_note

    return '轻', '持有中，距离任何止盈止损门槛尚有余量'


def _check_vol_spike(r):
    """检查量比是否异常放大（不管是放量涨还是放量跌，量比本身过高就值得留意）"""
    vol_ratio = r.get('vol_ratio')
    if vol_ratio is None:
        return None
    if vol_ratio >= VOL_SPIKE_MULTIPLIER:
        return f'量比达{vol_ratio:.2f}倍（阈值{VOL_SPIKE_MULTIPLIER:.1f}），明显异常放量，建议查看今日走势判断是买盘涌入还是出货'
    return None


def _check_near_threshold(r):
    """检查现价是否已逼近止损价（数字上很接近但还没跌破）"""
    price = r.get('price')
    stop_price = r.get('stop_price')
    if price is None or stop_price is None:
        return None
    if price > stop_price:
        gap_pct = (price - stop_price) / price
        if 0 < gap_pct <= NEAR_THRESHOLD_PCT:
            return f'现价距硬止损价仅{gap_pct:.1%}，接近但未触发，建议多留意'
    return None


def update_state(symbol, today_top_action, state):
    """更新本地记录：这个建议是不是从昨天延续下来的"""
    prev = state.get(symbol, {})
    prev_action = prev.get('last_action', 'HOLD')
    if today_top_action == prev_action:
        days_active = prev.get('days_active', 1) + 1
    else:
        days_active = 1
    state[symbol] = {
        'last_action': today_top_action,
        'days_active': days_active,
        'last_seen': datetime.now().strftime('%Y-%m-%d'),
    }


def main():
    state = load_state()

    print("=" * 92)
    print(f"📌 决策优先级分级  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("   （基于 position_monitor.py 的同一套规则，只加了「今天该多在意哪笔」的分级）")
    print("=" * 92)

    rank = {'STOP': 0, 'SELL': 1, 'HALF': 2, 'HOLD': 3}
    priority_icon = {'重要': '🔴 重要', '中': '🟡 中', '轻': '🟢 轻'}
    priority_order = {'重要': 0, '中': 1, '轻': 2}

    rows = []
    for pos in POSITIONS:
        r = analyze_position(pos)
        if 'error' in r:
            print(f"\n{pos['name']} ({pos['symbol']})  ❌ {r['error']}")
            continue

        top_action = min(r['actions'], key=lambda a: rank[a[0]])
        today_top_action = top_action[0]
        reason_text = top_action[1]

        priority, note = classify_priority(pos['symbol'], today_top_action, r, state)
        rows.append((priority, pos, r, today_top_action, reason_text, note))

        update_state(pos['symbol'], today_top_action, state)

    save_state(state)

    rows.sort(key=lambda x: priority_order[x[0]])

    for priority, pos, r, today_top_action, reason_text, note in rows:
        print(f"\n{'─'*92}")
        print(f"{priority_icon[priority]}  {pos['name']:<10}({pos['symbol']})  "
              f"现价 {r['price']:.3f}  盈亏 {r['pnl_pct']:+.1f}%")
        print(f"    机械建议：{today_top_action} —— {reason_text}")
        print(f"    优先级判断：{note}")

    print("\n" + "=" * 92)
    print("说明：本脚本不改变 position_monitor.py 的任何止盈止损规则，只是把「今天该")
    print("多花心思看哪一笔」标出来。🔴重要 建议今天就看；🟡中 是还没了结的旧建议，")
    print("找时间处理；🟢轻 今天可以不用特别管。最终决定权仍在你。")
    print("=" * 92)


if __name__ == "__main__":
    main()
