#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
周五扫描报告生成器 - 自动合并MCDX和DWM结果，生成优先级清单
"""
import os
import re
from datetime import datetime

def parse_mcdx_log():
    """从MCDX日志提取候选和得分"""
    log_files = [f for f in os.listdir(os.path.expanduser('~/Documents/PlanB_Scanner'))
                 if f.startswith('friday_mcdx_')]
    if not log_files:
        return {}
    
    latest_log = os.path.expanduser(f'~/Documents/PlanB_Scanner/{sorted(log_files)[-1]}')
    
    results = {}
    with open(latest_log, 'r', encoding='utf-8') as f:
        content = f.read()
        # 查找 code: score 的模式
        matches = re.findall(r"([0-9]{4}\.KL).*?(\d+\.\d+)", content)
        for code, score in matches:
            results[code] = float(score)
    
    return results

def parse_dwm_log():
    """从DWM日志提取通过的候选"""
    log_files = [f for f in os.listdir(os.path.expanduser('~/Documents/PlanB_Scanner'))
                 if f.startswith('friday_dwm_')]
    if not log_files:
        return []
    
    latest_log = os.path.expanduser(f'~/Documents/PlanB_Scanner/{sorted(log_files)[-1]}')
    
    results = []
    with open(latest_log, 'r', encoding='utf-8') as f:
        content = f.read()
        matches = re.findall(r"([0-9]{4}\.KL)", content)
        results = list(set(matches))  # 去重
    
    return results

# 生成报告
print("=" * 70)
print(f"【Plan B 周五融合报告】 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)
print("")

mcdx_dict = parse_mcdx_log()
dwm_list = parse_dwm_log()

print(f"📊 MCDX扫描：{len(mcdx_dict)}只股票")
print(f"🔄 DWM扫描：{len(dwm_list)}只股票")
print("")

# 分类
green_light = {}  # 都过
yellow_mcdx = {}  # 只过MCDX
yellow_dwm = []   # 只过DWM

for code, score in mcdx_dict.items():
    if code in dwm_list:
        green_light[code] = score
    else:
        yellow_mcdx[code] = score

for code in dwm_list:
    if code not in mcdx_dict:
        yellow_dwm.append(code)

# 输出
print("=" * 70)
print(f"🔴 绿灯（同时通过MCDX和DWM）：{len(green_light)}只 ← 最高优先级")
print("=" * 70)
if green_light:
    for code, score in sorted(green_light.items(), key=lambda x: x[1], reverse=True):
        print(f"  {code:10s} MCDX得分 {score:6.1f}分 ✅ DWM共振")
else:
    print("  (无交集)")

print("")
print("=" * 70)
print(f"🟡 黄灯-A（只通过MCDX）：{len(yellow_mcdx)}只 ← 次优先级")
print("=" * 70)
for code, score in sorted(yellow_mcdx.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"  {code:10s} MCDX得分 {score:6.1f}分 ⚠️  DWM未共振")
if len(yellow_mcdx) > 10:
    print(f"  ... 还有 {len(yellow_mcdx)-10}只")

print("")
print("=" * 70)
print(f"🟡 黄灯-B（只通过DWM）：{len(yellow_dwm)}只 ← 观察名单")
print("=" * 70)
if yellow_dwm:
    for code in yellow_dwm:
        print(f"  {code:10s} DWM共振 ⚠️  MCDX得分不明 (可能不在Top 10)")
else:
    print("  (无)")

print("")
print("=" * 70)
print("📋 建议行动")
print("=" * 70)
print("""
1. 【绿灯】优先年报验证（同时通过两个条件）
2. 【黄灯-A】次日检查基本面（MCDX强但技术未确认）
3. 【黄灯-B】加入观察清单（技术强但smart money未进）
4. 无需立即买入，等待确认信号
""")

print("=" * 70)
print(f"📁 详细日志保存在 ~/Documents/PlanB_Scanner/friday_*.log")
print("=" * 70)

