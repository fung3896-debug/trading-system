# manual_notes.py

NOTES = {
    "7103.KL": {
        "date": "2026-07-31",
        "iv": 3.34,          # DCF 内在价值
        "halve": 2.84,       # IV × 85% 减半线
        "exit": 3.34,        # IV × 100% 清仓线
        "type": "满格型",
        "comment": "red_ratio 1.00 满18月，超0.85警戒线，属满仓警惕区。量比6.11倍异常放量，需确认是买盘还是出货。估值已过减半线。",
    }
}


def check(ticker, price, in_profit):
    n = NOTES.get(ticker)
    if not n:
        return

    print(f"\n[{ticker}] {n['type']} · 备注于 {n['date']}")
    print(f"  现价 {price:.3f} / IV {n['iv']:.2f} = {price / n['iv']:.0%}")

    if price >= n["exit"]:
        action = "清仓条件已到"
    elif price >= n["halve"]:
        action = "减半条件已到"
    else:
        action = "维持"

    if action != "维持":
        action += "（盈利中，等人工确认）" if in_profit else "（未盈利，不启动）"

    print(f"  → {action}")
    print(f"  {n['comment']}")


if __name__ == "__main__":
    check("7103.KL", 3.00, True)