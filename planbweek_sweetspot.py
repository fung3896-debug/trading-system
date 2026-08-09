"""
KLSE 21支 甜蜜点验证 —— 60天持有版
测的是你实际在用的规则：resonance>=55 且 red_ratio 0.60~0.85(甜蜜点)
持有期 60 天，对齐 511信号回测的验证口径（而不是旧版 planbweek 的 5天）。
无前视偏差：每一天先截断日线再resample周/月线。

结论记录（2026-08-05 首次跑出的结果，仅供参考，不是定论）：
整体甜蜜点组胜率 77.0% vs 非甜蜜点 74.6%，差距仅2.4%，不算强；
且甜蜜点组平均涨幅反而更低(+8.5% vs +14.5%)——"更稳但涨得少"，
方向上与511信号回测的"3.76%超额收益"一致。
但21支里14支样本不足(甜蜜点天数<10)，能看的只有4支(1066/4863/6459/8907)，
其中2支"信号有效"、2支"反向"，完全对半分，不构成定论。
5263.KL 249天里248天都在甜蜜点区间(几乎常年命中)，
另一批股票(0099/5026/7103等)整个250天从未触发——
说明不同股票的red_ratio基线差异很大，同一套0.60-0.85阈值不是普适的，
这本身是值得深挖的现象，不是噪声。
若要做得更扎实：扩大样本用511信号回测那批更大股票池重跑这套60天口径。
"""

import sys
sys.path.insert(0, '/Users/fernando/Documents/PlanB_Scanner')

import yfinance as yf
import pandas as pd
import csv
from datetime import datetime
from collections import defaultdict

import v7pro_mcdx_scan as v7

MIN_LEN = max(v7.BANKER_PERIOD, v7.HOT_PERIOD) + 10  # 60
DAYS_BACK = 250
FORWARD = 60
PERSIST_MONTHS = 18


def compute_signal(df_trunc):
    d_tf = v7.analyze_timeframe_last(df_trunc, MIN_LEN)
    w_tf = v7.analyze_timeframe_last(v7.resample_ohlcv(df_trunc, 'W'), MIN_LEN)
    m_tf = v7.analyze_timeframe_last(v7.resample_ohlcv(df_trunc, 'ME'), MIN_LEN)
    resonance = v7.compute_resonance_score(d_tf, w_tf, m_tf)
    if resonance is None:
        return None

    red_ratio, red_streak, window_n = v7.compute_monthly_persistence(df_trunc, PERSIST_MONTHS)
    if red_ratio is None:
        return None

    is_sweet = v7.is_sweet_spot(resonance, red_ratio)
    return resonance, red_ratio, red_streak, is_sweet


KLSE_21 = ['7233.KL', '5211.KL', '8907.KL', '6459.KL', '5249.KL', '5026.KL',
           '5286.KL', '0225.KL', '0099.KL', '5031.KL', '5681.KL', '7163.KL',
           '8869.KL', '1066.KL', '0215.KL', '0326.KL', '7103.KL', '5263.KL',
           '4863.KL', '5243.KL', '5142.KL']

print("\n" + "=" * 70)
print("KLSE 21支 甜蜜点验证 60天持有版")
print(f"回溯{DAYS_BACK}天 | {FORWARD}天后结算 | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print("规则：resonance>=55 且 red_ratio 0.60~0.85（甜蜜点），对齐511信号回测口径")
print("=" * 70 + "\n")

all_records = []

for ticker in KLSE_21:
    try:
        print(f"下载 {ticker} ...", end=" ", flush=True)
        df = yf.download(ticker, period='7y', auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna(subset=['Close'])

        if len(df) < 300:
            print("数据不足,跳过")
            continue

        close_full = df['Close']
        if isinstance(close_full, pd.DataFrame):
            close_full = close_full.iloc[:, 0]

        start_idx = max(MIN_LEN, len(df) - DAYS_BACK - FORWARD)

        print("计算中...", end=" ", flush=True)

        for i in range(start_idx, len(df) - FORWARD):
            df_trunc = df.iloc[:i + 1]

            sig = compute_signal(df_trunc)
            if sig is None:
                continue
            resonance, red_ratio, red_streak, is_sweet = sig

            price_today = float(close_full.iloc[i])
            price_fwd = float(close_full.iloc[i + FORWARD])
            change_pct = (price_fwd - price_today) / price_today * 100
            result = "涨" if change_pct > 0 else "跌"

            all_records.append({
                'ticker': ticker,
                'date': df.index[i].strftime('%Y-%m-%d'),
                'resonance': round(resonance, 1),
                'red_ratio': round(red_ratio, 3),
                'red_streak': red_streak,
                'is_sweet': is_sweet,
                'change_pct': round(change_pct, 2),
                'result': result,
            })

        print(f"完成 (累计{len(all_records)}条)")

    except Exception as e:
        print(f"错误: {e}")
        continue

# ============ 汇总：整体甜蜜点 vs 非甜蜜点 ============
sweet_recs = [r for r in all_records if r['is_sweet']]
nonsweet_recs = [r for r in all_records if not r['is_sweet']]

print("\n" + "=" * 70)
print("整体汇总（21支股票合并）")
print("=" * 70)
if sweet_recs and nonsweet_recs:
    win_sweet = sum(1 for r in sweet_recs if r['result'] == '涨') / len(sweet_recs) * 100
    win_nonsweet = sum(1 for r in nonsweet_recs if r['result'] == '涨') / len(nonsweet_recs) * 100
    avg_sweet = sum(r['change_pct'] for r in sweet_recs) / len(sweet_recs)
    avg_nonsweet = sum(r['change_pct'] for r in nonsweet_recs) / len(nonsweet_recs)
    print(f"甜蜜点组:   {len(sweet_recs):>5} 笔  胜率 {win_sweet:.1f}%  平均涨幅 {avg_sweet:+.1f}%")
    print(f"非甜蜜点组: {len(nonsweet_recs):>5} 笔  胜率 {win_nonsweet:.1f}%  平均涨幅 {avg_nonsweet:+.1f}%")
    print(f"胜率差异: {win_sweet - win_nonsweet:+.1f}%")

# ============ 逐股票检验 ============
print("\n" + "=" * 70)
print("逐股票检验（样本≥10才纳入判断）")
print(f"{'股票':<10} {'甜蜜点笔数':>10} {'胜率':>8} {'非甜笔数':>9} {'胜率':>8} {'差异':>8}  判定")
print("-" * 70)

by_ticker = defaultdict(list)
for r in all_records:
    by_ticker[r['ticker']].append(r)

valid_signals = []
for t in KLSE_21:
    recs = by_ticker.get(t, [])
    in_sweet = [r for r in recs if r['is_sweet']]
    out_sweet = [r for r in recs if not r['is_sweet']]

    if len(in_sweet) < 10 or len(out_sweet) < 10:
        print(f"{t:<10} {len(in_sweet):>10} {'--':>8} {len(out_sweet):>9} {'--':>8} {'--':>8}  样本不足")
        continue

    r1 = sum(1 for r in in_sweet if r['result'] == '涨') / len(in_sweet) * 100
    r0 = sum(1 for r in out_sweet if r['result'] == '涨') / len(out_sweet) * 100
    diff = r1 - r0

    if diff >= 10:
        verdict = "信号有效"
        valid_signals.append(t)
    elif diff <= -10:
        verdict = "反向"
    else:
        verdict = "无差异"

    print(f"{t:<10} {len(in_sweet):>10} {r1:>7.1f}% {len(out_sweet):>9} {r0:>7.1f}% {diff:>+7.1f}%  {verdict}")

# ============ 存 CSV ============
filename = '/Users/fernando/Documents/planbweek_sweetspot_validation.csv'
with open(filename, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['ticker', 'date', 'resonance', 'red_ratio',
                                           'red_streak', 'is_sweet', 'change_pct', 'result'])
    writer.writeheader()
    writer.writerows(all_records)

print(f"\n已保存到 {filename}")

print("\n" + "=" * 70)
print("最终判决")
print("=" * 70)
if valid_signals:
    print(f"\n通过检验(差异>=10%)的股票: {', '.join(valid_signals)}")
    print("这些股票的甜蜜点信号具有预测力")
else:
    print("\n没有股票通过检验")
    print("甜蜜点规则(60天持有)在这批股票上未证明预测力，需结合511信号回测的更大样本判断")
print("=" * 70 + "\n")
