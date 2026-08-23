#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import glob
import os
from datetime import datetime

SCANNER_DIR = os.path.expanduser("~/Documents/PlanB_Scanner")


def latest_log(pattern):
    files = sorted(glob.glob(os.path.join(SCANNER_DIR, pattern)))
    return files[-1] if files else None


def parse_mcdx_log(path):
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    m = re.search(r"KLSE 马股.*?\n-+\n(.*?)\n\n", text, re.S)
    if not m:
        return {}
    block = m.group(1)
    results = {}
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        code = parts[0]
        if not re.match(r"^\d{4}\.KL$", code):
            continue
        try:
            score = float(parts[2])
        except ValueError:
            continue
        signal = "买入" if "买入" in line else ("关注" if "关注" in line else "避免")
        results[code] = {"score": score, "signal": signal}
    return results


def parse_dwm_log(path):
    if not path or not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    m = re.search(r"【KLSE】命中.*?\n(.*?)(?:\n\n|\Z)", text, re.S)
    if not m:
        return set()
    block = m.group(1)
    hits = set()
    for line in block.splitlines():
        m2 = re.search(r"(\d{4}\.KL)", line)
        if m2:
            hits.add(m2.group(1))
    return hits


def main():
    mcdx_path = latest_log("friday_mcdx_*.log")
    dwm_path = latest_log("friday_dwm_*.log")
    mcdx = parse_mcdx_log(mcdx_path)
    dwm_hits = parse_dwm_log(dwm_path)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 70)
    print(f"【Plan B 周五融合报告】 {now}")
    print("=" * 70)
    print()
    print(f"MCDX扫描：{len(mcdx)}只股票")
    print(f"DWM扫描：{len(dwm_hits)}只股票")
    print()

    mcdx_codes = set(mcdx.keys())
    green = sorted(mcdx_codes & dwm_hits, key=lambda c: -mcdx[c]["score"])
    yellow_a = sorted(mcdx_codes - dwm_hits, key=lambda c: -mcdx[c]["score"])
    yellow_b = sorted(dwm_hits - mcdx_codes)

    print("=" * 70)
    print(f"绿灯（同时通过MCDX和DWM）：{len(green)}只")
    print("=" * 70)
    if green:
        for c in green:
            print(f"  {c:<10} MCDX得分 {mcdx[c]['score']:6.1f}分  DWM共振  [{mcdx[c]['signal']}]")
    else:
        print("  (无交集)")
    print()

    print("=" * 70)
    print(f"黄灯-A（只通过MCDX）：{len(yellow_a)}只")
    print("=" * 70)
    for c in yellow_a[:10]:
        print(f"  {c:<10} MCDX得分 {mcdx[c]['score']:6.1f}分  DWM未共振  [{mcdx[c]['signal']}]")
    if len(yellow_a) > 10:
        print(f"  ... 还有 {len(yellow_a) - 10}只")
    print()

    print("=" * 70)
    print(f"黄灯-B（只通过DWM）：{len(yellow_b)}只")
    print("=" * 70)
    if yellow_b:
        for c in yellow_b:
            print(f"  {c:<10} DWM共振  MCDX不在清单")
    else:
        print("  (无)")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
