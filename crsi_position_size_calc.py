"""
crsi_position_size_calc.py
======================================================================
CRSI双确认信号的仓位计算器 —— 直接复用 position_size_calc.py 里
"固定风险法"的核心逻辑(用最大可承受亏损反推仓位)，不是另起一套。

跟 position_size_calc.py 的唯一差异：
  - CRSI 是纯动能型(无NTA可用，跟 momentum archetype 一致，12%硬止损)
  - risk_pct 在你平时用的基础上打折，反映CRSI是新验证、还没有实盘
    数据的信号：
      试运行期基础折扣: ×0.6
      对压力测试中反复垫底的股票(5000.KL/7233.KL/7197.KL): 再×0.7
  - 等CRSI跑出真实盈亏数据、可以用实盘结果重新校准后，这两个折扣
    应该重新评估，不是永久性的规则

用法：
  python3 crsi_position_size_calc.py <股票代码> <买入价> <账户资金> <你平时用的risk_pct>
  例如: python3 crsi_position_size_calc.py 8869.KL 2.91 50000 0.015
        (表示平时单笔最多愿意亏账户资金的1.5%)
======================================================================
"""

import sys

WATCH_CLOSELY = {'5000.KL', '7233.KL', '7197.KL'}
TRIAL_PERIOD_DISCOUNT = 0.6
WATCH_LIST_DISCOUNT = 0.7


def calc_crsi_position_size(capital: float, base_risk_pct: float,
                              entry: float, ticker: str) -> dict:
    if entry <= 0:
        raise ValueError("买入价必须大于 0")

    adjusted_risk_pct = base_risk_pct * TRIAL_PERIOD_DISCOUNT
    note = f"试运行期折扣 (你的risk_pct {base_risk_pct:.2%} × 0.6)"
    if ticker in WATCH_CLOSELY:
        adjusted_risk_pct *= WATCH_LIST_DISCOUNT
        note = f"试运行期折扣 + 高风险观察股票 (你的risk_pct {base_risk_pct:.2%} × 0.6 × 0.7)"

    hard_stop = entry * 0.88  # 12%硬止损，与momentum archetype一致
    max_loss_amount = capital * adjusted_risk_pct
    per_share_risk = entry - hard_stop
    shares = int(max_loss_amount / per_share_risk)
    total_cost = shares * entry

    halve_price = entry * 1.30   # 动能型标准：+30%减半
    exit_price = entry * 1.50    # 动能型标准：+50%清仓

    return {
        "ticker": ticker,
        "调整说明": note,
        "实际采用risk_pct": round(adjusted_risk_pct, 4),
        "entry": round(entry, 4),
        "12%硬止损价": round(hard_stop, 4),
        "最大可承受亏损金额": round(max_loss_amount, 2),
        "建议买入股数": shares,
        "预计投入资金": round(total_cost, 2),
        "减半仓位价(+30%)": round(halve_price, 4),
        "清仓价(+50%)": round(exit_price, 4),
    }


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("用法: python3 crsi_position_size_calc.py <股票代码> <买入价> <账户资金> <你平时用的risk_pct>")
        print("例如: python3 crsi_position_size_calc.py 8869.KL 2.91 50000 0.015")
        sys.exit(1)

    ticker = sys.argv[1]
    entry = float(sys.argv[2])
    capital = float(sys.argv[3])
    base_risk_pct = float(sys.argv[4])

    result = calc_crsi_position_size(capital, base_risk_pct, entry, ticker)
    print("=" * 60)
    print(f"CRSI仓位计算  |  {ticker}")
    print("=" * 60)
    for k, v in result.items():
        print(f"  {k}: {v}")
    if ticker in WATCH_CLOSELY:
        print(f"\n⚠️ {ticker} 在CRSI压力测试中反复出现在最差单笔名单里，")
        print(f"   建议额外盯紧，不要因为信号触发就掉以轻心")
# -*- coding: utf-8 -*-
"""
crsi_position_size_calc.py

CRSI双确认信号的简化仓位/止损计算器，借用现有"动能型"仓位管理框架
(position_size_calc.py里已经在用的cost-basis ladder逻辑)，不新造一套。

设计依据：
    CRSI信号本质上是动能型(没有DCF内在价值锚定,跟sweet spot的
    庄家型/满格型不同)，直接复用动能型的规则最合理：
    - 全局12%硬止损(和你系统里所有archetype一致)
    - +30%减半仓位(动能型标准)
    - +50%清仓(动能型标准)

与sweet spot的仓位差异(风险控制层面的调整，因为CRSI比sweet spot更年轻、
压力测试更少):
    - 建议起始仓位打6折(比照同等条件下sweet spot动能型仓位的60%)，
      作为"新信号试运行期"的保守调整，等实际运行几个月、有真实盈亏
      数据后再考虑上调到与sweet spot同等仓位
    - 对压力测试中反复出现在最差名单的股票(5000.KL/7233.KL/7197.KL)，
      额外打7折(即整体是原仓位的42%)，需要更强的确认才恢复正常仓位

⚠️ 这是试运行期的简化规则，不是最终版本。等CRSI在实盘/模拟盘跑出真实
盈亏数据后，应该用真实结果重新校准，而不是一直沿用这版基于回测的估算。

运行方式:
    python3 crsi_position_size_calc.py <股票代码> <触发日收盘价> <账户总资金>
    例如: python3 crsi_position_size_calc.py 8869.KL 2.91 50000
"""

import sys

# 压力测试中反复出现在最差名单的股票，需要额外降仓位
WATCH_CLOSELY = {'5000.KL', '7233.KL', '7197.KL'}

BASE_POSITION_PCT = 0.05      # 假设sweet spot动能型单笔基准仓位是账户5%(仅示例，按你实际规则调整)
TRIAL_PERIOD_DISCOUNT = 0.6   # 试运行期打6折
WATCH_LIST_DISCOUNT = 0.7     # 额外风险股票再打7折
HARD_STOP_PCT = 0.12          # 全局12%硬止损，与系统其他archetype一致
HALVE_AT_PCT = 0.30           # 涨30%减半仓位(动能型标准)
EXIT_AT_PCT = 0.50            # 涨50%清仓(动能型标准)


def calc_position(ticker: str, entry_price: float, account_size: float):
    position_pct = BASE_POSITION_PCT * TRIAL_PERIOD_DISCOUNT
    note = "试运行期标准仓位(基准×60%)"
    if ticker in WATCH_CLOSELY:
        position_pct *= WATCH_LIST_DISCOUNT
        note = "试运行期 + 高风险观察股票(基准×60%×70%=42%)"

    position_value = account_size * position_pct
    shares_approx = position_value / entry_price

    stop_loss_price = entry_price * (1 - HARD_STOP_PCT)
    halve_price = entry_price * (1 + HALVE_AT_PCT)
    exit_price = entry_price * (1 + EXIT_AT_PCT)

    print("=" * 60)
    print(f"CRSI仓位计算  |  {ticker}  |  {note}")
    print("=" * 60)
    print(f"触发价: {entry_price:.3f}")
    print(f"建议仓位: 账户资金的 {position_pct:.1%}  (约 {position_value:,.0f})")
    print(f"约可买入: {shares_approx:,.0f} 股 (未计入手续费/交易单位取整)")
    print(f"\n止损止盈规则(借用现有动能型框架):")
    print(f"  硬止损价 (-{HARD_STOP_PCT:.0%}): {stop_loss_price:.3f}")
    print(f"  减半仓位价 (+{HALVE_AT_PCT:.0%}): {halve_price:.3f}")
    print(f"  清仓价 (+{EXIT_AT_PCT:.0%}): {exit_price:.3f}")
    if ticker in WATCH_CLOSELY:
        print(f"\n⚠️ {ticker} 在CRSI压力测试中反复出现在最差单笔名单里，")
        print(f"   建议额外盯紧，不要因为信号触发就掉以轻心")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("用法: python3 crsi_position_size_calc.py <股票代码> <触发价> <账户总资金>")
        print("例如: python3 crsi_position_size_calc.py 8869.KL 2.91 50000")
        sys.exit(1)
    ticker = sys.argv[1]
    entry_price = float(sys.argv[2])
    account_size = float(sys.argv[3])
    calc_position(ticker, entry_price, account_size)

