#!/usr/bin/env python3
import sys, os, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.expanduser("~/Documents/PlanB_Scanner"))

import yfinance as yf
import planb_bridge as pb
import all_klse_sweetspot as ak

TICKERS = ["5026.KL", "7103.KL", "1155.KL", "6491.KL", "7161.KL"]
MONTHS = pb.PERSIST_WINDOW_MONTHS
print("对比窗口 months=%s，period=7y，auto_adjust=True\n" % MONTHS)

hdr = "%-10s %10s %10s %8s %10s %10s %8s" % (
    "ticker", "br_ratio", "ak_ratio", "同", "br_streak", "ak_streak", "同")
print(hdr)
print("-" * len(hdr))

mismatch = 0
for t in TICKERS:
    df = yf.download(t, period="7y", auto_adjust=True,
                     progress=False, threads=False)
    if isinstance(df.columns, __import__("pandas").MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df is None or df.empty:
        print("%-10s  下载失败/空" % t)
        continue

    br = pb.compute_persistence(df, months=MONTHS)
    ak_r, ak_s = ak.compute_persistence(df, months=MONTHS)

    def fmt(v):
        return "None" if v is None else "%.6f" % v

    same_r = (br["red_ratio"] is None and ak_r is None) or (
        br["red_ratio"] is not None and ak_r is not None
        and abs(br["red_ratio"] - ak_r) < 1e-9)
    same_s = br["red_streak"] == ak_s
    if not (same_r and same_s):
        mismatch += 1

    print("%-10s %10s %10s %8s %10d %10d %8s" % (
        t, fmt(br["red_ratio"]), fmt(ak_r), "✓" if same_r else "✗",
        br["red_streak"], ak_s, "✓" if same_s else "✗"))

    b_res = pb.compute_resonance_score(df)
    a_res = ak.compute_resonance_score(df)
    ok = abs(b_res - a_res) < 1e-9
    if not ok:
        mismatch += 1
    print("%-10s   resonance  bridge=%.4f  all_klse=%.4f  %s" % (
        "", b_res, a_res, "✓" if ok else "✗"))

print("\n不一致项: %d" % mismatch)
print("全部 ✓ 才可以统一到 planb_bridge；有任何 ✗ 先查差异，不要合并。")
