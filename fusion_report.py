#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
融合报告 - 合并MCDX和DWM结果，生成优先级清单
"""
import os
import sys
sys.path.insert(0, os.path.expanduser('~/Documents/PlanB_Scanner'))

from shared_watchlist import WATCHLIST
import v7pro_mcdx_scan as v7
import dwm_macd_scanner as dwm

print("=" * 70)
print("【Plan B 周五融合扫描报告】")
print("=" * 70)
print("")

# 运行MCDX扫描
print("📊 运行MCDX扫描...")
mcdx_results = v7.scan_mcdx(WATCHLIST)

# 运行DWM扫描
print("📊 运行DWM扫描...")
dwm_results = dwm.scan_dwm(WATCHLIST["KLSE"])

# 合并结果
print("")
print("=" * 70)
print("【融合结果】")
print("=" * 70)
print("")

# 找交集（都过）
intersection = {}
for r in mcdx_results:
    for d in dwm_results:
        if r['symbol'] == d['symbol']:
            intersection[r['symbol']] = {
                'mcdx': r.get('score', 0),
                'dwm': '✅ 通过',
                'priority': '🔴 绿灯'
            }

# 只过MCDX
only_mcdx = {}
for r in mcdx_results:
    if r['symbol'] not in intersection:
        only_mcdx[r['symbol']] = {
            'mcdx': r.get('score', 0),
            'dwm': '❌',
            'priority': '🟡 黄灯'
        }

# 只过DWM
only_dwm = {}
for d in dwm_results:
    if d['symbol'] not in intersection:
        only_dwm[d['symbol']] = {
            'mcdx': '?',
            'dwm': '✅ 通过',
            'priority': '🟡 黄灯'
        }

# 输出
print(f"🔴 绿灯（同时通过MCDX和DWM）：{len(intersection)}只")
for code, data in sorted(intersection.items(), key=lambda x: x[1]['mcdx'], reverse=True):
    print(f"  {code:10s} MCDX={data['mcdx']:6.1f} DWM={data['dwm']}")

print("")
print(f"🟡 黄灯（只通过MCDX）：{len(only_mcdx)}只")
for code, data in sorted(only_mcdx.items(), key=lambda x: x[1]['mcdx'], reverse=True)[:5]:
    print(f"  {code:10s} MCDX={data['mcdx']:6.1f} DWM={data['dwm']}")

print("")
print(f"🟡 黄灯（只通过DWM）：{len(only_dwm)}只")
for code, data in only_dwm.items():
    print(f"  {code:10s} MCDX={data['mcdx']} DWM={data['dwm']}")

print("")
print("=" * 70)
print("建议：优先年报验证绿灯候选，再看黄灯")
print("=" * 70)

