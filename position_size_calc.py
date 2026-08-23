"""
position_size_calc.py
======================================================================
仓位与止损计算器 —— 对齐 Plan B Scanner 实际的三种持仓原型逻辑，
不是通用的固定 R:R 模板。

三种类型止损规则：
  庄家型 (banker)：12% 硬止损 + NTA×95%，取离现价更近（更保守）的那个
  满格型 (full)：12% 硬止损（无 NTA 加成）
  动能型 (momentum)：12% 硬止损（止盈另有成本阶梯，不在本脚本处理）

用法：
  python3 position_size_calc.py
======================================================================
"""


def calc_position_size(capital: float,
                        risk_pct: float,
                        entry: float,
                        archetype: str,
                        nta: float = None) -> dict:
    """
    capital:    总账户资金 (RM)
    risk_pct:   单笔最大亏损比例，建议 0.01-0.02
    entry:      买入价
    archetype:  'banker' / 'full' / 'momentum'
    nta:        每股净有形资产，仅 banker 类型需要
    """
    if entry <= 0:
        raise ValueError("买入价必须大于 0")
    if archetype not in ("banker", "full", "momentum"):
        raise ValueError("archetype 必须是 banker / full / momentum")

    # 12% 硬止损是所有类型的通用天花板
    hard_stop = entry * 0.88

    stop_loss = hard_stop
    nta_stop = None

    if archetype == "banker":
        if nta is None:
            raise ValueError("庄家型必须提供 NTA (每股净有形资产)")
        nta_stop = nta * 0.95
        # 取离现价更近（更保守）的那个作为实际止损价
        stop_loss = max(hard_stop, nta_stop)

    max_loss_amount = capital * risk_pct
    per_share_risk = entry - stop_loss

    if per_share_risk <= 0:
        raise ValueError("止损价 >= 买入价，无法计算仓位（检查 NTA 输入是否有误）")

    shares = int(max_loss_amount / per_share_risk)
    total_cost = shares * entry

    return {
        "archetype": archetype,
        "entry": round(entry, 4),
        "12%硬止损价": round(hard_stop, 4),
        "NTA×95%止损价": round(nta_stop, 4) if nta_stop else "N/A",
        "实际采用止损价": round(stop_loss, 4),
        "单笔最大亏损额(RM)": round(max_loss_amount, 2),
        "建议买入股数": shares,
        "预估总成本(RM)": round(total_cost, 2),
    }


def _prompt_float(label: str) -> float:
    while True:
        raw = input(f"{label}: ").strip()
        try:
            return float(raw)
        except ValueError:
            print("  → 请输入数字，重试")


def main():
    print("=" * 50)
    print("Plan B Scanner - 仓位与止损计算器")
    print("=" * 50)

    capital = _prompt_float("总账户资金 (RM)")
    risk_pct_input = _prompt_float("单笔最大亏损比例，输入 1 代表 1% (建议 1-2)")
    risk_pct = risk_pct_input / 100

    entry = _prompt_float("买入价 (RM)")

    print("\n持仓类型：1=庄家型  2=满格型  3=动能型")
    type_map = {"1": "banker", "2": "full", "3": "momentum"}
    while True:
        choice = input("选择 (1/2/3): ").strip()
        if choice in type_map:
            archetype = type_map[choice]
            break
        print("  → 请输入 1、2 或 3")

    nta = None
    if archetype == "banker":
        nta = _prompt_float("每股净有形资产 NTA (RM)")

    try:
        result = calc_position_size(capital, risk_pct, entry, archetype, nta)
    except ValueError as e:
        print(f"\n❌ 计算失败: {e}")
        return

    print("\n" + "-" * 50)
    for k, v in result.items():
        print(f"{k:20s}: {v}")
    print("-" * 50)


if __name__ == "__main__":
    main()
