"""
MACD共振 + 机构筹码分数 整合脚本
------------------------------------------------
流程:
  1. 用 dwm_macd_scanner.check_dwm_signal() 扫描 NASDAQ_LIST, 找出 D/W/M 三线共振的股票
  2. 对有共振的股票, 额外调用 institutional_score.institutional_stability_score()
     显示机构筹码是加码还是减码, 当作第三方佐证
  3. KLSE股票不适用机构筹码分数(yfinance无此数据), 只跑MACD共振, 机构分数栏显示 N/A

注意: 机构筹码分数只是辅助参考, 不影响共振判定本身。
"""

from dwm_macd_scanner import check_dwm_signal, NASDAQ_LIST, KLSE_LIST
from institutional_score import institutional_stability_score


def scan_with_institutional_score(tickers, label):
    print(f"\n{'='*70}")
    print(f"扫描 {label} (MACD共振 + 机构筹码分数)")
    print(f"{'='*70}")

    resonance_hits = []
    for t in tickers:
        result = check_dwm_signal(t)
        if not result.get('valid'):
            continue
        if not result.get('resonance'):
            continue

        # 有共振的股票, 额外查机构筹码分数 (KLSE股票会自动返回 None)
        score, note = institutional_stability_score(t)
        result['inst_score'] = score
        result['inst_note'] = note
        resonance_hits.append(result)

    if not resonance_hits:
        print("  (本次扫描无三线共振信号)")
        return []

    print(f"\n{'股票':<10}{'收盘':<10}{'机构分数':<10}{'机构说明'}")
    print("-" * 70)
    for r in resonance_hits:
        score_display = r['inst_score'] if r['inst_score'] is not None else "N/A"
        print(f"{r['ticker']:<10}{r['last_close']:<10}{str(score_display):<10}{r['inst_note']}")

    return resonance_hits


if __name__ == "__main__":
    nasdaq_results = scan_with_institutional_score(NASDAQ_LIST, "NASDAQ 清单")
    klse_results = scan_with_institutional_score(KLSE_LIST, "KLSE 清单")
