#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trade_log.py —— 交易记录（手动维护）
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

    # ---- DUFU (7233.KL) ----
    {'date': None, 'symbol': '7233.KL', 'name': 'DUFU',
     'action': 'BUY', 'price': 2.467, 'lots': 3, 'reason': '历史仓位(未验证的"攻"信号方法,系统建立前)'},
    {'date': '2026-07-29', 'symbol': '7233.KL', 'name': 'DUFU',
     'action': 'SELL', 'price': 2.52, 'lots': 2, 'reason': '主动决定'},

    # ---- EG (8907.KL) ----
    {'date': None, 'symbol': '8907.KL', 'name': 'EG',
     'action': 'BUY', 'price': 1.797, 'lots': 6, 'reason': '系统验证后建仓,约8月初'},
]
