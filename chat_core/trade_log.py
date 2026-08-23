#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trade_log.py —— 交易记录（手动维护）
============================================================
记录所有已经真实发生过的买卖操作。这是"发生过什么"的事实记录，
不是"现在持有什么"（那是 position_monitor.py 的 POSITIONS 负责）。

用法：
  每次真实执行买入/卖出后，在 TRADES 列表里加一行。
  跑 python3 trade_performance.py 会读取这份记录，算出实际绩效。

字段说明：
  date       交易日期 'YYYY-MM-DD'，日期不确定的用 None
  symbol     股票代码
  name       名称
  action     'BUY' 买入 / 'SELL' 卖出
  price      成交价
  lots       本次交易的手数（不是持仓总数）
  reason     触发依据：'系统验证后建仓' / 'HALF触发' / 'SELL触发' /
             '主动决定' / '历史仓位(未验证方法)' 等，用于事后检讨
             "跟着规则做的" vs "自己主观决定的"两类表现有没有差异
"""

TRADES = [
    # ---- MHC (5026.KL) ----
    {'date': '2026-07-13', 'symbol': '5026.KL', 'name': 'MHC',
     'action': 'BUY', 'price': 1.78, 'lots': 2, 'reason': '系统验证后建仓'},
    {'date': '2026-07-20', 'symbol': '5026.KL', 'name': 'MHC',
     'action': 'BUY', 'price': 1.87, 'lots': 2, 'reason': '系统验证后加码'},
    {'date': '2026-07-24', 'symbol': '5026.KL', 'name': 'MHC',
     'action': 'BUY', 'price': 1.89, 'lots': 2, 'reason': '系统验证后加码'},

    # ---- SKBSHUT (7115.KL) ----
    {'date': None, 'symbol': '7115.KL', 'name': 'SKBSHUT',
     'action': 'BUY', 'price': 0.929, 'lots': 8, 'reason': '系统验证后建仓,日期未记录'},

    # ---- Spritzer (7103.KL) ----
    {'date': None, 'symbol': '7103.KL', 'name': 'Spritzer',
     'action': 'BUY', 'price': 2.89, 'lots': 6, 'reason': '系统验证后建仓,日期未记录'},
    {'date': '2026-07-29', 'symbol': '7103.KL', 'name': 'Spritzer',
     'action': 'SELL', 'price': 2.96, 'lots': 4, 'reason': '主动决定(尾盘拉高观察后)'},
    {'date': '2026-08-04', 'symbol': '7103.KL', 'name': 'Spritzer',
     'action': 'SELL', 'price': 3.00, 'lots': 1, 'reason': 'HALF触发'},
    {'date': '2026-08-10', 'symbol': '7103.KL', 'name': 'Spritzer',
     'action': 'SELL', 'price': 3.03, 'lots': 1, 'reason': 'HALF触发,清仓最后1lot'},

    # ---- DUFU (7233.KL) ----
    {'date': None, 'symbol': '7233.KL', 'name': 'DUFU',
     'action': 'BUY', 'price': 2.467, 'lots': 3, 'reason': '历史仓位(未验证的"攻"信号方法,系统建立前)'},
    {'date': '2026-07-29', 'symbol': '7233.KL', 'name': 'DUFU',
     'action': 'SELL', 'price': 2.52, 'lots': 2, 'reason': '主动决定'},
    {'date': '2026-08-13', 'symbol': '7233.KL', 'name': 'DUFU',
     'action': 'SELL', 'price': 2.89, 'lots': 1, 'reason': '主动决定,清仓最后1lot(此前连续多日SELL信号未跟,今日改变主意)'},

    # ---- RHBBANK (1066.KL) ----
    {'date': '2026-08-11', 'symbol': '1066.KL', 'name': 'RHBBANK',
     'action': 'BUY', 'price': 8.82, 'lots': 1, 'reason': '系统验证后建仓(持续双强型,streak12月)'},

    {'date': '2026-08-12', 'symbol': '7115.KL', 'name': 'SKBSHUT',
     'action': 'SELL', 'price': 1.26, 'lots': 4, 'reason': '主动决定(接近+30%门槛,提前落袋)'},
    {'date': '2026-08-19', 'symbol': '7115.KL', 'name': 'SKBSHUT',
     'action': 'SELL', 'price': 1.10, 'lots': 4, 'reason': '主动决定,清仓最后4lot(技术面转弱后落袋)'},

    # ---- EG (8907.KL) ----
    {'date': None, 'symbol': '8907.KL', 'name': 'EG',
     'action': 'BUY', 'price': 1.797, 'lots': 6, 'reason': '系统验证后建仓,约8月初'},
    {'date': '2026-08-14', 'symbol': '8907.KL', 'name': 'EG',
     'action': 'SELL', 'price': 1.81, 'lots': 5, 'reason': '主动决定,剩2lot'},

    # ---- KERJAYA (7161.KL) ----
    {'date': '2026-08-18', 'symbol': '7161.KL', 'name': 'KERJAYA',
     'action': 'BUY', 'price': 2.73, 'lots': 1, 'reason': '系统验证后建仓(streak实际15月,三模型估值一致低估22-42%)'},

    # ---- KFIMA (6491.KL) ----
    {'date': '2026-08-17', 'symbol': '6491.KL', 'name': 'KFIMA',
     'action': 'BUY', 'price': 2.78, 'lots': 1, 'reason': '系统验证后建仓(streak16月,三模型估值一致低估60-75%)'},

    # ---- AMBANK (1015.KL) ----
    {'date': '2026-08-14', 'symbol': '1015.KL', 'name': 'AMBANK',
     'action': 'BUY', 'price': 7.35, 'lots': 1, 'reason': '系统验证后建仓(持续双强型,与RHBBANK同梯队)'},
]
